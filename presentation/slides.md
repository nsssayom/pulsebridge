<!-- .slide: class="title-slide" -->

<div class="title-copy">
<p class="kicker">Advanced Computer Architecture, Spring 2026</p>
<h1>Coherent Publication Channels for CPS Monitoring</h1>
<p class="subtitle">Correct and efficient publication of multi-field control records over coherent memory.</p>
<div class="rule"></div>
<p class="author">Nazmus Shakib Sayom</p>
<p class="affiliation">University of Utah, Kahlert School of Computing</p>
<p class="contact">sayom.shakib@utah.edu</p>
</div>

Note:
This presentation describes a project that studies the communication channel between the main controller and the safety-critical monitor on modern multicore systems. The systems in question are safety-critical cyber-physical systems, abbreviated CPS, and include automotive ECUs, drone flight controllers, and industrial robots. Modern CPS platforms pair a fast application CPU with a small supervisory core whose role is to catch the main CPU producing an unsafe output before that output reaches an actuator.

The central question of the project is how the supervisory core should read the main core's state. The finding is that handling the channel incorrectly is not a performance issue. It is a correctness failure.

The presentation introduces each technical concept on first use. The audience is assumed to know general computer architecture; CPS monitoring, cache coherence rules, and synchronization primitives are defined as they appear. The presentation is organized into six sections and runs approximately twenty minutes.

---

## Safety Islands on Multicore SoCs

<div class="grid-2">
  <div class="col">
    <h3>What it is</h3>
    <p>A small supervisory core on the same SoC as the main
    controller. It runs its own software stack. Its one job: to detect
    unsafe controller output before it reaches the actuator.</p>
  </div>
  <div class="col">
    <h3>Where it appears</h3>
    <ul class="arrow-list vendor-list">
      <li><img class="vendor-mark arm" src="web-assets/logos/arm/arm-logo-2025-ink-rgb.svg" alt="Arm"> Arm Automotive Enhanced safety island</li>
      <li><img class="vendor-mark nvidia" src="web-assets/logos/nvidia/nvidia-logo-black.svg" alt="NVIDIA"> NVIDIA DRIVE functional-safety island</li>
      <li>ISO&nbsp;26262 ASIL-D architectures</li>
      <li>Aerospace and industrial control SoCs</li>
    </ul>
  </div>
</div>

<div class="callout">
The question is narrower and more concrete:
<strong>How should the main controller hand its state over to the
safety island?</strong>
</div>

Note:
The first technical term to define is "safety island." A safety island is a small supervisory core located on the same system-on-chip, abbreviated SoC, as the main application complex. It runs an independent software stack, sometimes under a different real-time operating system (RTOS) and sometimes at a different instruction-set architecture level from the main CPU. Its role is not to perform control work. Its role is to observe the controller and detect unsafe output before it reaches the actuator.

The pattern is now standard in automotive silicon. Arm markets an Automotive Enhanced safety island product line. NVIDIA's DRIVE platform includes a functional-safety island. ISO 26262, the international automotive functional-safety standard, effectively requires this partitioning at its top safety grades. Those grades are the Automotive Safety Integrity Levels, or ASIL. ASIL-D is the highest grade and covers systems in which a failure can cause serious injury or death. The same partitioning pattern appears in aerospace and industrial-control SoCs.

Given the pattern, the architectural question the project addresses is narrow: how should the main controller hand its state to the supervisory core?

---

## The Witness Record: Fields and Layout

<div class="record-shell">
  <header class="record-header">
    <div class="record-title">
      <span class="record-title-kicker">cache line</span>
      <span class="record-title-value">64 B</span>
    </div>
    <div class="record-chips">
      <span class="chip outline">cache-line aligned</span>
      <span class="chip outline">1 logical publication</span>
    </div>
  </header>

  <div class="record-map">
    <div class="record-layout">
      <div class="field ident">
        <div class="name">epoch</div>
        <div class="size">8 B</div>
      </div>
      <div class="field time">
        <div class="name">ts_ns</div>
        <div class="size">8 B</div>
      </div>
      <div class="field data">
        <div class="name">duty_a</div>
        <div class="size">4 B</div>
      </div>
      <div class="field data">
        <div class="name">duty_b</div>
        <div class="size">4 B</div>
      </div>
      <div class="field data">
        <div class="name">duty_c</div>
        <div class="size">4 B</div>
      </div>
      <div class="field meta-detail">
        <div class="name">config_id</div>
        <div class="size">4 B</div>
      </div>
      <div class="field neutral">
        <div class="name">mac</div>
        <div class="size">8 B</div>
      </div>
      <div class="field neutral">
        <div class="name">reserved</div>
        <div class="size">24 B</div>
      </div>
    </div>

    <div class="record-ruler">
      <div class="tick first">
        <span class="mark-start">0</span>
        <span class="mark">8</span>
      </div>
      <div class="tick"><span class="mark">16</span></div>
      <div class="tick"><span class="mark">20</span></div>
      <div class="tick"><span class="mark">24</span></div>
      <div class="tick"><span class="mark">28</span></div>
      <div class="tick"><span class="mark">32</span></div>
      <div class="tick"><span class="mark">40</span></div>
      <div class="tick last"><span class="mark-end">64</span></div>
    </div>
  </div>
