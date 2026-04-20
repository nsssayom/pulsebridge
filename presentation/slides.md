<!-- .slide: class="title-slide" -->

<p class="kicker">Advanced Computer Architecture &middot; Spring 2026</p>

# Coherent Publication Channels for CPS Monitoring

<p class="subtitle">Correct and efficient publication of multi-field control records over coherent memory.</p>

<div class="rule"></div>

<p class="author">Nazmus Shakib Sayom</p>

<p class="affiliation">University of Utah &middot; Kahlert School of Computing</p>

<p class="venue">sayomshakib@gmail.com</p>

Note:
Modern cars, drones, industrial robots — safety-critical cyber-physical systems — are now built on multicore chips that pair a fast application CPU with a small supervisory core. That small core has one job: catch the main CPU making a mistake, before the mistake reaches a motor, a brake, or a control surface.

This talk is about how that small core reads the main core's state, and why getting that channel wrong is not a performance issue — it's a correctness failure.

I'll build every concept from the ground up. If CPS monitoring, cache coherence, or sequence locks are new to you, we'll get there together. The whole arc is six acts, about twenty minutes.

---

## The safety island pattern

<div class="grid-2">
  <div class="col">
    <h3>What it is</h3>
    <p>A small supervisory core on the same SoC as the main
    controller. It runs its own software stack. Its one job: detect
    unsafe controller output before it reaches the actuator.</p>
  </div>
  <div class="col">
    <h3>Where it appears</h3>
    <ul>
      <li>Arm Automotive Enhanced safety island</li>
      <li>NVIDIA DRIVE functional-safety island</li>
      <li>ISO&nbsp;26262 ASIL-D architectures</li>
      <li>Aerospace and industrial control SoCs</li>
    </ul>
  </div>
</div>

<div class="callout">
The question is narrower and more concrete:
<strong>how should the main controller hand its state over to the
safety island?</strong>
</div>

Note:
Let's start with the term itself. A safety island is a small supervisory core that lives on the same SoC as the main application complex. It runs its own software stack — sometimes a different RTOS, sometimes a different ISA level — and its job is not to do the control work. Its job is to watch the controller and catch it making a mistake before the output reaches an actuator.

This pattern is now standard in automotive silicon. Arm sells an Automotive Enhanced safety island product line. NVIDIA's DRIVE platform has a functional-safety island. ISO 26262, the automotive functional-safety standard, effectively requires this kind of partitioning at the top ASIL levels. You see the same shape in aerospace and industrial control SoCs.

The narrow question we're asking today is: how should the big controller hand its state to the small monitor? That's a computer-architecture question about a communication channel.

---

## What the monitor actually reads

<div class="record-layout">
  <div class="field" style="flex: 2;"><div class="name">epoch</div><div class="bytes">8 B</div></div>
  <div class="field" style="flex: 2;"><div class="name">ts_ns</div><div class="bytes">8 B</div></div>
  <div class="field" style="flex: 1;"><div class="name">duty_a</div><div class="bytes">4 B</div></div>
  <div class="field" style="flex: 1;"><div class="name">duty_b</div><div class="bytes">4 B</div></div>
  <div class="field" style="flex: 1;"><div class="name">duty_c</div><div class="bytes">4 B</div></div>
  <div class="field meta-detail" style="flex: 1;"><div class="name">config_id</div><div class="bytes">4 B<br>dup low-16 of epoch</div></div>
  <div class="field" style="flex: 2;"><div class="name">mac</div><div class="bytes">8 B</div></div>
  <div class="field" style="flex: 6;"><div class="name">reserved</div><div class="bytes">24 B</div></div>
</div>

<p class="record-caption">64 bytes total &middot; cache-line aligned</p>

<ul style="font-size: 18px;">
  <li><code>epoch</code> &middot; which publication this is</li>
  <li><code>ts_ns</code> &middot; producer timestamp</li>
  <li><code>duty_a / b / c</code> &middot; three-phase PWM actuation values</li>
  <li><code>config_id</code> &middot; carries a <strong>redundant low-16 of epoch</strong> — our torn-read detector</li>
</ul>

Note:
The monitor doesn't read a single scalar. It reads a record.

In this study the record is 64 bytes — one cache line, aligned. It carries an epoch, meaning "which publication is this"; a nanosecond timestamp; three duty values for a three-phase PWM output (think of a motor controller); and some metadata.

There's one specific piece of metadata I'd like you to hold onto. The `config_id` field carries a redundant 16-bit copy of the low half of the epoch. That redundant copy is our torn-read detector. If the primary epoch and the redundant copy disagree, we know the reader saw parts of two different publications interleaved into one logical read. We'll use this in a few slides.

---

<!-- .slide: class="hero" -->

<p class="kicker">The strawman</p>

<p class="headline">We have cache coherence.<br>Problem solved, right?</p>

