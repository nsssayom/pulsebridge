# Narration script

Full verbatim speaker script for the reveal.js deck. Each section
heading matches a slide title; the body is what the speaker reads.
The same text is embedded in `slides.md` as `Note:` blocks so it
appears in reveal.js's speaker view (press `S`).

Target duration: 18–20 minutes at a natural speaking pace. Every
concept is demystified the first time it's introduced — the audience
is assumed to know general computer architecture, not CPS monitoring,
STL, sequence locks, or DMA engines.

---

## 1. Title — Coherent Publication Channels for CPS Monitoring

Modern cars, drones, industrial robots — safety-critical
cyber-physical systems — are now built on multicore chips that pair a
fast application CPU with a small supervisory core. That small core
has one job: catch the main CPU making a mistake, before the mistake
reaches a motor, a brake, or a control surface.

This talk is about how that small core reads the main core's state,
and why getting that channel wrong is not a performance issue — it's
a correctness failure.

I'll build every concept from the ground up. If CPS monitoring, cache
coherence, or sequence locks are new to you, we'll get there
together. The whole arc is six acts, about twenty minutes.

## 2. The safety island pattern

Let's start with the term itself. A safety island is a small
supervisory core that lives on the same SoC as the main application
complex. It runs its own software stack — sometimes a different RTOS,
sometimes a different ISA level — and its job is not to do the
control work. Its job is to watch the controller and catch it making
a mistake before the output reaches an actuator.

This pattern is now standard in automotive silicon. Arm sells an
Automotive Enhanced safety island product line. NVIDIA's DRIVE
platform has a functional-safety island. ISO 26262, the automotive
functional-safety standard, effectively requires this kind of
partitioning at the top ASIL levels. You see the same shape in
aerospace and industrial control SoCs.

The narrow question we're asking today is: how should the big
controller hand its state to the small monitor? That's a
computer-architecture question about a communication channel.

## 3. What the monitor actually reads

The monitor doesn't read a single scalar. It reads a record.

In this study the record is 64 bytes — one cache line, aligned. It
carries an epoch, meaning "which publication is this"; a nanosecond
timestamp; three duty values for a three-phase PWM output (think of a
motor controller); and some metadata.

There's one specific piece of metadata I'd like you to hold onto. The
`config_id` field carries a redundant 16-bit copy of the low half of
the epoch. That redundant copy is our torn-read detector. If the
primary epoch and the redundant copy disagree, we know the reader saw
parts of two different publications interleaved into one logical
read. We'll use this in a few slides.

## 4. The strawman — we have cache coherence

Before we go any further, let me name the naive answer out loud,
because it's where most people's intuition lands.

Modern multicore CPUs have cache coherence. Different cores see a
consistent view of shared memory. So the strawman says: put the
record in shared memory, let the coherence protocol handle it, we're
done.

That intuition is wrong. Explaining why takes two slides — but it's
the core insight of the paper, so it's worth the time.

## 5. Coherence is not consistency

These two words get confused constantly, so let me pin them down.

Cache coherence is a *per-location* property. For a single memory
address, all cores agree on the order of writes. That's what MESI and
MOESI protocols deliver.

Memory consistency is the *cross-address* story. When a core writes
address X and then address Y, does a second core necessarily see
those writes in that order? On ARMv8 — the architecture we use in
gem5 — the answer is: not without a barrier.

ARMv8 is a weak memory model. Unless you put in an explicit
release-acquire pair, or a DMB instruction, the hardware and the
compiler are free to reorder independent writes. So a writer can
store `duty_a`, then `duty_b`, then `duty_c`, and a reader on another
core can observe those in a different order, interleaved with an
older publication. That's exactly the vulnerability we're about to
show.

## 6. A torn read, in slow motion

Let's walk through what goes wrong, step by step.

The producer publishes record *k* — three field writes. Then it
starts publishing record *k+1*. It writes the new epoch, writes
`duty_a` to 6, and right at that instant the reader on the other core
copies the record.

What does the reader see? Epoch equals *k+1*, `duty_a` equals 6 — but
`duty_b` and `duty_c` are still 5, because the producer hasn't
reached them yet. The reader has just observed a record whose fields
come from two different publications interleaved. That state never
existed in the producer — the producer was never in a configuration
where `duty_a` was 6 and the others were still 5.