</div>

<div class="detail-grid">
  <div class="detail-item ident">
    <h3><code>epoch</code></h3>
    <p>Which publication the monitor is looking at.</p>
  </div>
  <div class="detail-item time">
    <h3><code>ts_ns</code></h3>
    <p>Producer timestamp for freshness and ordering.</p>
  </div>
  <div class="detail-item data">
    <h3><code>duty_a / b / c</code></h3>
    <p>Three-phase PWM actuation values that must be interpreted together.</p>
  </div>
  <div class="detail-item warn">
    <h3><code>config_id</code></h3>
    <p>Redundant low-16 of <code>epoch</code> used as the torn-read detector.</p>
  </div>
</div>

Note:
The monitor does not read a single scalar value. It reads a structured record consisting of multiple related fields that must be interpreted together as one logical publication.

In this study the record is 64 bytes, which is the size of one cache line on most modern processors. A cache line is the unit of memory that a CPU cache loads and evicts as an indivisible block. The record is aligned to a cache-line boundary so that it occupies exactly one line.

The record carries five items. First, an epoch, which is a counter that identifies the publication. Second, a nanosecond timestamp. Third, three duty values for a three-phase pulse-width-modulated output. Pulse-width modulation, or PWM, is the standard mechanism by which digital chips drive analog actuators such as a three-phase motor: instead of varying the output voltage, the chip varies the fraction of time the voltage is asserted. Fourth and fifth are metadata fields.

One of the metadata fields is central to the rest of the presentation and is worth introducing here. The `config_id` field carries a redundant 16-bit copy of the low half of the epoch. If the primary epoch and the redundant copy disagree, the reader has observed fragments of two different publications stitched together into one logical read. That redundant copy serves as the torn-read detector used throughout the experimental results.

---

<!-- .slide: class="hero" -->

<p class="kicker">A Tempting Baseline</p>

<p class="headline">Does cache coherence alone suffice?</p>

<p class="answer-no">No.</p>

<p class="subhead">Coherence synchronizes a single address.<br>
It does not order writes across the fields of a record.</p>

Note:
A tempting first answer to the channel question is worth stating explicitly, because it represents the most common initial intuition.

Modern multicore CPUs provide cache coherence. Different cores therefore observe a consistent view of shared memory. The strawman argument follows: place the record in shared memory, let the coherence protocol handle the rest, and the problem is solved.

This intuition is incorrect. The next two slides explain why, because the reasoning is the central technical insight of the project.

---

## Coherence Is Not Consistency

<div class="grid-2">
  <div class="col">
    <h3>Coherence</h3>
    <p>A <strong>per-location</strong> property. All agents agree on the
    order of writes to <em>one</em> address.</p>
    <p class="principle-caption">
      "Writes to X happen in some global order."
    </p>
  </div>
  <div class="col">
    <h3>Consistency</h3>
    <p>A <strong>cross-location</strong> property. Rules about ordering
    writes across <em>different</em> addresses.</p>
    <p class="principle-caption">
      "If I write X then Y, does anyone else see them in that order?"
    </p>
  </div>
</div>

<ul class="consequence">
  <li><strong>ARMv8 is weakly ordered.</strong> Independent writes may commit out of program order.</li>
  <li><strong>No release / acquire, no <code>DMB</code> &rarr; no ordering.</strong> Hardware and compiler are free to reorder.</li>
  <li><strong>Consequence.</strong> A reader on another core can see fields in a different order than the writer issued them.</li>
</ul>

Note:
Cache coherence and memory consistency sound like synonyms, but they describe different properties, and they are routinely confused. Both require explicit definition.