<p class="answer-no fragment">No.</p>

Note:
Before we go any further, let me name the naive answer out loud, because it's where most people's intuition lands.

Modern multicore CPUs have cache coherence. Different cores see a consistent view of shared memory. So the strawman says: put the record in shared memory, let the coherence protocol handle it, we're done.

That intuition is wrong. Explaining why takes two slides — but it's the core insight of the paper, so it's worth the time.

---

## Coherence is not consistency

<div class="grid-2">
  <div class="col">
    <h3>Coherence</h3>
    <p>A <strong>per-location</strong> property. All agents agree on the
    order of writes to <em>one</em> address.</p>
    <p style="color: var(--ink-4); font-size: 15px;">
      "Writes to X happen in some global order."
    </p>
  </div>
  <div class="col">
    <h3>Consistency</h3>
    <p>A <strong>cross-location</strong> property. Rules about ordering
    writes across <em>different</em> addresses.</p>
    <p style="color: var(--ink-4); font-size: 15px;">
      "If I write X then Y, does anyone else see them in that order?"
    </p>
  </div>
</div>

<div class="callout warn">
ARMv8 is a <strong>weakly ordered</strong> memory model. Without explicit
release / acquire or a <code>DMB</code> barrier, the hardware and compiler
are free to reorder independent writes. A reader on another core can see
fields in a different order than the writer issued them.
</div>

Note:
These two words get confused constantly, so let me pin them down.

Cache coherence is a *per-location* property. For a single memory address, all cores agree on the order of writes. That's what MESI and MOESI protocols deliver.

Memory consistency is the *cross-address* story. When a core writes address X and then address Y, does a second core necessarily see those writes in that order? On ARMv8 — the architecture we use in gem5 — the answer is: not without a barrier.

ARMv8 is a weak memory model. Unless you put in an explicit release-acquire pair, or a DMB instruction, the hardware and the compiler are free to reorder independent writes. So a writer can store `duty_a`, then `duty_b`, then `duty_c`, and a reader on another core can observe those in a different order, interleaved with an older publication. That's exactly the vulnerability we're about to show.

---

## A torn read, in slow motion

<div class="torn-scope">
  <div class="lane producer">
    <div class="lane-title">Producer<br>core 0</div>
    <div class="track">
      <div class="rail"></div>
      <div class="window" style="left: 50%; right: 2%;"><div class="wlabel">publication k+1 in progress</div></div>
      <div class="evt" style="left: 8%;"><div class="dot"></div><div class="lbl">epoch=k</div></div>
      <div class="evt" style="left: 18%;"><div class="dot"></div><div class="lbl">a=5</div></div>
      <div class="evt" style="left: 28%;"><div class="dot"></div><div class="lbl">b=5</div></div>
      <div class="evt" style="left: 38%;"><div class="dot"></div><div class="lbl">c=5</div></div>
      <div class="evt" style="left: 52%;"><div class="dot"></div><div class="lbl">epoch=k+1</div></div>
      <div class="evt" style="left: 62%;"><div class="dot"></div><div class="lbl">a=6</div></div>
      <div class="evt" style="left: 80%;"><div class="dot"></div><div class="lbl">b=6</div></div>
      <div class="evt" style="left: 94%;"><div class="dot"></div><div class="lbl">c=6</div></div>
    </div>
  </div>

  <div class="lane monitor">
    <div class="lane-title">Monitor<br>core 1</div>
    <div class="track">
      <div class="rail"></div>
      <div class="sample-marker" style="left: 72%;"><span class="pin">reader samples here</span></div>
      <div class="evt" style="left: 72%;"><div class="dot"></div></div>
    </div>
  </div>
</div>

<div class="observation fragment">
  <div class="tag">observed — chimera record, never existed in producer</div>
  <div class="record-layout torn">
    <div class="field pub-new" style="flex: 2;">
      <div class="name">epoch</div>
      <div class="val">k+1</div>
      <div class="src">pub k+1</div>
    </div>
    <div class="field pub-new" style="flex: 1;">
      <div class="name">duty_a</div>
      <div class="val">6</div>
      <div class="src">pub k+1</div>
    </div>
    <div class="field pub-old" style="flex: 1;">
      <div class="name">duty_b</div>
      <div class="val">5</div>
      <div class="src">pub k</div>
    </div>
    <div class="field pub-old" style="flex: 1;">
      <div class="name">duty_c</div>
      <div class="val">5</div>
      <div class="src">pub k</div>
    </div>
    <div class="field detect" style="flex: 1.4;">
      <div class="name">config_id</div>
      <div class="val">k <span class="sub">(low-16)</span></div>
      <div class="src">epoch mismatch &rarr; tear</div>
    </div>
  </div>
</div>

Note:
Let's walk through what goes wrong, step by step.

The producer publishes record *k* — three field writes. Then it starts publishing record *k+1*. It writes the new epoch, writes `duty_a` to 6, and right at that instant the reader on the other core copies the record.