This is a torn read. The redundant-epoch detector I asked you to
remember catches it: the low 16 bits of epoch in the header will be
*k+1*, but the redundant copy in `config_id` — which the writer
updates last — will still be *k*. Mismatch, so we flag it.

## 7. Why torn reads are a correctness failure

I want to be very explicit about why this matters, because the
natural reaction is: "so what, the monitor lost one sample, it'll
catch the next one."

No. The monitor's whole purpose is to verify that the controller's
output is consistent with expected behavior. If the record it's
verifying is a chimera — a state that never existed — then the
verification is meaningless. It might alarm on a problem that isn't
there. More dangerously, it might miss a problem that is.

This is a correctness failure, not a performance issue. That framing
matters for the rest of the talk. We don't care about shaving
nanoseconds off an incorrect answer.

## 8. Two design choices, not one

Two design choices interact in this channel, and most of the value in
the paper comes from separating them cleanly.

First is *transport*: how does the record actually move from producer
memory to monitor memory? Two options — direct coherent sharing, or
an explicit copy through a DMA engine into a mirror page.

Second is the *primitive*: does the record carry a synchronization
discipline that lets the reader detect an overlapping writer? Three
options — none, sequence lock, or generation double-buffer.

That gives a 2-by-3 grid. We populate five of the six cells. We don't
run DMA plus double-buffer, because the DMA engine forces the mirror
to be a single active slot — it doesn't generalize to the two-slot
double-buffer idea without redesigning the engine.

Five architectures, five shades of the same question.

## 9. Transport A: direct coherent sharing

Direct coherent sharing is the simplest model. The producer writes to
a shared record. The monitor reads the same memory. The cache
coherence protocol — MESI in our case — moves the line between their
L1 caches on demand.

When the producer writes, the monitor's copy is invalidated. When the
monitor reads again, it re-fetches the line. One memory region, no
explicit copy, no extra hardware.

This is what your intuition probably suggested two slides ago.

## 10. Transport B: DMA-pulled mirror

Transport B is explicit transfer. The producer still writes to its
own memory. A small DMA engine — in our gem5 setup, a custom
SimObject we call `WitnessPullEngine` — periodically copies that
record from producer memory into a separate mirror page. The cadence
we study is 1000 nanoseconds, once per microsecond. The monitor reads
the mirror, not the producer's active line.

One important point: the mirror still lives in coherent memory. This
is not a coherence-disabled baseline. What changes is the
communication pattern — the monitor is no longer touching the
producer's hot line directly.

## 11. Primitive A: sequence lock

The first primitive is a sequence lock, or seqlock. It adds one word
to the record: a version counter, with a simple convention — odd
means a writer is mid-update, even means the record is stable and
readable.

The writer does four things: bump the version to odd, write the
fields, bump the version to even.

The reader samples the version, checks it's even, copies the fields,
samples the version again. If the two samples don't match, or the
first sample was odd, the reader knows it raced with a writer and
retries.

Lock-free on the reader side. Wait-free on the writer side. This is a
textbook technique — Lamport described it in the 1970s, and Linux
uses it today in its timekeeping code.

## 12. Primitive B: generation-counter double buffer

The second primitive is a generation-counter double buffer. Two slots
instead of one.

The writer fills an inactive slot, then release-stores a monotonic
generation counter. The reader samples the generation, copies the
addressed slot, samples the generation again, and accepts if the two
samples match. If the generation advanced by two or more during the
copy, the writer lapped the reader, and it retries.

One design point that's easy to miss: a binary "which slot is
current" flag does *not* work. If the writer flips the flag twice
during a single read — that's the double-lap case — the flag returns
to its original value. The reader thinks nothing changed and accepts
a torn slot. A monotonic counter catches this, because two laps means
the counter went up by two.

This is why we specifically use a counter, not a flag. A small
distinction, but load-bearing.

## 13. The five architectures

Here's the full matrix. Three direct-coherent designs — no primitive,
sequence lock, double buffer — and two DMA-mirror designs — no
primitive, and sequence lock on the mirror.

The reason this structure matters is that we can attribute any result
cleanly to either the primitive or the transport, because we only
change one variable at a time.