Cache coherence is a property of a single memory location. For one address, all cores must eventually agree on the order of writes to that address. Hardware protocols such as MESI and MOESI provide this guarantee. MESI names the four states a cache line can hold across cores: Modified, Exclusive, Shared, Invalid. MOESI adds an Owned state. Neither protocol constrains ordering between different addresses.

Memory consistency is the property that governs ordering across different addresses. When one core writes address X and then writes address Y, memory consistency determines whether another core necessarily observes the two writes in that same order. On ARMv8, the 64-bit ARM architecture used in the gem5 experiments of this project, the answer is no, unless the program states so explicitly. ARMv8 is classified as a weak memory model. Without a matched release-acquire fence pair, or a data-memory-barrier instruction, called DMB, both the hardware and the compiler are free to reorder writes to independent addresses. As a consequence, the producer may issue stores to `duty_a`, `duty_b`, and `duty_c` in program order, while a reader on another core observes those stores in a different order, interleaved with fields from an older publication.

This reordering is the vulnerability that the next slide illustrates.

---

## Anatomy of a Torn Read

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
  <div class="tag">observed: chimera record, never existed in producer</div>
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
The failure scenario, traced step by step.

The producer completes publication *k* by writing its three duty-value fields. It then begins publication *k+1*. It writes the new epoch. It writes `duty_a` to the new value, 6. At that instant, the reader on a different core copies the record.

The reader observes an epoch of *k+1* and a `duty_a` of 6, because those two fields have just been updated. However, `duty_b` and `duty_c` still hold the previous value, 5, because the producer has not yet reached them. The resulting observation is a record whose fields originate in two different publications. That specific combination never existed inside the producer; the producer was never in a state in which `duty_a` was 6 and the other two duties were still 5.

This observation is a torn read. The redundant-epoch detector catches it. The low 16 bits of the header epoch have advanced to *k+1*, but the redundant copy in `config_id`, which the writer updates last, still reads *k*. The two disagree, and the read is flagged as torn.

---

<!-- .slide: class="hero" -->

<p class="kicker">Correctness Implication</p>

<p class="headline">A torn read is a correctness failure, not a latency event.</p>

<p class="subhead">The monitor evaluates a state that never existed.<br>
The verdict is not stale. It is about the wrong system.</p>

Note:
It is necessary to categorize what a torn read actually is. The natural initial reaction is that the monitor simply missed one sample and will recover on the next one, so the event is tolerable. That framing is incorrect.

The monitor's function is to verify that the controller's output is consistent with expected behavior. If the record under verification is a chimera, that is, a state that never existed inside the controller, then the verification is meaningless. The monitor may alarm on a nonexistent fault. More seriously, it may fail to alarm on a real fault, because the chimera happened to appear benign under the safety specification.

This categorization governs the rest of the analysis. The project does not aim to minimize nanoseconds on an incorrect answer; it aims to minimize nanoseconds on an answer that is correct in the first place.

---

## Two Orthogonal Design Dimensions

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
Two separate design choices interact in this channel, and keeping them distinct is central to the project's analysis.

The first choice is transport: the mechanism by which the record physically moves from producer memory to monitor memory. The project compares two transports. The first is direct coherent sharing, in which both cores read and write the same memory. The second is explicit copy, in which a small hardware engine transfers the record from producer memory into a separate mirror page.

The second choice is the synchronization primitive: whether the record carries a discipline that allows the reader to detect an overlapping writer. The project compares three primitives: no primitive, a sequence lock, and a generation-counter double buffer.

Two transports and three primitives define a 2-by-3 grid. The project populates five of the six cells. The sixth cell, DMA transport combined with a double buffer, is omitted because the DMA engine forces the mirror to be a single active slot and does not generalize to the two-slot design without a redesign of the engine.

The resulting five architectures are the units of comparison for the remainder of the presentation.

---

## Transport A: Direct Coherent Sharing

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
      <div class="sub">64 bytes, coherent</div>
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

<div class="fact-strip">
  <div class="fact">
    <span>Memory layout</span>
    One shared witness record
  </div>
  <div class="fact">
    <span>Producer effect</span>
    Writes invalidate the monitor's copy
  </div>
  <div class="fact">
    <span>Reader cost</span>
    Next read refetches the hot line
  </div>
</div>