What does the reader see? Epoch equals *k+1*, `duty_a` equals 6 — but `duty_b` and `duty_c` are still 5, because the producer hasn't reached them yet. The reader has just observed a record whose fields come from two different publications interleaved. That state never existed in the producer — the producer was never in a configuration where `duty_a` was 6 and the others were still 5.

This is a torn read. The redundant-epoch detector I asked you to remember catches it: the low 16 bits of epoch in the header will be *k+1*, but the redundant copy in `config_id` — which the writer updates last — will still be *k*. Mismatch, so we flag it.

---

<!-- .slide: class="hero" -->

<p class="kicker">Why this matters</p>

<p class="headline">The policy layer is now reasoning about a state the system was never in.</p>

<p class="subhead">This is not latency jitter. It is a wrong answer.</p>

Note:
I want to be very explicit about why this matters, because the natural reaction is: "so what, the monitor lost one sample, it'll catch the next one."

No. The monitor's whole purpose is to verify that the controller's output is consistent with expected behavior. If the record it's verifying is a chimera — a state that never existed — then the verification is meaningless. It might alarm on a problem that isn't there. More dangerously, it might miss a problem that is.

This is a correctness failure, not a performance issue. That framing matters for the rest of the talk. We don't care about shaving nanoseconds off an incorrect answer.

---

## Two design choices, not one

<div class="matrix">
  <div class="h-col"></div>
  <div class="h-col">No primitive</div>
  <div class="h-col">Sequence lock</div>
  <div class="h-col">Generation<br>double-buffer</div>

  <div class="h-row">Direct coherent sharing</div>
  <div class="cell used">unsync</div>
  <div class="cell used">seqlock</div>
  <div class="cell used">dblbuf</div>

  <div class="h-row">DMA-pulled mirror</div>
  <div class="cell used">dma_naive</div>
  <div class="cell used">dma_seqlock</div>
  <div class="cell skip">not applicable</div>
</div>

<div class="grid-2">
  <div class="col">
    <h3>Transport</h3>
    <p>How does the record move from producer memory to monitor
    memory?</p>
  </div>
  <div class="col">
    <h3>Primitive</h3>
    <p>Does the record carry a discipline that lets the reader detect
    an overlapping writer?</p>
  </div>
</div>

Note:
Two design choices interact in this channel, and most of the value in the paper comes from separating them cleanly.

First is *transport*: how does the record actually move from producer memory to monitor memory? Two options — direct coherent sharing, or an explicit copy through a DMA engine into a mirror page.

Second is the *primitive*: does the record carry a synchronization discipline that lets the reader detect an overlapping writer? Three options — none, sequence lock, or generation double-buffer.

That gives a 2-by-3 grid. We populate five of the six cells. We don't run DMA plus double-buffer, because the DMA engine forces the mirror to be a single active slot — it doesn't generalize to the two-slot double-buffer idea without redesigning the engine.

Five architectures, five shades of the same question.

---

## Transport A &middot; direct coherent sharing

<div class="topology direct">
  <div class="zone">
    <div class="node producer">
      <div class="role">Producer</div>
      <div class="name">core 0</div>
      <div class="detail">application complex</div>
    </div>
  </div>

  <div class="zone">
    <div class="conduit">
      <div class="tag">shared cache line</div>
      <div class="name">witness record</div>
      <div class="sub">64 bytes &middot; coherent</div>
    </div>
    <div class="caption">MESI moves the line between L1 caches on demand</div>
  </div>

  <div class="zone">
    <div class="node monitor">
      <div class="role">Monitor</div>
      <div class="name">core 1</div>
      <div class="detail">safety island</div>
    </div>
  </div>
</div>

<ul style="font-size: 17px; margin-top: 8px;">
  <li>One memory region &middot; no explicit copy</li>
  <li>Producer's write invalidates the monitor's copy</li>
  <li>Monitor re-fetches the line on next read</li>
</ul>

Note:
Direct coherent sharing is the simplest model. The producer writes to a shared record. The monitor reads the same memory. The cache coherence protocol — MESI in our case — moves the line between their L1 caches on demand.

When the producer writes, the monitor's copy is invalidated. When the monitor reads again, it re-fetches the line. One memory region, no explicit copy, no extra hardware.

This is what your intuition probably suggested two slides ago.

---

## Transport B &middot; DMA-pulled mirror