`unsync` → `seqlock` → `dblbuf` holds transport fixed and isolates
the primitive. `unsync` versus `dma_naive` holds primitive fixed at
nothing and isolates the transport. `seqlock` versus `dma_seqlock`
holds primitive fixed at sequence lock and isolates the transport.

That's the analytical grid we'll use to read every result that
follows.

## 14. The testbed

We implement all five architectures in C11 as a shared core library,
cross-compile for ARM aarch64, and run the benchmark under gem5 in
system-emulation mode. The coherence protocol is Ruby
`MESI_Two_Level`.

We configure three CPUs for the benchmark itself — producer, monitor,
and a joiner that waits for the producer to finish — plus zero, two,
or four extra stressor CPUs running disjoint-line cache thrashers to
inject hierarchy pressure. For the DMA variants we attach our custom
pull engine as a SimObject on Ruby's DMA sequencer.

One honest point up front: this is not a cycle-accurate model of any
specific commercial interconnect. It's protocol-level architectural
evidence from Ruby's message counts and directory traffic. That's
what we claim; we don't claim more.

## 15. Matrix and metrics

Each cell in the matrix runs 5000 publications.

Two workloads. The first is a captured trace from a real STM32
logic-analyzer run — sparse divergence between intended and realized
behavior. The second is synthesized: a sustained 15 percent
multiplicative bias, designed to make the monitor fire repeatedly.

Three contention levels: zero, two, or four stressor CPUs.

And five primary metrics. Torn-read fraction, measured by the
redundant-epoch detector we set up earlier. CPU-side coherence
messages per publish, summed from Ruby's L1-to-directory and
directory-to-memory counters. DMA messages per publish, which is only
nonzero for the DMA architectures. Retries per run, counting how many
times the reader rejected a read. And whole-workload simulated time —
a throughput-style cost proxy, not a per-publication latency
distribution. I'll flag that caveat again at the end.

## 16. Result 1 — correctness

First metric — and it's the one that decides everything else — torn
reads.

The two undisciplined architectures tear in every single measured
condition. Averaged across the 30-cell matrix, `unsync` tears on
4.26 percent of read attempts. `dma_naive` tears on 18.22 percent —
roughly four times worse than the unsynchronized direct baseline.

All three disciplined architectures — `seqlock`, `dblbuf`,
`dma_seqlock` — are flat zero torn reads in every cell.

The striking thing here is `dma_naive`. Adding a DMA engine did not
fix correctness. It made it worse, because the reader now races on
the mirror side *as well as* the producer side.

Transport alone does not solve this problem. The primitive does.
That's the central claim of the paper, and it shows up right here on
the first plot.

## 17. Result 2 — CPU-side coherence traffic

Among the three correct designs, they separate on cost. The first
cost dimension is CPU-side coherence messages per publish.

`dblbuf` averages 27.6 messages per publish. `seqlock` averages 37.8.
`dma_seqlock` averages 28.9 — close to `dblbuf`.

The reason `seqlock` pays more is architectural. `seqlock` keeps both
the producer and the monitor on one hot record, so the version
validation and the payload copy contend on the same cache line. Every
validation pulls the line, every producer update invalidates it.

`dblbuf` moves the producer to an inactive slot, so the monitor's
working set and the producer's working set don't overlap during a
copy. The monitor only has to fetch the tiny generation word on the
hot path.

That's where the 27 percent traffic reduction comes from.

## 18. Result 3 — whole-workload simulated time

The second cost dimension is whole-workload simulated time — how long
it takes to retire 5000 publications.

`dblbuf` wins in every cell we measured. Averaged over the full
matrix, `dblbuf` takes 0.346 milliseconds. `seqlock` takes 0.485.
`dma_seqlock` takes 0.482.

If you divide by 5000 publications, that's roughly 69 nanoseconds per
publish for `dblbuf` — I give that as a ballpark anchor, not as a
latency distribution. `dblbuf` comes in 29 percent faster than
`seqlock` and 28 percent faster than `dma_seqlock`, and it's the
fastest correct design in all 15 captured-workload cells.

## 19. Result 4 — the retry cliff

Third cost dimension, and this is where it gets striking: retries per
run.

`dblbuf`: 0.7 retries per 5000-publication run. Essentially never
retries. `seqlock`: 1,543 retries per run. `dma_seqlock`:
14,345 retries per run.

