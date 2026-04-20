"""
Two-core ARM SE-mode gem5 config with Ruby MESI_Two_Level.

Runs the witness-export harness (producer + monitor threads) on cores
0-1 and, optionally, N cache-thrash stressor processes on cores 2..N+1
for the contention study.

Usage (from impl/gem5/):

    $GEM5_ROOT/build/ARM_MESI_Two_Level/gem5.opt \
        configs/two_core_ruby.py \
        --bench-bin workload/build/bench-aarch64-seqlock \
        --workload-dir ../workloads/synthesized/duty_bias \
        [--pacing-ns 0] [--epsilon 0.10] [--stl-window 8] \
        [--cpu-type TimingSimpleCPU|DerivO3CPU] \
        [--num-stressors N --stressor-binary workload/build/stress-aarch64]

The host must provide GEM5_ROOT pointing at a gem5 source tree built for
ARM with the MESI_Two_Level protocol; the script adds
$GEM5_ROOT/configs to sys.path and reuses gem5's own helper modules
(common.Options, common.Simulation, ruby.Ruby) to stay compatible with
gem5's evolving API.
"""

import argparse
import os
import sys
from os.path import abspath, isdir, isfile, join as pjoin

_GEM5_ROOT = os.environ.get("GEM5_ROOT")
if not _GEM5_ROOT or not isdir(pjoin(_GEM5_ROOT, "configs")):
    print(
        "error: GEM5_ROOT must point to a gem5 source tree "
        "(containing configs/ruby/MESI_Two_Level.py).",
        file=sys.stderr,
    )
    sys.exit(2)

sys.path.insert(0, pjoin(_GEM5_ROOT, "configs"))

import m5  # noqa: E402
from m5.objects import (  # noqa: E402
    AddrRange,
    Process,
    Root,
    SEWorkload,
    SrcClockDomain,
    System,
    VoltageDomain,
    WitnessPullEngine,
)
from m5.util import fatal  # noqa: E402

from common import Options, Simulation  # noqa: E402
from ruby import Ruby  # noqa: E402


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Two-core ARM SE+Ruby config for the witness harness",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Harness-specific (gem5's common Options.py registers its own
    # `--bench` for the legacy benchmark catalogue, so we use
    # `--bench-bin` for our cross-compiled harness binary.)
    parser.add_argument(
        "--bench-bin",
        required=True,
        help="path to an aarch64 bench-aarch64-<proto> binary",
    )
    parser.add_argument(
        "--workload-dir",
        required=True,
        help="workload directory (witness.csv, evidence.csv, PROVENANCE)",
    )
    parser.add_argument("--pacing-ns", type=int, default=0)
    parser.add_argument(
        "--dma-period-ns",
        type=int,
        default=1000,
        help="DMA-pull engine tick period in ns (protocol=dma only)",
    )
    parser.add_argument("--epsilon", type=float, default=0.10)
    parser.add_argument("--stl-window", type=int, default=8)
    parser.add_argument("--bench-verbose", action="store_true")
    # Stressor-specific
    parser.add_argument(
        "--num-stressors",
        type=int,
        default=0,
        help="extra CPUs running the cache-thrash stressor",
    )
    parser.add_argument(
        "--stressor-binary",
        default=None,
        help="aarch64 stressor binary (required if --num-stressors > 0)",
    )
    parser.add_argument(
        "--stressor-footprint",
        type=int,
        default=(4 << 20),
        help="per-stressor footprint in bytes",
    )
    parser.add_argument(
        "--stressor-stride",
        type=int,
        default=64,
        help="per-stressor stride in bytes",
    )
    # DMA-pull baseline (protocol=dma). Wire a WitnessPullEngine into
    # the Ruby DMASequencer so the bench's m5_dma_setup/start m5ops have
    # a real device to configure. Harmless for the other protocols — the
    # engine just sits idle if the bench never calls m5_dma_setup.
    parser.add_argument(
        "--enable-dma-engine",
        action="store_true",
        help="instantiate a WitnessPullEngine wired to Ruby (protocol=dma)",
    )
    parser.add_argument(
        "--dma-engine-clock",
        default="1GHz",
        help="clock for the WitnessPullEngine",
    )
    # Pull in gem5's own parser surfaces so --cpu-type, --num-dirs, etc.
    # work without us having to enumerate them by hand.
    Options.addCommonOptions(parser)
    Options.addSEOptions(parser)
    Ruby.define_options(parser)
    args = parser.parse_args()
    # gem5's default cpu-type is Atomic, which skips memory timing and
    # makes the whole Ruby latency story meaningless. Upgrade to a
    # timing-capable default unless the user asked for Atomic explicitly.
    if not any(a == "--cpu-type" or a.startswith("--cpu-type=")
               for a in sys.argv[1:]):
        args.cpu_type = "TimingSimpleCPU"
    return args


