# Narration script

Verbatim speaker script for the reveal.js deck of an academic
project presentation. Each section heading matches a slide title;
the body is the text the presenter reads. The same text is embedded
in `slides.md` as `Note:` blocks so it renders in reveal.js's
speaker view (press `S`).

Target duration: 18–20 minutes at a natural pace. The register is
an academic project presentation, not a public talk. Every acronym
and every technical term is defined on first use. The audience is
assumed to know general computer architecture (caches, multicore,
memory hierarchy) but not CPS monitoring, sequence locks, DMA
engines, or ARM memory-ordering rules.

---

## 1. Title — Coherent Publication Channels for CPS Monitoring

This presentation describes a project that studies the communication
channel between the main controller and the safety-critical monitor
on modern multicore systems. The systems in question are
safety-critical cyber-physical systems, abbreviated CPS, and include
automotive ECUs, drone flight controllers, and industrial robots.
Modern CPS platforms pair a fast application CPU with a small
supervisory core whose role is to catch the main CPU producing an
unsafe output before that output reaches an actuator.

The central question of the project is how the supervisory core
should read the main core's state. The finding is that handling the
channel incorrectly is not a performance issue. It is a correctness
failure.

The presentation introduces each technical concept on first use.
The audience is assumed to know general computer architecture; CPS
monitoring, cache coherence rules, and synchronization primitives
are defined as they appear. The presentation is organized into six
sections and runs approximately twenty minutes.

## 2. The safety island pattern

The first technical term to define is "safety island." A safety
island is a small supervisory core located on the same
system-on-chip, abbreviated SoC, as the main application complex.
It runs an independent software stack, sometimes under a different
real-time operating system (RTOS) and sometimes at a different
instruction-set architecture level from the main CPU. Its role is
not to perform control work. Its role is to observe the controller
and detect unsafe output before it reaches the actuator.

The pattern is now standard in automotive silicon. Arm markets an
Automotive Enhanced safety island product line. NVIDIA's DRIVE
platform includes a functional-safety island. ISO 26262, the
international automotive functional-safety standard, effectively
requires this partitioning at its top safety grades. Those grades
are the Automotive Safety Integrity Levels, or ASIL. ASIL-D is the
highest grade and covers systems in which a failure can cause
serious injury or death. The same partitioning pattern appears in
aerospace and industrial-control SoCs.

Given the pattern, the architectural question the project addresses
is narrow: how should the main controller hand its state to the
supervisory core?

## 3. What the monitor actually reads

The monitor does not read a single scalar value. It reads a
structured record consisting of multiple related fields that must be
interpreted together as one logical publication.

In this study the record is 64 bytes, which is the size of one
cache line on most modern processors. A cache line is the unit of
memory that a CPU cache loads and evicts as an indivisible block.
The record is aligned to a cache-line boundary so that it occupies
exactly one line.

The record carries five items. First, an epoch, which is a counter
that identifies the publication. Second, a nanosecond timestamp.
Third, three duty values for a three-phase pulse-width-modulated
output. Pulse-width modulation, or PWM, is the standard mechanism
by which digital chips drive analog actuators such as a three-phase
motor: instead of varying the output voltage, the chip varies the
fraction of time the voltage is asserted. Fourth and fifth are
metadata fields.

One of the metadata fields is central to the rest of the
presentation and is worth introducing here. The `config_id` field
carries a redundant 16-bit copy of the low half of the epoch. If the
primary epoch and the redundant copy disagree, the reader has
observed fragments of two different publications stitched together
into one logical read. That redundant copy serves as the torn-read
detector used throughout the experimental results.

## 4. The strawman — we have cache coherence

A tempting first answer to the channel question is worth stating
explicitly, because it represents the most common initial intuition.

Modern multicore CPUs provide cache coherence. Different cores
therefore observe a consistent view of shared memory. The strawman
argument follows: place the record in shared memory, let the
coherence protocol handle the rest, and the problem is solved.

This intuition is incorrect. The next two slides explain why,
because the reasoning is the central technical insight of the
project.

## 5. Coherence is not consistency

Cache coherence and memory consistency sound like synonyms, but
they describe different properties, and they are routinely confused.
Both require explicit definition.

Cache coherence is a property of a single memory location. For one
address, all cores must eventually agree on the order of writes to
that address. Hardware protocols such as MESI and MOESI provide
this guarantee. MESI names the four states a cache line can hold
across cores: Modified, Exclusive, Shared, Invalid. MOESI adds an
Owned state. Neither protocol constrains ordering between different
addresses.