That's more than nine times `seqlock`, and roughly 20,000 times
`dblbuf`. Let that number land for a second.

Both `dblbuf` and `dma_seqlock` are "correct" by the torn-read metric
— neither one ever returns a torn record. But on the work the reader
has to do to *maintain* that correctness, they're separated by four
orders of magnitude.

Correctness is binary. Cost is not.

## 20. Result 5 — the accepted-read cliff

The flip side of retries is accepted reads. What fraction of read
attempts actually return data?

`dblbuf`: 99.95 percent. `seqlock`: 97.85 percent. `dma_seqlock`:
8.03 percent — twelve times worse than either direct-sharing design.

Why? Architectural. The DMA mirror is refreshed on its own cadence —
every 1000 nanoseconds in our configuration — regardless of whether
the reader is in the middle of a copy. Every refresh creates another
race window.

In `dblbuf`, the reader only races during the writer's actual publish
event, and the publish event is just a single generation-counter
store — a very short window. In `dma_seqlock`, the reader effectively
races continuously.

If your monitor has a CPU budget — and on a small supervisory core,
it absolutely does — then an 8 percent accept rate means the monitor
is spending 92 percent of its time retrying instead of doing monitor
work. That's operationally expensive, even when it's logically
correct.

## 21. Workload and contention

Two sensitivity axes worth showing.

First, workload shape. Moving from the captured workload to the
sustained-bias workload increases CPU-side traffic by 37 percent for
`dblbuf` and 36 percent for `seqlock`. The synchronized DMA mirror
stays essentially flat — less than one percent change. That's
architecturally consistent: the DMA design keeps the monitor
interacting with the mirror, not the producer's hot line, so
producer-side activity matters less.

Second, contention. Going from zero to four stressor CPUs raises
traffic for every architecture. But the ordering is stable. The
disciplined architectures remain zero-torn in every single cell. The
undisciplined architectures tear in every single cell. And `dblbuf`
is the fastest correct design in every single cell.

Workload and contention change the absolute numbers. They don't
change who wins.

## 22. The headline

That's the whole paper in one sentence.

A coherent fabric can move the latest cache line quickly. It cannot
tell the reader whether several fields on that line belong to one
logical publication. That's the contract the publication primitive
has to supply.

And in the five architectures we studied, the choice of primitive
dominates the choice of transport. Explicit DMA transfer does not fix
correctness on its own. Sequence lock and double buffer both fix
correctness on either transport. And among the correct combinations,
generation-counter double buffer over direct coherent sharing wins on
every cost dimension we measured.

## 23. Design implications

Two practical takeaways.

One — if your design uses direct coherent sharing, and this is the
default for most monitor channels on a modern SoC, use a
generation-counter double buffer. It's the same engineering effort as
a sequence lock, and in our matrix it's cheaper on every axis. Do
*not* use a binary "published-index" flag — it has the double-lap
failure mode we showed earlier.

Two — if your design prefers explicit transfer for isolation reasons
(maybe you want the monitor not to touch the producer's hot cache
line, or you want a separate power domain) then you still need a
record-level handshake on the mirror side. The transfer itself does
not buy correctness. And be aware that the reader will pay in
retries, because the transfer cadence creates additional race
windows.

The meta-lesson is that monitor channels should be specified around
three things: the publication unit, the validity check, and the
reader's behavior on overlap. If those three aren't in your spec, you
have an underspecified channel.

## 24. Limitations and next steps

I want to end with an honest accounting of what this paper is and
isn't.

The evidence is protocol-level, not cycle-accurate. gem5 Ruby
`MESI_Two_Level` gives us message counts and directory traffic, which
is enough to see the correctness and cost effects we care about — but
it's not a model of any specific commercial interconnect like Arm CHI
or Intel UPI.

The timing metric is whole-workload simulated time, a throughput
proxy — not a per-publication latency distribution. That's the most
important caveat, and I've tried to flag it consistently.

We study one DMA cadence, 1000 nanoseconds. Sweeping cadence is
future work. And we study one coherence protocol, `MESI_Two_Level`.
MOESI or directory-based variants will shift the absolute numbers,
though I'd expect the ranking to be fairly robust.

Repo and paper are linked on the slide. Thank you — happy to take
questions.

## 25. Questions

Thank you. Happy to take questions.