Note:
Transport A is direct coherent sharing, the simplest option. The producer writes to a shared record. The monitor reads the same record. The cache coherence protocol, MESI in this setup, moves the cache line between the two cores' L1 caches on demand. The L1 cache is the smallest and fastest level of the cache hierarchy and sits adjacent to each core.

When the producer writes, the monitor's copy of the line is invalidated. When the monitor subsequently reads, it refetches the line. The design uses a single memory region, has no explicit copy step, and requires no additional hardware.

This is the design that the intuition addressed two slides earlier corresponds to.

---

## Transport B: DMA-Pulled Mirror

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

<div class="fact-strip">
  <div class="fact">
    <span>Producer side</span>
    Writes its own private record
  </div>
  <div class="fact">
    <span>Engine cadence</span>
    The mirror refreshes every 1000 ns
  </div>
  <div class="fact">
    <span>Important caveat</span>
    The mirror is still <strong>coherent memory</strong>
  </div>
</div>

Note:
Transport B is an explicit hardware transfer. The producer writes to its own private memory. A small direct-memory-access engine, called a DMA engine, periodically copies the record from producer memory into a separate mirror page, and the monitor reads only from the mirror. DMA is a standard SoC feature that allows an I/O block to move data between memory regions without involving the CPU.

In the gem5 simulation used in this project, the engine is implemented as a custom SimObject, which is gem5's unit of modeled hardware, and is named `WitnessPullEngine`. The configuration used throughout the study copies the record once every 1000 nanoseconds, that is, once per microsecond.

One detail is important. The mirror page still resides in coherent memory. This transport is not a coherence-disabled baseline. The only property that changes is the communication pattern: the monitor no longer touches the producer's hot cache line directly.

---

## Primitive A: Sequence Lock

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
The first synchronization primitive is a sequence lock, usually shortened to seqlock. The seqlock adds one word to the record, a version counter, with a simple convention: an odd version indicates that a writer is mid-update and the record is unstable, while an even version indicates that the record is stable and safe to read.

The writer executes four steps: increment the version to an odd value, write the payload fields, and increment the version to the next even value.

The reader executes four steps as well: sample the version into a local variable, verify that the sample is even, copy all payload fields into a local scratch buffer, and sample the version a second time. If the two samples match and the first was even, the read is valid. If they do not match, or if the first sample was odd, the reader has detected a race with the writer and retries.

The reader never acquires a lock, which makes the design lock-free on the reader side. The writer never waits for readers, which makes it wait-free on the writer side. The seqlock is a textbook technique: Leslie Lamport described it in the 1970s, and the Linux kernel currently uses it to publish timekeeping state.

---

## Primitive B: Generation-Counter Double Buffer

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
    <div class="note">monotonic, release-stored after slot fill</div>
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
The second primitive is a generation-counter double buffer. The record is stored in two slots rather than one, and a generation counter is maintained as a monotonic integer, that is, an integer that only increases.

The writer selects the inactive slot, writes the full record into it, and then release-stores a new generation value. A release-store is a compiler-and-hardware construct that guarantees the slot contents become globally visible before the updated generation value becomes visible.

The reader samples the generation counter, copies the slot whose index corresponds to that generation, samples the counter a second time, and accepts the read if the two samples match. If the counter advanced by two or more between the two samples, the writer lapped the reader inside the buffer, and the reader retries.

One design point is easy to overlook. A binary flag that indicates the current slot is not a correct replacement for the counter. If the writer flips the flag twice during a single read, a case referred to as the double-lap, the flag returns to its original value. The reader perceives no change and accepts a torn slot. A monotonic counter captures the double-lap because two flips produce an increment of two. For this reason, the project specifically uses a counter rather than a flag.

---

## The Five Evaluated Architectures

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

<div class="callout warn">
<strong>Why no DMA + double buffer?</strong>
The pull engine copies one mirror slot, not a two-slot pair. Generation-counter double buffering would require redesigning the engine, so the sixth cell is left out of scope.
</div>

Note:
The complete matrix comprises five architectures. Three use direct coherent sharing: `unsync` uses no primitive, `seqlock` uses a sequence lock, and `dblbuf` uses a generation-counter double buffer. Two use the DMA-pulled mirror: `dma_naive` uses no primitive, and `dma_seqlock` uses a sequence lock on the mirror.

