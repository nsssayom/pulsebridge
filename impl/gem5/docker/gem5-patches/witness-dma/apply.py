#!/usr/bin/env python3
"""
Install the WitnessPullEngine SimObject into the bind-mounted gem5 tree
and wire it into the build + pseudo-instruction dispatch.

Idempotent: each step is guarded by a sentinel check, so re-running after
a partial failure (or on each container start) does nothing on files that
already look patched.

Called from apply-patches.sh. Assumes gem5-src/ lives at /gem5 inside the
container and this script lives alongside witness_pull_engine.{hh,cc}
and WitnessPullEngine.py.
"""

import pathlib
import shutil
import sys

GEM5 = pathlib.Path("/gem5")
HERE = pathlib.Path(__file__).resolve().parent


def die(msg):
    print(f"witness-dma patch: {msg}", file=sys.stderr)
    sys.exit(1)


def log(msg):
    print(f"witness-dma patch: {msg}")


# --- 1) Copy new source files into gem5-src/src/dev/ -------------------

def copy_sources():
    dev_dir = GEM5 / "src" / "dev"
    if not dev_dir.is_dir():
        die(f"{dev_dir} does not exist; wrong GEM5 path?")
    for name in ("witness_pull_engine.hh",
                 "witness_pull_engine.cc",
                 "WitnessPullEngine.py"):
        src = HERE / name
        dst = dev_dir / name
        if not src.is_file():
            die(f"missing source: {src}")
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            continue
        shutil.copy2(src, dst)
        log(f"installed {dst}")


# --- 2) Patch dev/SConscript -------------------------------------------

SCONSCRIPT_MARKER = "WitnessPullEngine.py"
SCONSCRIPT_APPEND = """

# --- WitnessPullEngine (added by impl/gem5/docker/gem5-patches/witness-dma) ---
SimObject('WitnessPullEngine.py', sim_objects=['WitnessPullEngine'])
Source('witness_pull_engine.cc')
"""


def patch_sconscript():
    p = GEM5 / "src" / "dev" / "SConscript"
    text = p.read_text()
    if SCONSCRIPT_MARKER in text:
        return
    p.write_text(text + SCONSCRIPT_APPEND)
    log(f"appended SimObject/Source registration to {p}")


# --- 3) Patch include/gem5/asm/generic/m5ops.h -------------------------
# Extend M5OP_FOREACH with two new entries that alias m5_dma_setup and
# m5_dma_start onto M5OP_RESERVED1 and M5OP_RESERVED2 respectively. The
# userspace m5op library generates real ELF symbols from this macro.

M5OPS_MARKER = "m5_dma_setup"
M5OPS_ANCHOR = "    M5OP(m5_hypercall, M5OP_HYPERCALL)                          \\"
M5OPS_REPLACEMENT = (
    "    M5OP(m5_hypercall, M5OP_HYPERCALL)                          \\\n"
    "    M5OP(m5_dma_setup, M5OP_RESERVED1)                          \\\n"
    "    M5OP(m5_dma_start, M5OP_RESERVED2)                          \\"
)


def patch_m5ops_h():
    p = GEM5 / "include" / "gem5" / "asm" / "generic" / "m5ops.h"
    text = p.read_text()
    if M5OPS_MARKER in text:
        return
    if M5OPS_ANCHOR not in text:
        die(f"{p}: could not locate M5OP(m5_hypercall...) anchor; upstream "
            f"gem5 may have changed the macro layout.")
    text = text.replace(M5OPS_ANCHOR, M5OPS_REPLACEMENT, 1)
    p.write_text(text)
    log(f"extended M5OP_FOREACH in {p}")


# --- 3b) Patch include/gem5/m5ops.h to declare the C prototypes --------
# The assembly macro generates ELF symbols; the header declares them for
# C/C++ callers. Without these the bench can't call m5_dma_setup by name.

PROTO_MARKER = "m5_dma_setup"
PROTO_ANCHOR = "void m5_workload();"
PROTO_REPLACEMENT = (
    "void m5_workload();\n"
    "/* --- WitnessPullEngine prototypes (impl/gem5 patch) --- */\n"
    "void m5_dma_setup(uint64_t src_va, uint64_t dst_va,\n"
    "                  uint64_t size, uint64_t period_ns);\n"
    "void m5_dma_start(void);"
)


def patch_m5ops_public_h():
    p = GEM5 / "include" / "gem5" / "m5ops.h"
    text = p.read_text()
    if PROTO_MARKER in text:
        return
    if PROTO_ANCHOR not in text:
        die(f"{p}: m5_workload anchor missing; bailing.")
    text = text.replace(PROTO_ANCHOR, PROTO_REPLACEMENT, 1)
    p.write_text(text)
    log(f"added prototypes to {p}")


# --- 4) Patch src/sim/pseudo_inst.hh -----------------------------------
# The stock hh declares pseudoInstWork() inline and lists all M5OP_* cases;
# we change RESERVED1/2 from "warn and return false" to invokeSimcall
# dispatches, and add forward declarations for dmaSetup/dmaStart so the
# template compiles.

HH_DECL_MARKER = "void dmaSetup(ThreadContext *tc"
HH_DECL_ANCHOR = "void m5Hypercall(ThreadContext *tc, uint64_t hypercall_id);"
HH_DECL_REPLACEMENT = (
    "void m5Hypercall(ThreadContext *tc, uint64_t hypercall_id);\n"
    "/* --- WitnessPullEngine dispatch (impl/gem5 patch) --- */\n"
    "void dmaSetup(ThreadContext *tc, GuestAddr src_va, GuestAddr dst_va,\n"
    "              uint64_t size, uint64_t period_ns);\n"
    "void dmaStart(ThreadContext *tc);"
)