<div class="topology dma">
  <div class="zone">
    <div class="node producer">
      <div class="role">Producer</div>
      <div class="name">core 0</div>
      <div class="detail">writes its own memory</div>
    </div>
    <div class="memtile">
      <div class="mt-label">producer memory</div>
      <div class="mt-value">witness record</div>
    </div>
  </div>

  <div class="zone">
    <div class="engine">
      <div class="tag">pull engine</div>
      <div class="name">WitnessPullEngine</div>
      <div class="cadence">every 1000 ns</div>
      <div class="pulse" aria-hidden="true"></div>
    </div>
    <div class="flow-arrow">copies record</div>
  </div>

  <div class="zone">
    <div class="node monitor">
      <div class="role">Monitor</div>
      <div class="name">core 1</div>
      <div class="detail">reads the mirror</div>
    </div>
    <div class="memtile mirror">
      <div class="mt-label">mirror page</div>
      <div class="mt-value">witness record</div>
    </div>
  </div>
</div>

<p style="text-align: center; font-size: 14px; color: var(--ink-3); margin-top: 8px;">
Mirror page still lives in <strong>coherent memory</strong> — this is not a coherence-disabled baseline.
</p>

Note:
Transport B is explicit transfer. The producer still writes to its own memory. A small DMA engine — in our gem5 setup, a custom SimObject we call `WitnessPullEngine` — periodically copies that record from producer memory into a separate mirror page. The cadence we study is 1000 nanoseconds, once per microsecond. The monitor reads the mirror, not the producer's active line.

One important point: the mirror still lives in coherent memory. This is not a coherence-disabled baseline. What changes is the communication pattern — the monitor is no longer touching the producer's hot line directly.

---

## Primitive A &middot; sequence lock

<div class="lane writer">
  <div class="lane-title">Writer</div>
  <div class="track">
    <div class="rail"></div>
    <div class="window" style="left: 10%; right: 18%;"><div class="wlabel">odd &middot; mid-write</div></div>
    <div class="evt" style="left: 12%;"><div class="dot"></div><div class="lbl">v = odd</div></div>
    <div class="evt" style="left: 30%;"><div class="dot"></div><div class="lbl">a</div></div>
    <div class="evt" style="left: 48%;"><div class="dot"></div><div class="lbl">b</div></div>
    <div class="evt" style="left: 66%;"><div class="dot"></div><div class="lbl">c</div></div>
    <div class="evt" style="left: 82%;"><div class="dot"></div><div class="lbl">v = even</div></div>
  </div>
</div>

<div class="lane reader">
  <div class="lane-title">Reader</div>
  <div class="track">
    <div class="rail"></div>
    <div class="evt" style="left: 12%;"><div class="dot"></div><div class="lbl">v<sub>0</sub> = v</div></div>
    <div class="evt" style="left: 42%;"><div class="dot"></div><div class="lbl">copy a, b, c</div></div>
    <div class="evt" style="left: 78%;"><div class="dot"></div><div class="lbl">v<sub>1</sub> = v</div></div>
  </div>
</div>

<div class="callout">
Reader samples the version <strong>twice</strong>, sandwiching its field
copy. If the two samples differ, or v<sub>0</sub> is odd, the reader
raced with a writer and retries.
</div>

Note:
The first primitive is a sequence lock, or seqlock. It adds one word to the record: a version counter, with a simple convention — odd means a writer is mid-update, even means the record is stable and readable.

The writer does four things: bump the version to odd, write the fields, bump the version to even.

The reader samples the version, checks it's even, copies the fields, samples the version again. If the two samples don't match, or the first sample was odd, the reader knows it raced with a writer and retries.

Lock-free on the reader side. Wait-free on the writer side. This is a textbook technique — Lamport described it in the 1970s, and Linux uses it today in its timekeeping code.

---

## Primitive B &middot; generation-counter double buffer

<div class="slot-deck">
  <div class="slot published">
    <div class="idx">slot[0]</div>
    <div class="payload">epoch = k<br>a, b, c</div>
    <div class="state">published</div>
  </div>
  <div class="slot inflight">
    <div class="idx">slot[1]</div>
    <div class="payload">epoch = k+1<br>writing…</div>
    <div class="state">in-flight</div>
  </div>
  <div class="gen-card">
    <div class="tag">published_gen</div>
    <div class="value">k</div>
    <div class="note">monotonic &middot; release-stored after slot fill</div>
  </div>
</div>

<div class="procedure">
  <div class="col writer">
    <h4>Writer</h4>
    <ol>
      <li>fill <strong>slot[(k+1) mod 2]</strong></li>
      <li>release-store <strong>gen = k+1</strong></li>
    </ol>
  </div>
  <div class="col reader">
    <h4>Reader</h4>
    <ol>
      <li>g<sub>0</sub> = gen</li>
      <li>copy slot[g<sub>0</sub> mod 2]</li>
      <li>g<sub>1</sub> = gen · accept if g<sub>0</sub> = g<sub>1</sub></li>
    </ol>
  </div>
</div>

<div class="callout warn">
A binary "published-index" <strong>flag</strong> doesn't work: two flips
during one read return the flag to its original value. A monotonic
<strong>counter</strong> catches the double-lap.
</div>

Note:
The second primitive is a generation-counter double buffer. Two slots instead of one.