Memory consistency is the property that governs ordering across
different addresses. When one core writes address X and then writes
address Y, memory consistency determines whether another core
necessarily observes the two writes in that same order. On ARMv8,
the 64-bit ARM architecture used in the gem5 experiments of this
project, the answer is no, unless the program states so explicitly.
ARMv8 is classified as a weak memory model. Without a matched
release-acquire fence pair, or a data-memory-barrier instruction,
called DMB, both the hardware and the compiler are free to reorder
writes to independent addresses. As a consequence, the producer may
issue stores to `duty_a`, `duty_b`, and `duty_c` in program order,
while a reader on another core observes those stores in a different
order, interleaved with fields from an older publication.

This reordering is the vulnerability that the next slide
illustrates.

## 6. A torn read, in slow motion

The failure scenario, traced step by step.

The producer completes publication *k* by writing its three
duty-value fields. It then begins publication *k+1*. It writes the
new epoch. It writes `duty_a` to the new value, 6. At that instant,
the reader on a different core copies the record.

The reader observes an epoch of *k+1* and a `duty_a` of 6, because
those two fields have just been updated. However, `duty_b` and
`duty_c` still hold the previous value, 5, because the producer has
not yet reached them. The resulting observation is a record whose
fields originate in two different publications. That specific
combination never existed inside the producer; the producer was
never in a state in which `duty_a` was 6 and the other two duties
were still 5.

This observation is a torn read. The redundant-epoch detector
catches it. The low 16 bits of the header epoch have advanced to
*k+1*, but the redundant copy in `config_id`, which the writer
updates last, still reads *k*. The two disagree, and the read is
flagged as torn.

## 7. Why torn reads are a correctness failure

It is necessary to categorize what a torn read actually is. The
natural initial reaction is that the monitor simply missed one
sample and will recover on the next one, so the event is tolerable.
That framing is incorrect.

The monitor's function is to verify that the controller's output is
consistent with expected behavior. If the record under verification
is a chimera, that is, a state that never existed inside the
controller, then the verification is meaningless. The monitor may
alarm on a nonexistent fault. More seriously, it may fail to alarm
on a real fault, because the chimera happened to appear benign
under the safety specification.

This categorization governs the rest of the analysis. The project
does not aim to minimize nanoseconds on an incorrect answer; it
aims to minimize nanoseconds on an answer that is correct in the
first place.

## 8. Two design choices, not one

Two separate design choices interact in this channel, and keeping
them distinct is central to the project's analysis.

The first choice is transport: the mechanism by which the record
physically moves from producer memory to monitor memory. The
project compares two transports. The first is direct coherent
sharing, in which both cores read and write the same memory. The
second is explicit copy, in which a small hardware engine transfers
the record from producer memory into a separate mirror page.

The second choice is the synchronization primitive: whether the
record carries a discipline that allows the reader to detect an
overlapping writer. The project compares three primitives: no
primitive, a sequence lock, and a generation-counter double buffer.

Two transports and three primitives define a 2-by-3 grid. The
project populates five of the six cells. The sixth cell, DMA
transport combined with a double buffer, is omitted because the DMA
engine forces the mirror to be a single active slot and does not
generalize to the two-slot design without a redesign of the engine.

The resulting five architectures are the units of comparison for
the remainder of the presentation.

## 9. Transport A — direct coherent sharing

Transport A is direct coherent sharing, the simplest option. The
producer writes to a shared record. The monitor reads the same
record. The cache coherence protocol, MESI in this setup, moves the
cache line between the two cores' L1 caches on demand. The L1 cache
is the smallest and fastest level of the cache hierarchy and sits
adjacent to each core.

When the producer writes, the monitor's copy of the line is
invalidated. When the monitor subsequently reads, it refetches the
line. The design uses a single memory region, has no explicit copy
step, and requires no additional hardware.

This is the design that the intuition addressed two slides earlier
corresponds to.

## 10. Transport B — DMA-pulled mirror

Transport B is an explicit hardware transfer. The producer writes
to its own private memory. A small direct-memory-access engine,
called a DMA engine, periodically copies the record from producer
memory into a separate mirror page, and the monitor reads only from
the mirror. DMA is a standard SoC feature that allows an I/O block
to move data between memory regions without involving the CPU.

In the gem5 simulation used in this project, the engine is
implemented as a custom SimObject, which is gem5's unit of modeled
hardware, and is named `WitnessPullEngine`. The configuration used
throughout the study copies the record once every 1000 nanoseconds,
that is, once per microsecond.