The layout is useful because every pairwise comparison changes exactly one variable. The comparison across `unsync`, `seqlock`, and `dblbuf` holds the transport fixed at direct sharing and isolates the effect of the primitive. The comparison between `unsync` and `dma_naive` holds the primitive fixed at none and isolates the effect of the transport. The comparison between `seqlock` and `dma_seqlock` holds the primitive fixed at sequence lock and isolates the effect of the transport.

This grid is the analytical frame used to interpret every result that follows.

---

## Experimental Testbed

<div class="testbed-split">
  <div class="spec-sheet">
    <div class="spec-row">
      <span class="spec-tag">simulator</span>
      <div class="spec-body">
        <img class="inline-logo gem5" src="web-assets/logos/gem5/gem5-color-long.gif" alt="gem5">
        <span>25.1.0, ARM SE mode, <code>TimingSimpleCPU</code></span>
      </div>
    </div>
    <div class="spec-row">
      <span class="spec-tag">protocol</span>
      <div class="spec-body">Ruby <code>MESI_Two_Level</code>, two-level MESI hierarchy</div>
    </div>
    <div class="spec-row">
      <span class="spec-tag">topology</span>
      <div class="spec-body">Producer + monitor + joiner, with 0 / 2 / 4 stressor CPUs</div>
    </div>
    <div class="spec-row">
      <span class="spec-tag">dma</span>
      <div class="spec-body">Custom <code>WitnessPullEngine</code> on the Ruby DMA sequencer</div>
    </div>
    <div class="spec-row caveat">
      <span class="spec-tag">scope</span>
      <div class="spec-body"><strong>Protocol evidence</strong>, not a cycle-accurate CHI model</div>
    </div>
  </div>
  <div class="figure">
    <div class="fig-wrap">
      <img src="figures/witness_evidence_arch_print.svg" alt="Producer core, publication channel, monitor core, evidence stream">
    </div>
  </div>
</div>

Note:
All five architectures are implemented in C11, which is the 2011 C language standard, as a shared core library. The library is cross-compiled for 64-bit ARM, identified by the target name `aarch64`, and executed under gem5 in system-emulation mode. System-emulation mode is a gem5 configuration that executes a user-mode binary directly, without booting a full operating system.

The coherence protocol is Ruby `MESI_Two_Level`. Ruby is gem5's detailed memory-system model, and `MESI_Two_Level` is its reference implementation of a two-level MESI hierarchy: private L1 caches per core and a shared L2 cache backed by a coherence directory that tracks which cores hold a copy of each line.

The benchmark uses three CPUs: a producer, a monitor, and a joiner that waits for the producer to finish. Between zero and four additional stressor CPUs run concurrently. Each stressor executes a cache thrasher that touches a disjoint block of cache lines, meaning lines that neither the producer nor the monitor touches. The stressors therefore share no memory with the benchmark, but they compete for the shared cache hierarchy and the coherence directory, which introduces controlled hierarchy pressure. For the DMA variants, the custom pull engine is attached as a SimObject on Ruby's DMA sequencer.

One honest qualification up front: this testbed is not a cycle-accurate model of any specific commercial interconnect. It provides protocol-level architectural evidence measured as Ruby message counts and directory traffic. That is the claim the project makes, and no stronger claim is implied.

---

## Experimental Matrix and Metrics

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
    <ul class="arrow-list">
      <li><code>captured/periodic_suppression</code><br>
          Real STM32 per-period capture, sparse divergence</li>
      <li><code>synthesized/duty_bias</code><br>
          Sustained +15% multiplicative bias</li>
    </ul>
  </div>
</div>

<h3 class="metrics-heading">Metrics</h3>
<p class="metric-pill-row">
<span class="pill">Torn-read fraction</span>
<span class="pill">CPU msgs / publish</span>
<span class="pill">DMA msgs / publish</span>
<span class="pill">Retries / run</span>
<span class="pill">Whole-workload sim time</span>
</p>

Note:
Each matrix cell executes 5000 publications.

Two workloads are used. The first is a captured trace from a real STM32 development board. STM32 is a family of ARM Cortex-M microcontrollers widely used in embedded controllers. The board was instrumented with a logic analyzer, which recorded the duty-value stream while the controller ran an algorithm that produces sparse divergence between intended and realized behavior. The second workload is synthesized with a sustained 15 percent multiplicative bias between intended and realized values, which causes the monitor to fire repeatedly rather than sparsely.

Contention is varied across three levels: 0, 2, and 4 stressor CPUs. Five architectures, two workloads, and three contention levels together define the 30-cell experimental matrix.