The writer fills an inactive slot, then release-stores a monotonic generation counter. The reader samples the generation, copies the addressed slot, samples the generation again, and accepts if the two samples match. If the generation advanced by two or more during the copy, the writer lapped the reader, and it retries.

One design point that's easy to miss: a binary "which slot is current" flag does *not* work. If the writer flips the flag twice during a single read — that's the double-lap case — the flag returns to its original value. The reader thinks nothing changed and accepts a torn slot. A monotonic counter catches this, because two laps means the counter went up by two.

This is why we specifically use a counter, not a flag. A small distinction, but load-bearing.

---

## The five architectures

<table>
  <thead>
    <tr>
      <th>Architecture</th>
      <th>Transport</th>
      <th>Primitive</th>
    </tr>
  </thead>
  <tbody>
    <tr><td><code>unsync</code></td><td>Coherent line</td><td>None</td></tr>
    <tr><td><code>seqlock</code></td><td>Coherent line</td><td>Odd-even version</td></tr>
    <tr class="win"><td><code>dblbuf</code></td><td>Coherent slot pair</td><td>Generation counter</td></tr>
    <tr><td><code>dma_naive</code></td><td>DMA-pulled mirror</td><td>None</td></tr>
    <tr><td><code>dma_seqlock</code></td><td>DMA-pulled mirror</td><td>Odd-even version on mirror</td></tr>
  </tbody>
</table>

<div class="callout">
<strong>Factorial attribution.</strong>
&nbsp;<code>unsync</code> → <code>seqlock</code> → <code>dblbuf</code>
holds transport fixed, varies primitive. &nbsp;<code>unsync</code> vs
<code>dma_naive</code> and <code>seqlock</code> vs <code>dma_seqlock</code>
hold primitive fixed, vary transport.
</div>

Note:
Here's the full matrix. Three direct-coherent designs — no primitive, sequence lock, double buffer — and two DMA-mirror designs — no primitive, and sequence lock on the mirror.

The reason this structure matters is that we can attribute any result cleanly to either the primitive or the transport, because we only change one variable at a time.

`unsync` → `seqlock` → `dblbuf` holds transport fixed and isolates the primitive. `unsync` versus `dma_naive` holds primitive fixed at nothing and isolates the transport. `seqlock` versus `dma_seqlock` holds primitive fixed at sequence lock and isolates the transport.

That's the analytical grid we'll use to read every result that follows.

---

<!-- .slide: class="figure-slide" -->

## The testbed

<div class="fig-wrap">
  <img src="figures/witness_evidence_arch_print.svg" alt="Producer core, publication channel, monitor core, evidence stream">
</div>

<ul style="font-size: 16px; columns: 2; column-gap: 40px;">
  <li>gem5 25.1.0 &middot; ARM SE mode &middot; <code>TimingSimpleCPU</code></li>
  <li>Ruby <code>MESI_Two_Level</code> coherence protocol</li>
  <li>Producer + monitor + joiner, 0 / 2 / 4 stressor CPUs</li>
  <li>Custom <code>WitnessPullEngine</code> on Ruby DMA sequencer</li>
  <li><strong>Not</strong> cycle-accurate CHI — protocol-level evidence</li>
</ul>

Note:
We implement all five architectures in C11 as a shared core library, cross-compile for ARM aarch64, and run the benchmark under gem5 in system-emulation mode. The coherence protocol is Ruby `MESI_Two_Level`.

We configure three CPUs for the benchmark itself — producer, monitor, and a joiner that waits for the producer to finish — plus zero, two, or four extra stressor CPUs running disjoint-line cache thrashers to inject hierarchy pressure. For the DMA variants we attach our custom pull engine as a SimObject on Ruby's DMA sequencer.

One honest point up front: this is not a cycle-accurate model of any specific commercial interconnect. It's protocol-level architectural evidence from Ruby's message counts and directory traffic. That's what we claim; we don't claim more.

---

## Matrix and metrics

<div class="grid-2">
  <div class="col">
    <h3>30 cells</h3>
    <ul>
      <li>5 architectures</li>
      <li>× 2 workloads</li>
      <li>× 3 contention levels</li>
      <li>5000 publications per cell</li>
    </ul>
  </div>
  <div class="col">
    <h3>Workloads</h3>
    <ul>
      <li><code>captured/periodic_suppression</code><br>
          real STM32 per-period capture &middot; sparse divergence</li>
      <li><code>synthesized/duty_bias</code><br>
          +15% multiplicative bias &middot; sustained</li>
    </ul>
  </div>
</div>

<h3 style="margin-top: 22px;">Metrics</h3>
<p style="font-size: 15px; margin-top: 4px;">
<span class="pill">Torn-read fraction</span>
<span class="pill">CPU msgs / publish</span>
<span class="pill">DMA msgs / publish</span>
<span class="pill">Retries / run</span>
<span class="pill">Whole-workload sim time</span>
</p>