HH_CASE_MARKER = "invokeSimcall<ABI>(tc, dmaSetup);"
HH_CASE_ANCHOR = """      case M5OP_RESERVED1:
      case M5OP_RESERVED2:
      case M5OP_RESERVED3:
      case M5OP_RESERVED4:
      case M5OP_RESERVED5:
        warn("Unimplemented m5 op (%#x)\\n", func);
        return false;"""
HH_CASE_REPLACEMENT = """      case M5OP_RESERVED1:
        invokeSimcall<ABI>(tc, dmaSetup);
        return true;

      case M5OP_RESERVED2:
        invokeSimcall<ABI>(tc, dmaStart);
        return true;

      case M5OP_RESERVED3:
      case M5OP_RESERVED4:
      case M5OP_RESERVED5:
        warn("Unimplemented m5 op (%#x)\\n", func);
        return false;"""


def patch_pseudo_inst_hh():
    p = GEM5 / "src" / "sim" / "pseudo_inst.hh"
    text = p.read_text()
    changed = False
    if HH_DECL_MARKER not in text:
        if HH_DECL_ANCHOR not in text:
            die(f"{p}: m5Hypercall anchor missing; bailing.")
        text = text.replace(HH_DECL_ANCHOR, HH_DECL_REPLACEMENT, 1)
        changed = True
    if HH_CASE_MARKER not in text:
        if HH_CASE_ANCHOR not in text:
            die(f"{p}: RESERVED case block anchor missing; bailing.")
        text = text.replace(HH_CASE_ANCHOR, HH_CASE_REPLACEMENT, 1)
        changed = True
    if changed:
        p.write_text(text)
        log(f"patched {p}")


# --- 5) Patch src/sim/pseudo_inst.cc -----------------------------------
# Add an include for witness_pull_engine.hh + page_table.hh, and append
# the two handler function definitions at the bottom of the pseudo_inst
# namespace.

CC_MARKER = "pseudo_inst::dmaSetup"

CC_INCLUDE_ANCHOR = '#include "sim/system.hh"'
CC_INCLUDE_REPLACEMENT = (
    '#include "sim/system.hh"\n'
    '/* --- WitnessPullEngine dispatch (impl/gem5 patch) --- */\n'
    '#include "dev/witness_pull_engine.hh"\n'
    '#include "mem/page_table.hh"\n'
    '#include "sim/process.hh"'
)

CC_FN_BLOCK = '''

/* --- WitnessPullEngine dispatch (impl/gem5 patch) ---------------------
 * m5_dma_setup(src_va, dst_va, size, period_ns): translate both VAs
 *   through the calling process's SE page table, hand the PAs to the
 *   singleton engine. Called once at bench init.
 * m5_dma_start(): arm periodic pulls on the singleton engine.
 */
static bool
witnessTranslateSE(ThreadContext *tc, Addr va, Addr &pa)
{
    Process *proc = tc->getProcessPtr();
    if (!proc) return false;
    return proc->pTable->translate(va, pa);
}

void
dmaSetup(ThreadContext *tc, GuestAddr src_va, GuestAddr dst_va,
         uint64_t size, uint64_t period_ns)
{
    DPRINTF(PseudoInst,
            "pseudo_inst::dmaSetup(src_va=%#x dst_va=%#x size=%llu "
            "period_ns=%llu)\\n",
            src_va.addr, dst_va.addr,
            (unsigned long long)size, (unsigned long long)period_ns);

    if (!WitnessPullEngine::instance) {
        warn("m5_dma_setup: no WitnessPullEngine instance in this system");
        return;
    }
    Addr src_pa = 0, dst_pa = 0;
    if (!witnessTranslateSE(tc, src_va.addr, src_pa)) {
        warn("m5_dma_setup: translate src_va=%#x failed", src_va.addr);
        return;
    }
    if (!witnessTranslateSE(tc, dst_va.addr, dst_pa)) {
        warn("m5_dma_setup: translate dst_va=%#x failed", dst_va.addr);
        return;
    }
    Tick period_ticks = sim_clock::as_int::ns * period_ns;
    WitnessPullEngine::instance->configure(src_pa, dst_pa, size, period_ticks);
}

void
dmaStart(ThreadContext *tc)
{
    DPRINTF(PseudoInst, "pseudo_inst::dmaStart()\\n");
    if (!WitnessPullEngine::instance) {
        warn("m5_dma_start: no WitnessPullEngine instance in this system");
        return;
    }
    WitnessPullEngine::instance->startPulling();
}
'''

CC_NAMESPACE_CLOSE = "} // namespace pseudo_inst"


def patch_pseudo_inst_cc():
    p = GEM5 / "src" / "sim" / "pseudo_inst.cc"
    text = p.read_text()
    if CC_MARKER in text:
        return
    if CC_INCLUDE_ANCHOR not in text:
        die(f"{p}: include anchor missing; bailing.")
    if CC_NAMESPACE_CLOSE not in text:
        die(f"{p}: pseudo_inst namespace close missing; bailing.")
    text = text.replace(CC_INCLUDE_ANCHOR, CC_INCLUDE_REPLACEMENT, 1)
    text = text.replace(CC_NAMESPACE_CLOSE,
                        CC_FN_BLOCK + "\n" + CC_NAMESPACE_CLOSE, 1)
    p.write_text(text)
    log(f"patched {p}")


def main():
    copy_sources()
    patch_sconscript()
    patch_m5ops_h()
    patch_m5ops_public_h()
    patch_pseudo_inst_hh()
    patch_pseudo_inst_cc()
    log("all steps complete")


if __name__ == "__main__":
    main()