Each cell contributes five primary metrics. The first is torn-read fraction, measured by the redundant-epoch detector described earlier. The second is CPU-side coherence messages per publish, computed by summing two Ruby traffic counters: L1-to-directory and directory-to-memory. The third is DMA messages per publish, which is nonzero only for the DMA architectures. The fourth is retries per run, which counts reads rejected by the reader and repeated. The fifth is whole-workload simulated time, defined as the gem5 simulated clock from the start to the end of the 5000-publication benchmark. That last metric serves as a throughput-style cost proxy rather than a per-publication latency distribution, and the caveat is revisited in the limitations section.

---

<!-- .slide: class="figure-slide" -->

## Result 1: Correctness (Torn-Read Fraction)

<div class="fig-wrap r-stretch">
  <img src="figures/rq1_torn_reads.png" alt="Torn-read fraction by protocol and contention level">
</div>

<div class="callout warn">
<code>unsync</code>: <strong>4.26%</strong> torn &middot;
<code>dma_naive</code>: <strong>18.22%</strong> torn.
All three disciplined architectures: <strong>zero</strong> torn reads in
every cell.
</div>

Note:
The first metric gates every other result: torn reads.

The two architectures without a primitive tear in every measured condition. Averaged across the 30-cell matrix, `unsync` tears on 4.26 percent of read attempts and `dma_naive` tears on 18.22 percent, which is roughly four times worse than unsynchronized direct sharing. The three architectures with a primitive, namely `seqlock`, `dblbuf`, and `dma_seqlock`, return zero torn reads in every cell.

The `dma_naive` result is particularly significant. The addition of a DMA engine, which isolates the monitor from the producer's hot cache line, did not repair correctness. It degraded correctness, because the reader now races on the mirror side in addition to the producer side.

Transport alone does not solve the tearing problem. The primitive does. This is the central claim of the project, and it appears on the first result plot.

---

<!-- .slide: class="figure-slide" -->

## Result 2: CPU-Side Coherence Traffic

<div class="fig-wrap r-stretch">
  <img src="figures/rq1_coherence_per_publish.png" alt="CPU-side coherence messages per publish">
</div>

<div class="metric-row tight">
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
The three correct designs are now compared on cost. The first cost dimension is CPU-side coherence messages per publish, which measures the channel's traffic on the shared cache hierarchy.

`dblbuf` averages 27.6 messages per publish. `seqlock` averages 37.8. `dma_seqlock` averages 28.9, close to `dblbuf`.

The explanation for `seqlock`'s higher cost is architectural. A seqlock keeps both the producer and the monitor on a single hot record. The version validation and the field copy both contend on the same cache line, so every validation pulls the line and every producer update invalidates it. `dblbuf`, by contrast, moves the producer to the inactive slot, so the monitor's and the producer's working sets do not overlap during a copy. The monitor fetches only the small generation word on the hot path, not the full payload line. The 27 percent reduction in traffic originates here.

---

<!-- .slide: class="figure-slide" -->

## Result 3: Whole-Workload Simulated Time

<div class="fig-wrap r-stretch">
  <img src="figures/rq3_roi_duration.png" alt="Whole-workload simulated time">
</div>

<div class="metric-row tight">
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
The second cost dimension is whole-workload simulated time: the total simulated-clock duration gem5 reports for retiring all 5000 publications.

`dblbuf` wins in every cell of the matrix. Averaged over the full matrix, `dblbuf` takes 0.346 milliseconds. `seqlock` takes 0.485. `dma_seqlock` takes 0.482. Dividing by 5000 publications yields approximately 69 nanoseconds per publish for `dblbuf`. This figure serves as a ballpark anchor rather than a latency distribution. `dblbuf` is 29 percent faster than `seqlock` and 28 percent faster than `dma_seqlock`, and it is the fastest correct design in all 15 captured-workload cells.

---

## Result 4: Reader-Side Retry Cost

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

<p class="result-note">
Averaged across the 30-cell matrix, 5000 publications per run
</p>

<div class="callout warn">
A <strong>~20,000× gap</strong> between the best and worst correct
design. Both are equally "correct." They are not equally usable.
</div>

Note:
The third cost dimension is where the gap between the correct designs becomes sharp: retries per run. A retry occurs when the reader detects a protocol inconsistency, rejects the sample, and repeats the read.

`dblbuf` averages 0.7 retries per 5000-publication run, essentially never retrying. `seqlock` averages 1,543 retries per run. `dma_seqlock` averages 14,345 retries per run, which is more than nine times `seqlock`'s rate and approximately twenty thousand times `dblbuf`'s rate.