One detail is important. The mirror page still resides in coherent
memory. This transport is not a coherence-disabled baseline. The
only property that changes is the communication pattern: the
monitor no longer touches the producer's hot cache line directly.

## 11. Primitive A — sequence lock

The first synchronization primitive is a sequence lock, usually
shortened to seqlock. The seqlock adds one word to the record, a
version counter, with a simple convention: an odd version indicates
that a writer is mid-update and the record is unstable, while an
even version indicates that the record is stable and safe to read.

The writer executes four steps: increment the version to an odd
value, write the payload fields, and increment the version to the
next even value.

The reader executes four steps as well: sample the version into a
local variable, verify that the sample is even, copy all payload
fields into a local scratch buffer, and sample the version a second
time. If the two samples match and the first was even, the read is
valid. If they do not match, or if the first sample was odd, the
reader has detected a race with the writer and retries.

The reader never acquires a lock, which makes the design lock-free
on the reader side. The writer never waits for readers, which makes
it wait-free on the writer side. The seqlock is a textbook
technique: Leslie Lamport described it in the 1970s, and the Linux
kernel currently uses it to publish timekeeping state.

## 12. Primitive B — generation-counter double buffer

The second primitive is a generation-counter double buffer. The
record is stored in two slots rather than one, and a generation
counter is maintained as a monotonic integer, that is, an integer
that only increases.

The writer selects the inactive slot, writes the full record into
it, and then release-stores a new generation value. A release-store
is a compiler-and-hardware construct that guarantees the slot
contents become globally visible before the updated generation
value becomes visible.

The reader samples the generation counter, copies the slot whose
index corresponds to that generation, samples the counter a second
time, and accepts the read if the two samples match. If the counter
advanced by two or more between the two samples, the writer lapped
the reader inside the buffer, and the reader retries.

One design point is easy to overlook. A binary flag that indicates
the current slot is not a correct replacement for the counter. If
the writer flips the flag twice during a single read, a case
referred to as the double-lap, the flag returns to its original
value. The reader perceives no change and accepts a torn slot. A
monotonic counter captures the double-lap because two flips produce
an increment of two. For this reason, the project specifically uses
a counter rather than a flag.

## 13. The five architectures

The complete matrix comprises five architectures. Three use direct
coherent sharing: `unsync` uses no primitive, `seqlock` uses a
sequence lock, and `dblbuf` uses a generation-counter double
buffer. Two use the DMA-pulled mirror: `dma_naive` uses no
primitive, and `dma_seqlock` uses a sequence lock on the mirror.

The layout is useful because every pairwise comparison changes
exactly one variable. The comparison across `unsync`, `seqlock`,
and `dblbuf` holds the transport fixed at direct sharing and
isolates the effect of the primitive. The comparison between
`unsync` and `dma_naive` holds the primitive fixed at none and
isolates the effect of the transport. The comparison between
`seqlock` and `dma_seqlock` holds the primitive fixed at sequence
lock and isolates the effect of the transport.

This grid is the analytical frame used to interpret every result
that follows.

## 14. The testbed

All five architectures are implemented in C11, which is the 2011 C
language standard, as a shared core library. The library is
cross-compiled for 64-bit ARM, identified by the target name
`aarch64`, and executed under gem5 in system-emulation mode.
System-emulation mode is a gem5 configuration that executes a
user-mode binary directly, without booting a full operating system.

The coherence protocol is Ruby `MESI_Two_Level`. Ruby is gem5's
detailed memory-system model, and `MESI_Two_Level` is its reference
implementation of a two-level MESI hierarchy: private L1 caches per
core and a shared L2 cache backed by a coherence directory that
tracks which cores hold a copy of each line.

The benchmark uses three CPUs: a producer, a monitor, and a joiner
that waits for the producer to finish. Between zero and four
additional stressor CPUs run concurrently. Each stressor executes a
cache thrasher that touches a disjoint block of cache lines,
meaning lines that neither the producer nor the monitor touches.
The stressors therefore share no memory with the benchmark, but
they compete for the shared cache hierarchy and the coherence
directory, which introduces controlled hierarchy pressure. For the
DMA variants, the custom pull engine is attached as a SimObject on
Ruby's DMA sequencer.

One honest qualification up front: this testbed is not a
cycle-accurate model of any specific commercial interconnect. It
provides protocol-level architectural evidence measured as Ruby
message counts and directory traffic. That is the claim the project
makes, and no stronger claim is implied.

