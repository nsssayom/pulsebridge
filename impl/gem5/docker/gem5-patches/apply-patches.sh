#!/bin/bash
# Idempotent in-container patching of the bind-mounted gem5 source tree.
#
# Run inside the gem5 container (gem5-src is bind-mounted at /gem5).
# Safe to re-run: each patch checks for its own marker before applying.
#
# Patches applied:
#   1. ARM KVM SConsopts → neutered (v25.1 armv8_cpu.cc compile bug)
#   2. SCTLR_EL1.UCI=1 in AArch64 reset (enables user-mode `dc civac`)

set -euo pipefail

GEM5=/gem5
PATCHES=/impl/gem5/docker/gem5-patches

# --- 1) Neuter ARM KVM SConsopts ---------------------------------------
install -m 0644 "$PATCHES/arm-kvm-SConsopts" \
                "$GEM5/src/arch/arm/kvm/SConsopts"

# --- 2) SCTLR_EL1.UCI=1 for AArch64 reset ------------------------------
misc_cc="$GEM5/src/arch/arm/regs/misc.cc"
if grep -q "sctlr.uci = 1; // SE-MODE-UCI-PATCH" "$misc_cc"; then
    echo "patches: UCI already applied"
else
    # Insert `sctlr.uci = 1;` right after the `sctlr.sa0 = 1;` line inside
    # the AArch64 branch of sctlr_reset.
    sed -i '/sctlr\.sa0 = 1;$/a\            sctlr.uci = 1; // SE-MODE-UCI-PATCH' \
        "$misc_cc"
    # Verify the line landed exactly once.
    count=$(grep -c "SE-MODE-UCI-PATCH" "$misc_cc")
    if [[ "$count" != "1" ]]; then
        echo "patches: UCI sed produced $count matches (expected 1)" >&2
        exit 1
    fi
    echo "patches: UCI applied"
fi

# --- 3) Install custom Kconfig preset ----------------------------------
install -m 0644 "$PATCHES/../gem5-build-opts/ARM_MESI_Two_Level" \
                "$GEM5/build_opts/ARM_MESI_Two_Level"

# --- 4) Install WitnessPullEngine SimObject + pseudo_inst wiring -------
# Delegated to a Python helper because the edits span multiple files and
# need sentinel-based idempotency. See witness-dma/apply.py for details.
python3 "$PATCHES/witness-dma/apply.py"