Note:
Each cell in the matrix runs 5000 publications.

Two workloads. The first is a captured trace from a real STM32 logic-analyzer run — sparse divergence between intended and realized behavior. The second is synthesized: a sustained 15 percent multiplicative bias, designed to make the monitor fire repeatedly.

Three contention levels: zero, two, or four stressor CPUs.

And five primary metrics. Torn-read fraction, measured by the redundant-epoch detector we set up earlier. CPU-side coherence messages per publish, summed from Ruby's L1-to-directory and directory-to-memory counters. DMA messages per publish, which is only nonzero for the DMA architectures. Retries per run, counting how many times the reader rejected a read. And whole-workload simulated time — a throughput-style cost proxy, not a per-publication latency distribution. I'll flag that caveat again at the end.

---

<!-- .slide: class="figure-slide" -->

## Result 1 &middot; correctness

<div class="fig-wrap">
  <img src="figures/rq1_torn_reads.png" alt="Torn-read fraction by protocol and contention level">
</div>

<div class="callout warn">
<code>unsync</code>: <strong>4.26%</strong> torn &middot;
<code>dma_naive</code>: <strong>18.22%</strong> torn.
All three disciplined architectures: <strong>zero</strong> torn reads in
every cell.
</div>

Note:
First metric — and it's the one that decides everything else — torn reads.

The two undisciplined architectures tear in every single measured condition. Averaged across the 30-cell matrix, `unsync` tears on 4.26 percent of read attempts. `dma_naive` tears on 18.22 percent — roughly four times worse than the unsynchronized direct baseline.

All three disciplined architectures — `seqlock`, `dblbuf`, `dma_seqlock` — are flat zero torn reads in every cell.

The striking thing here is `dma_naive`. Adding a DMA engine did not fix correctness. It made it worse, because the reader now races on the mirror side *as well as* the producer side.

Transport alone does not solve this problem. The primitive does. That's the central claim of the paper, and it shows up right here on the first plot.

---

<!-- .slide: class="figure-slide" -->

## Result 2 &middot; CPU coherence traffic

<div class="fig-wrap">
  <img src="figures/rq1_coherence_per_publish.png" alt="CPU-side coherence messages per publish">
</div>

<div class="metric-row" style="grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 14px 0 0 0;">
  <div class="metric win">
    <div class="value">27.6</div>
    <div class="label">dblbuf</div>
    <div class="sub">msgs / publish</div>
  </div>
  <div class="metric">
    <div class="value">37.8</div>
    <div class="label">seqlock</div>
    <div class="sub">msgs / publish</div>
  </div>
  <div class="metric">
    <div class="value">28.9</div>
    <div class="label">dma_seqlock</div>
    <div class="sub">msgs / publish</div>
  </div>
</div>

Note:
Among the three correct designs, they separate on cost. The first cost dimension is CPU-side coherence messages per publish.

`dblbuf` averages 27.6 messages per publish. `seqlock` averages 37.8. `dma_seqlock` averages 28.9 — close to `dblbuf`.

The reason `seqlock` pays more is architectural. `seqlock` keeps both the producer and the monitor on one hot record, so the version validation and the payload copy contend on the same cache line. Every validation pulls the line, every producer update invalidates it.

`dblbuf` moves the producer to an inactive slot, so the monitor's working set and the producer's working set don't overlap during a copy. The monitor only has to fetch the tiny generation word on the hot path.

That's where the 27 percent traffic reduction comes from.

---

<!-- .slide: class="figure-slide" -->

## Result 3 &middot; whole-workload time

<div class="fig-wrap">
  <img src="figures/rq3_roi_duration.png" alt="Whole-workload simulated time">
</div>

<div class="metric-row" style="grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 14px 0 0 0;">
  <div class="metric win">
    <div class="value">0.346<span class="unit">ms</span></div>
    <div class="label">dblbuf</div>
    <div class="sub">fastest in every cell</div>
  </div>
  <div class="metric">
    <div class="value">0.485<span class="unit">ms</span></div>
    <div class="label">seqlock</div>
    <div class="sub">+40%</div>
  </div>
  <div class="metric">
    <div class="value">0.482<span class="unit">ms</span></div>
    <div class="label">dma_seqlock</div>
    <div class="sub">+39%</div>
  </div>
</div>

Note:
The second cost dimension is whole-workload simulated time — how long it takes to retire 5000 publications.

`dblbuf` wins in every cell we measured. Averaged over the full matrix, `dblbuf` takes 0.346 milliseconds. `seqlock` takes 0.485. `dma_seqlock` takes 0.482.

If you divide by 5000 publications, that's roughly 69 nanoseconds per publish for `dblbuf` — I give that as a ballpark anchor, not as a latency distribution. `dblbuf` comes in 29 percent faster than `seqlock` and 28 percent faster than `dma_seqlock`, and it's the fastest correct design in all 15 captured-workload cells.