## 15. Matrix and metrics

Each matrix cell executes 5000 publications.

Two workloads are used. The first is a captured trace from a real
STM32 development board. STM32 is a family of ARM Cortex-M
microcontrollers widely used in embedded controllers. The board was
instrumented with a logic analyzer, which recorded the duty-value
stream while the controller ran an algorithm that produces sparse
divergence between intended and realized behavior. The second
workload is synthesized with a sustained 15 percent multiplicative
bias between intended and realized values, which causes the monitor
to fire repeatedly rather than sparsely.

Contention is varied across three levels: 0, 2, and 4 stressor
CPUs. Five architectures, two workloads, and three contention
levels together define the 30-cell experimental matrix.

Each cell contributes five primary metrics. The first is torn-read
fraction, measured by the redundant-epoch detector described
earlier. The second is CPU-side coherence messages per publish,
computed by summing two Ruby traffic counters: L1-to-directory and
directory-to-memory. The third is DMA messages per publish, which
is nonzero only for the DMA architectures. The fourth is retries
per run, which counts reads rejected by the reader and repeated.
The fifth is whole-workload simulated time, defined as the gem5
simulated clock from the start to the end of the 5000-publication
benchmark. That last metric serves as a throughput-style cost
proxy rather than a per-publication latency distribution, and the
caveat is revisited in the limitations section.

## 16. Result 1 — correctness

The first metric gates every other result: torn reads.

The two architectures without a primitive tear in every measured
condition. Averaged across the 30-cell matrix, `unsync` tears on
4.26 percent of read attempts and `dma_naive` tears on 18.22
percent, which is roughly four times worse than unsynchronized
direct sharing. The three architectures with a primitive, namely
`seqlock`, `dblbuf`, and `dma_seqlock`, return zero torn reads in
every cell.

The `dma_naive` result is particularly significant. The addition
of a DMA engine, which isolates the monitor from the producer's
hot cache line, did not repair correctness. It degraded
correctness, because the reader now races on the mirror side in
addition to the producer side.

Transport alone does not solve the tearing problem. The primitive
does. This is the central claim of the project, and it appears on
the first result plot.

## 17. Result 2 — CPU-side coherence traffic

The three correct designs are now compared on cost. The first cost
dimension is CPU-side coherence messages per publish, which
measures the channel's traffic on the shared cache hierarchy.

`dblbuf` averages 27.6 messages per publish. `seqlock` averages
37.8. `dma_seqlock` averages 28.9, close to `dblbuf`.

The explanation for `seqlock`'s higher cost is architectural. A
seqlock keeps both the producer and the monitor on a single hot
record. The version validation and the field copy both contend on
the same cache line, so every validation pulls the line and every
producer update invalidates it. `dblbuf`, by contrast, moves the
producer to the inactive slot, so the monitor's and the producer's
working sets do not overlap during a copy. The monitor fetches
only the small generation word on the hot path, not the full
payload line. The 27 percent reduction in traffic originates here.

## 18. Result 3 — whole-workload simulated time

The second cost dimension is whole-workload simulated time: the
total simulated-clock duration gem5 reports for retiring all 5000
publications.

`dblbuf` wins in every cell of the matrix. Averaged over the full
matrix, `dblbuf` takes 0.346 milliseconds. `seqlock` takes 0.485.
`dma_seqlock` takes 0.482. Dividing by 5000 publications yields
approximately 69 nanoseconds per publish for `dblbuf`. This figure
serves as a ballpark anchor rather than a latency distribution.
`dblbuf` is 29 percent faster than `seqlock` and 28 percent faster
than `dma_seqlock`, and it is the fastest correct design in all 15
captured-workload cells.

## 19. Result 4 — the retry cliff

The third cost dimension is where the gap between the correct
designs becomes sharp: retries per run. A retry occurs when the
reader detects a protocol inconsistency, rejects the sample, and
repeats the read.

`dblbuf` averages 0.7 retries per 5000-publication run, essentially
never retrying. `seqlock` averages 1,543 retries per run.
`dma_seqlock` averages 14,345 retries per run, which is more than
nine times `seqlock`'s rate and approximately twenty thousand times
`dblbuf`'s rate.

`dblbuf` and `dma_seqlock` are equally correct under the torn-read
metric: neither ever returns a torn record. However, the
reader-side work required to maintain that correctness differs by
four orders of magnitude.

Correctness is a binary property. Cost is not. The two must be
measured and reported separately.

## 20. Result 5 — the accepted-read cliff