`dblbuf` and `dma_seqlock` are equally correct under the torn-read metric: neither ever returns a torn record. However, the reader-side work required to maintain that correctness differs by four orders of magnitude.

Correctness is a binary property. Cost is not. The two must be measured and reported separately.

---

## Result 5: Accepted-Read Fraction

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
in-progress mirror update, then retry.
</div>

<p class="result-note emphasis">
On a CPU-budget-constrained supervisory core, that matters.
</p>

Note:
The complement of retries is accepted reads: the fraction of read attempts that return valid data.

`dblbuf` accepts 99.95 percent. `seqlock` accepts 97.85 percent. `dma_seqlock` accepts only 8.03 percent, which is approximately twelve times worse than either direct-sharing design.

The mechanism is architectural. The DMA mirror refreshes on its own fixed cadence, once every 1000 nanoseconds in this configuration, regardless of the reader's state. Every refresh is a potential race window for the reader. In `dblbuf`, the only race window is the brief interval during which the writer stores a new generation value. In `dma_seqlock`, the reader races effectively continuously.

This result matters because a real safety-island core operates under a bounded CPU budget. An 8 percent accept rate implies that 92 percent of the monitor's reader-side cycles are spent retrying rather than performing monitor work. The design is logically correct but operationally expensive.

---

## Sensitivity to Workload and Contention

<div class="grid-2">
  <div class="col">
    <h3>Workload shape</h3>
    <p class="section-lede">Captured &rarr; synthesized (sustained bias):</p>
    <ul class="compact-list arrow-list">
      <li><code>dblbuf</code>: <strong>+37%</strong> CPU traffic</li>
      <li><code>seqlock</code>: <strong>+36%</strong> CPU traffic</li>
      <li><code>dma_seqlock</code>: <strong>&lt;1%</strong> (flat)</li>
    </ul>
  </div>
  <div class="col">
    <h3>Contention (0 &rarr; 4 stressors)</h3>
    <p class="section-lede">All architectures grow. <strong>Ordering does not change.</strong></p>
    <ul class="compact-list arrow-list">
      <li>3 disciplined architectures: zero-torn in every cell</li>
      <li>2 undisciplined architectures: tear in every cell</li>
      <li><code>dblbuf</code>: fastest in every cell</li>
    </ul>
  </div>
</div>

<div class="callout">
Absolute cost moves with workload and contention.
<strong>The ranking among correct designs does not.</strong>
</div>

Note:
Two sensitivity axes are relevant.

The first is workload shape. Moving from the captured STM32 trace to the synthesized sustained-bias workload raises CPU-side traffic by 37 percent for `dblbuf` and by 36 percent for `seqlock`. For the synchronized DMA mirror, traffic remains essentially flat, with less than one percent change. This pattern is architecturally consistent: the DMA design keeps the monitor interacting with the mirror rather than with the producer's hot line, so producer-side activity has a smaller effect on the monitor.

The second axis is contention. Increasing stressor CPUs from zero to four raises traffic for every architecture. However, the ordering of designs is stable. The architectures with a primitive remain zero-torn in every cell. The architectures without a primitive tear in every cell. And `dblbuf` is the fastest correct design in every cell.

Workload and contention shift the absolute numbers. They do not change the ranking.

---

<!-- .slide: class="hero" -->

<p class="kicker">Central Claim</p>

<p class="headline">Coherence is the substrate, not the publication contract.</p>

<p class="subhead">Coherence moves the most recent cache line.<br>
It does not attest that its fields belong to the same publication.<br>
That contract must come from the primitive.</p>

Note:
The project's central finding, stated in one sentence: a coherent memory fabric can move the most recent cache line rapidly, but it cannot inform the reader whether the multiple fields on that line belong to one logical publication. That property is a contract, and the contract must be supplied by the publication primitive, not by the transport.

Across the five architectures evaluated, the choice of primitive dominates the choice of transport. Explicit DMA transfer does not, by itself, repair correctness. Both the sequence lock and the double buffer repair correctness regardless of the transport on which they sit. Among the four correct combinations, the generation-counter double buffer over direct coherent sharing wins on every cost dimension measured: fewest coherence messages, shortest whole-workload time, fewest retries, highest accepted-read fraction.

---

## Design Implications