---

## Result 4 &middot; the retry cliff

<div class="metric-row">
  <div class="metric win">
    <div class="value">0.7</div>
    <div class="label">dblbuf</div>
    <div class="sub">retries / run</div>
  </div>
  <div class="metric">
    <div class="value">1,543</div>
    <div class="label">seqlock</div>
    <div class="sub">retries / run</div>
  </div>
  <div class="metric lose">
    <div class="value">14,345</div>
    <div class="label">dma_seqlock</div>
    <div class="sub">retries / run</div>
  </div>
</div>

<p style="text-align: center; font-size: 14px; color: var(--ink-4); margin-top: -6px;">
averaged across the 30-cell matrix &middot; 5000 publications per run
</p>

<div class="callout warn">
A <strong>~20,000× gap</strong> between the best and worst correct
design. Both are equally "correct." They are not equally usable.
</div>

Note:
Third cost dimension, and this is where it gets striking: retries per run.

`dblbuf`: 0.7 retries per 5000-publication run. Essentially never retries. `seqlock`: 1,543 retries per run. `dma_seqlock`: 14,345 retries per run.

That's more than nine times `seqlock`, and roughly 20,000 times `dblbuf`. Let that number land for a second.

Both `dblbuf` and `dma_seqlock` are "correct" by the torn-read metric — neither one ever returns a torn record. But on the work the reader has to do to *maintain* that correctness, they're separated by four orders of magnitude.

Correctness is binary. Cost is not.

---

## Result 5 &middot; the accepted-read cliff

<div class="metric-row">
  <div class="metric win">
    <div class="value">99.95%</div>
    <div class="label">dblbuf</div>
    <div class="sub">reads accepted</div>
  </div>
  <div class="metric">
    <div class="value">97.85%</div>
    <div class="label">seqlock</div>
    <div class="sub">reads accepted</div>
  </div>
  <div class="metric lose">
    <div class="value">8.03%</div>
    <div class="label">dma_seqlock</div>
    <div class="sub">reads accepted</div>
  </div>
</div>

<div class="callout">
The DMA mirror refreshes on <strong>its own cadence</strong>, regardless
of reader progress. Every refresh is another chance to observe an
in-progress mirror update — and retry.
</div>

<p style="text-align: center; font-size: 15px; color: var(--ink-3); margin-top: 2px;">
On a CPU-budget-constrained supervisory core, that matters.
</p>

Note:
The flip side of retries is accepted reads. What fraction of read attempts actually return data?

`dblbuf`: 99.95 percent. `seqlock`: 97.85 percent. `dma_seqlock`: 8.03 percent — twelve times worse than either direct-sharing design.

Why? Architectural. The DMA mirror is refreshed on its own cadence — every 1000 nanoseconds in our configuration — regardless of whether the reader is in the middle of a copy. Every refresh creates another race window.

In `dblbuf`, the reader only races during the writer's actual publish event, and the publish event is just a single generation-counter store — a very short window. In `dma_seqlock`, the reader effectively races continuously.

If your monitor has a CPU budget — and on a small supervisory core, it absolutely does — then an 8 percent accept rate means the monitor is spending 92 percent of its time retrying instead of doing monitor work. That's operationally expensive, even when it's logically correct.

---

## Workload and contention

<div class="grid-2">
  <div class="col">
    <h3>Workload shape</h3>
    <p style="font-size: 17px;">Captured &rarr; synthesized (sustained bias):</p>
    <ul style="font-size: 16px;">
      <li><code>dblbuf</code> &middot; <strong>+37%</strong> CPU traffic</li>
      <li><code>seqlock</code> &middot; <strong>+36%</strong> CPU traffic</li>
      <li><code>dma_seqlock</code> &middot; <strong>&lt;1%</strong> (flat)</li>
    </ul>
  </div>
  <div class="col">
    <h3>Contention &middot; 0 &rarr; 4 stressors</h3>
    <p style="font-size: 17px;">All architectures grow. <strong>Ordering does not change.</strong></p>
    <ul style="font-size: 16px;">
      <li>3 disciplined architectures &middot; zero-torn in every cell</li>
      <li>2 undisciplined architectures &middot; tear in every cell</li>
      <li><code>dblbuf</code> &middot; fastest in every cell</li>
    </ul>
  </div>
</div>

<div class="callout">
Absolute cost moves with workload and contention.
<strong>The ranking among correct designs does not.</strong>
</div>

Note:
Two sensitivity axes worth showing.

First, workload shape. Moving from the captured workload to the sustained-bias workload increases CPU-side traffic by 37 percent for `dblbuf` and 36 percent for `seqlock`. The synchronized DMA mirror stays essentially flat — less than one percent change. That's architecturally consistent: the DMA design keeps the monitor interacting with the mirror, not the producer's hot line, so producer-side activity matters less.