The complement of retries is accepted reads: the fraction of read
attempts that return valid data.

`dblbuf` accepts 99.95 percent. `seqlock` accepts 97.85 percent.
`dma_seqlock` accepts only 8.03 percent, which is approximately
twelve times worse than either direct-sharing design.

The mechanism is architectural. The DMA mirror refreshes on its
own fixed cadence, once every 1000 nanoseconds in this
configuration, regardless of the reader's state. Every refresh is
a potential race window for the reader. In `dblbuf`, the only race
window is the brief interval during which the writer stores a new
generation value. In `dma_seqlock`, the reader races effectively
continuously.

This result matters because a real safety-island core operates
under a bounded CPU budget. An 8 percent accept rate implies that
92 percent of the monitor's reader-side cycles are spent retrying
rather than performing monitor work. The design is logically
correct but operationally expensive.

## 21. Workload and contention

Two sensitivity axes are relevant.

The first is workload shape. Moving from the captured STM32 trace
to the synthesized sustained-bias workload raises CPU-side traffic
by 37 percent for `dblbuf` and by 36 percent for `seqlock`. For the
synchronized DMA mirror, traffic remains essentially flat, with
less than one percent change. This pattern is architecturally
consistent: the DMA design keeps the monitor interacting with the
mirror rather than with the producer's hot line, so producer-side
activity has a smaller effect on the monitor.

The second axis is contention. Increasing stressor CPUs from zero
to four raises traffic for every architecture. However, the
ordering of designs is stable. The architectures with a primitive
remain zero-torn in every cell. The architectures without a
primitive tear in every cell. And `dblbuf` is the fastest correct
design in every cell.

Workload and contention shift the absolute numbers. They do not
change the ranking.

## 22. The headline

The project's central finding, stated in one sentence: a coherent
memory fabric can move the most recent cache line rapidly, but it
cannot inform the reader whether the multiple fields on that line
belong to one logical publication. That property is a contract, and
the contract must be supplied by the publication primitive, not by
the transport.

Across the five architectures evaluated, the choice of primitive
dominates the choice of transport. Explicit DMA transfer does not,
by itself, repair correctness. Both the sequence lock and the
double buffer repair correctness regardless of the transport on
which they sit. Among the four correct combinations, the
generation-counter double buffer over direct coherent sharing wins
on every cost dimension measured: fewest coherence messages,
shortest whole-workload time, fewest retries, highest accepted-read
fraction.

## 23. Design implications

Two practical implications follow.

First, designs built on direct coherent sharing, which is the
default for most monitor channels on current SoCs, should use a
generation-counter double buffer. The engineering cost is
comparable to that of a sequence lock, and the double buffer is
cheaper on every axis measured in this project. A binary
which-slot-is-current flag should not be used, because the flag
has the double-lap failure mode demonstrated earlier. A monotonic
counter does not.

Second, designs that use explicit transfer for isolation reasons,
for example to prevent the monitor from touching the producer's
hot cache line, or to place the monitor on a separate power
domain, still require a record-level handshake on the mirror. The
transfer itself provides isolation, but not correctness.
Furthermore, the reader pays for this isolation in retries,
because the transfer cadence creates additional race windows
beyond those introduced by the writer.

The broader implication is that a monitor channel specification
should state three properties explicitly: the publication unit,
the validity check, and the reader's behavior on overlap. A
specification missing any of these three properties is
underspecified.

## 24. Limitations and next steps

To close, an honest accounting of what this project is and is not.

The evidence is protocol-level, not cycle-accurate. gem5 Ruby
`MESI_Two_Level` provides message counts and directory traffic,
which is sufficient to observe the correctness and cost effects
reported in the results. It is not a model of any specific
commercial interconnect such as Arm CHI, Intel UPI, or the
AXI4-ACE family.

The timing metric is whole-workload simulated time, defined as the
gem5 simulated clock from start to finish of the 5000-publication
benchmark. That metric is a throughput proxy, not a
per-publication latency distribution. This is the most important
caveat of the study, and the presentation has flagged it
repeatedly.

The DMA cadence is fixed at 1000 nanoseconds, and the coherence
protocol is fixed at `MESI_Two_Level`. Sweeping the DMA cadence is
future work. Alternative coherence protocols such as MOESI or
directory-based variants will shift the absolute numbers, although
the ranking of designs is expected to remain robust.

The repository and the written report are linked on this slide.
Thank you. Questions are welcome.

## 25. Questions

Thank you. Questions are welcome.