<div class="principle-list">
  <div class="principle">
    <div class="principle-num">01</div>
    <p><strong>Direct coherent sharing:</strong> Use a <strong>generation-counter double buffer</strong>. Not a sequence lock. Not a binary published-index flag.</p>
  </div>
  <div class="principle">
    <div class="principle-num">02</div>
    <p><strong>Isolation via explicit transfer:</strong> The mirror still needs a <strong>record-level handshake</strong>. Transport alone does not buy correctness. The reader pays for isolation in retries.</p>
  </div>
  <div class="principle">
    <div class="principle-num">03</div>
    <p><strong>Specify every channel</strong> on three axes: the publication unit, the validity check, and the reader's behavior on overlap.</p>
  </div>
</div>

Note:
Two practical implications follow.

First, designs built on direct coherent sharing, which is the default for most monitor channels on current SoCs, should use a generation-counter double buffer. The engineering cost is comparable to that of a sequence lock, and the double buffer is cheaper on every axis measured in this project. A binary which-slot-is-current flag should not be used, because the flag has the double-lap failure mode demonstrated earlier. A monotonic counter does not.

Second, designs that use explicit transfer for isolation reasons, for example to prevent the monitor from touching the producer's hot cache line, or to place the monitor on a separate power domain, still require a record-level handshake on the mirror. The transfer itself provides isolation, but not correctness. Furthermore, the reader pays for this isolation in retries, because the transfer cadence creates additional race windows beyond those introduced by the writer.

The broader implication is that a monitor channel specification should state three properties explicitly: the publication unit, the validity check, and the reader's behavior on overlap. A specification missing any of these three properties is underspecified.

---

## Limitations and Future Work

<div class="limit-grid">
  <div class="limit-card">
    <h3>Protocol evidence</h3>
    <p>Ruby <code>MESI_Two_Level</code> gives ordering and message-count evidence, not a cycle-accurate model of CHI, UPI, or AXI4-ACE.</p>
  </div>
  <div class="limit-card">
    <h3>Throughput proxy</h3>
    <p>Whole-workload simulated time is a cost proxy over 5000 publications, not a per-publication latency distribution.</p>
  </div>
  <div class="limit-card">
    <h3>Fixed DMA cadence</h3>
    <p>The pull engine is fixed at 1000 ns. Sweeping cadence is straightforward future work.</p>
  </div>
  <div class="limit-card">
    <h3>One coherence protocol</h3>
    <p><code>MESI_Two_Level</code> only. Alternative directory variants may shift absolute numbers even if the ranking remains stable.</p>
  </div>
</div>

<div class="repo-band">
  <span>Paper + repo</span>
  <code>github.com/nsssayom/pulsebridge</code>
</div>

Note:
To close, an honest accounting of what this project is and is not.

The evidence is protocol-level, not cycle-accurate. gem5 Ruby `MESI_Two_Level` provides message counts and directory traffic, which is sufficient to observe the correctness and cost effects reported in the results. It is not a model of any specific commercial interconnect such as Arm CHI, Intel UPI, or the AXI4-ACE family.

The timing metric is whole-workload simulated time, defined as the gem5 simulated clock from start to finish of the 5000-publication benchmark. That metric is a throughput proxy, not a per-publication latency distribution. This is the most important caveat of the study, and the presentation has flagged it repeatedly.

The DMA cadence is fixed at 1000 nanoseconds, and the coherence protocol is fixed at `MESI_Two_Level`. Sweeping the DMA cadence is future work. Alternative coherence protocols such as MOESI or directory-based variants will shift the absolute numbers, although the ranking of designs is expected to remain robust.

The repository and the written report are linked on this slide. Thank you. Questions are welcome.

---

<!-- .slide: class="title-slide closing-slide" -->

<div class="title-copy">
<p class="kicker">Thank you</p>
<h1>Questions?</h1>
<p class="subtitle">Coherent publication channels for CPS monitoring.</p>
<div class="rule"></div>
<p class="author">Nazmus Shakib Sayom</p>
<p class="affiliation">University of Utah, Kahlert School of Computing</p>
<p class="contact">sayom.shakib@utah.edu</p>
<p class="repo">github.com/nsssayom/pulsebridge</p>
</div>

<div class="closing-qr">
  <img src="web-assets/qr/git-repo-qr.png" alt="github.com/nsssayom/pulsebridge">
  <p class="qr-caption">scan to view repo</p>
</div>

Note:
Thank you. Questions are welcome.