Second, contention. Going from zero to four stressor CPUs raises traffic for every architecture. But the ordering is stable. The disciplined architectures remain zero-torn in every single cell. The undisciplined architectures tear in every single cell. And `dblbuf` is the fastest correct design in every single cell.

Workload and contention change the absolute numbers. They don't change who wins.

---

<!-- .slide: class="hero" -->

<p class="kicker">The headline</p>

<p class="headline">Coherence is the substrate,<br>not the publication contract.</p>

<p class="subhead">A coherent fabric moves the latest line. It cannot tell the reader whether the fields on that line belong to one logical publication.</p>

Note:
That's the whole paper in one sentence.

A coherent fabric can move the latest cache line quickly. It cannot tell the reader whether several fields on that line belong to one logical publication. That's the contract the publication primitive has to supply.

And in the five architectures we studied, the choice of primitive dominates the choice of transport. Explicit DMA transfer does not fix correctness on its own. Sequence lock and double buffer both fix correctness on either transport. And among the correct combinations, generation-counter double buffer over direct coherent sharing wins on every cost dimension we measured.

---

## Design implications

<div class="callout">
<strong>Direct coherent sharing?</strong> Use a <strong>generation-counter
double buffer</strong>. Not a sequence lock. Not a binary
published-index flag.
</div>

<div class="callout">
<strong>Explicit transfer for isolation?</strong> The mirror still needs
a <strong>record-level handshake</strong>. Transport alone does not buy
correctness — and the reader will pay in retries.
</div>

<div class="callout">
<strong>Specify three things</strong> about every monitor channel:
the publication unit, the validity check, and the reader's behavior on
overlap.
</div>

Note:
Two practical takeaways.

One — if your design uses direct coherent sharing, and this is the default for most monitor channels on a modern SoC, use a generation-counter double buffer. It's the same engineering effort as a sequence lock, and in our matrix it's cheaper on every axis. Do *not* use a binary "published-index" flag — it has the double-lap failure mode we showed earlier.

Two — if your design prefers explicit transfer for isolation reasons (maybe you want the monitor not to touch the producer's hot cache line, or you want a separate power domain) then you still need a record-level handshake on the mirror side. The transfer itself does not buy correctness. And be aware that the reader will pay in retries, because the transfer cadence creates additional race windows.

The meta-lesson is that monitor channels should be specified around three things: the publication unit, the validity check, and the reader's behavior on overlap. If those three aren't in your spec, you have an underspecified channel.

---

## Limitations and next steps

<ul style="font-size: 17px;">
  <li><strong>Protocol-level, not cycle-accurate.</strong> Ruby
  <code>MESI_Two_Level</code> gives message counts and ordering evidence
  — not a specific commercial interconnect (CHI, UPI, AXI4-ACE).</li>
  <li><strong>Throughput proxy, not latency distribution.</strong>
  Whole-workload simulated time is a cost proxy over 5000 publications.
  Per-publication latency instrumentation is the natural next step.</li>
  <li><strong>One DMA cadence.</strong> We fix 1000 ns for the pull
  engine. Sweeping cadence is future work.</li>
  <li><strong>One coherence protocol.</strong> <code>MESI_Two_Level</code>
  only. MOESI or directory-based variants may shift absolute numbers.</li>
</ul>

<p style="font-size: 13px; color: var(--ink-4); margin-top: 18px; letter-spacing: 0.02em;">
Repo &amp; paper:
<code>github.com/nsssayom/adv.comp.arc.project-proposal</code>
</p>

Note:
I want to end with an honest accounting of what this paper is and isn't.

The evidence is protocol-level, not cycle-accurate. gem5 Ruby `MESI_Two_Level` gives us message counts and directory traffic, which is enough to see the correctness and cost effects we care about — but it's not a model of any specific commercial interconnect like Arm CHI or Intel UPI.

The timing metric is whole-workload simulated time, a throughput proxy — not a per-publication latency distribution. That's the most important caveat, and I've tried to flag it consistently.

We study one DMA cadence, 1000 nanoseconds. Sweeping cadence is future work. And we study one coherence protocol, `MESI_Two_Level`. MOESI or directory-based variants will shift the absolute numbers, though I'd expect the ranking to be fairly robust.

Repo and paper are linked on the slide. Thank you — happy to take questions.

---

<!-- .slide: class="title-slide" -->

<p class="kicker">Thank you</p>

# Questions?

<p class="subtitle">Coherent publication channels for CPS monitoring.</p>

<div class="rule"></div>

<p class="author">Nazmus Shakib Sayom</p>

<p class="affiliation">sayomshakib@gmail.com</p>

<p class="venue">github.com/nsssayom/adv.comp.arc.project-proposal</p>

Note:
Thank you. Happy to take questions.