def _build_system(args):
    bench = abspath(args.bench_bin)
    if not isfile(bench):
        fatal(f"bench binary not found: {bench}")
    wl_dir = abspath(args.workload_dir)
    if not isdir(wl_dir):
        fatal(f"workload dir not found: {wl_dir}")

    # 3 = main thread (joiner) + producer + monitor. gem5's SE clone
    # routes each pthread_create to the next free ThreadContext, so we
    # need one context per concurrent pthread. The coherence traffic
    # studied here is producer<->monitor on cpu[1] and cpu[2]; cpu[0]
    # is blocked in pthread_join for the duration of the ROI.
    n_bench = 3
    n_total = n_bench + args.num_stressors
    stressor_bin = None
    if args.num_stressors > 0:
        if not args.stressor_binary:
            fatal("--num-stressors > 0 requires --stressor-binary")
        stressor_bin = abspath(args.stressor_binary)
        if not isfile(stressor_bin):
            fatal(f"stressor binary not found: {stressor_bin}")

    # Force our topology onto the gem5 helpers regardless of parser defaults.
    args.num_cpus = n_total
    args.ruby = True
    if not getattr(args, "cacheline_size", None):
        args.cacheline_size = 64
    if not getattr(args, "mem_size", None):
        args.mem_size = "512MB"

    (CPUClass, mem_mode, _) = Simulation.setCPUClass(args)
    CPUClass.numThreads = 1

    system = System(
        cpu=[CPUClass(cpu_id=i) for i in range(n_total)],
        mem_mode=mem_mode,
        mem_ranges=[AddrRange(args.mem_size)],
        cache_line_size=args.cacheline_size,
    )
    system.voltage_domain = VoltageDomain(voltage=args.sys_voltage)
    system.clk_domain = SrcClockDomain(
        clock=args.sys_clock, voltage_domain=system.voltage_domain
    )
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(
        clock=args.cpu_clock, voltage_domain=system.cpu_voltage_domain
    )
    for cpu in system.cpu:
        cpu.clk_domain = system.cpu_clk_domain

    system.workload = SEWorkload.init_compatible(bench)

    bench_cmd = [
        bench,
        "--workload", wl_dir,
        "--pacing-ns", str(args.pacing_ns),
        "--dma-period-ns", str(args.dma_period_ns),
        "--epsilon", str(args.epsilon),
        "--stl-window", str(args.stl_window),
    ]
    if args.bench_verbose:
        bench_cmd.append("-v")

    bench_proc = Process(pid=100, cmd=bench_cmd, executable=bench)

    # Every bench CPU points at the *same* Process object. gem5's SE
    # syscall layer routes the harness's pthread_create onto the next
    # CPU context; base.cc still expects cpu.workload.size() ==
    # numThreads, so we assign the shared Process to both. Stressors
    # below are independent single-threaded processes on their own CPUs.
    for cpu in system.cpu[:n_bench]:
        cpu.workload = bench_proc
        cpu.createThreads()

    for i in range(args.num_stressors):
        p = Process(
            pid=200 + i,
            cmd=[
                stressor_bin,
                str(args.stressor_footprint),
                str(args.stressor_stride),
            ],
            executable=stressor_bin,
        )
        system.cpu[n_bench + i].workload = p
        system.cpu[n_bench + i].createThreads()

    # Optional DMA-pull engine for baseline C. Constructed before
    # Ruby.create_system so its `dma` port can be registered as one of
    # Ruby's dma_ports; without that, the MESI_Two_Level config skips
    # creating a DMAController for this endpoint.
    dma_ports = []
    if args.enable_dma_engine:
        system.witness_pull_engine = WitnessPullEngine(
            clk_domain=system.cpu_clk_domain,
        )
        dma_ports = [system.witness_pull_engine.dma]

    Ruby.create_system(args, False, system, dma_ports=dma_ports)
    system.ruby.clk_domain = SrcClockDomain(
        clock=args.ruby_clock, voltage_domain=system.voltage_domain
    )

    if len(system.cpu) != len(system.ruby._cpu_ports):
        fatal(
            f"ruby ports ({len(system.ruby._cpu_ports)}) "
            f"!= cpus ({len(system.cpu)})"
        )
    for i, cpu in enumerate(system.cpu):
        cpu.createInterruptController()
        ruby_port = system.ruby._cpu_ports[i]
        cpu.icache_port = ruby_port.in_ports
        cpu.dcache_port = ruby_port.in_ports

    return system


def _run():
    args = _parse_args()
    system = _build_system(args)
    root = Root(full_system=False, system=system)

    m5.instantiate()

    print(
        f"two_core_ruby: root={root.__class__.__name__} "
        f"bench={args.bench_bin} workload={args.workload_dir} "
        f"cpus={args.num_cpus} stressors={args.num_stressors} "
        f"cpu_type={args.cpu_type}",
        flush=True,
    )
    exit_event = m5.simulate()
    print(
        f"two_core_ruby: exit @ tick {m5.curTick()} "
        f"cause={exit_event.getCause()} code={exit_event.getCode()}",
        flush=True,
    )


if __name__ == "__m5_main__":
    _run()
