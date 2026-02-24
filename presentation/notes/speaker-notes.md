# Speaker Notes — Cache-Coherent Safety Islands for Low-Latency CPS Policy Monitoring

*20-minute proposal talk. Aim for ~1–1.5 minutes per slide, leaving ~2 minutes for questions.*

---

## Title

> Good morning/afternoon. My name is Nazmus Shakib Sayom, and today I'm presenting my project proposal: **Cache-Coherent Safety Islands for Low-Latency CPS Policy Monitoring**.

> The core idea is simple: modern safety-critical SoCs already have isolated "safety islands" to supervise the main system — but the way they get data today is too slow and too coarse. We want to use cache coherence to fix that.

---

## Slide 1 — Motivation: Functional Safety Implies Bounded Time

> Let's start with *why* this matters.

> In any safety-critical cyber-physical system — think automotive, industrial control, robotics — functional safety standards require that we detect faults and reach a safe state before a hazard can occur. The window we have is called the **Fault-Tolerant Time Interval**, or FTTI.

> Modern automotive SoCs already include a dedicated safety island: a small, isolated processor that watches the main system and can force a fail-safe reaction. But today these islands mostly just check watchdogs and fault flags.

> The opportunity here is to move beyond those coarse checks to **online policy monitoring** — continuously checking that the system's behavior stays within a safety envelope, using real signals, in real time.

---

## Slide 2 — Safety Islands: Where They Sit and What They Do

> So what exactly is a safety island?

> Three key properties: **isolation** — it has its own core, its own memory, its own trusted software stack, so a bug in the main CPU can't take it down. **Supervision** — it observes system health and safety-relevant signals and decides when to trigger a safe state. And **interfaces** — this is where the gap is.

> Today, those interfaces are coarse: watchdog kicks, fault flags, periodic status registers. What's missing is architecture support to let the safety island check **behavioral safety policies** — temporal properties over actual signals — fast enough to matter within FTTI.

---

## Slide 3 — Policy Monitoring: Intent vs. Evidence

> So what does policy monitoring actually look like?

> The key abstraction is **intent versus evidence**. Intent is what the controller *asked* for — the duty cycle it commanded, the dead-time it configured, the update sequence and timestamp. Evidence is what the system *actually did* — the measured PWM edges, the actual waveform timing.

> A policy is a temporal constraint that relates these two. For example: "the realized duty must converge to the intended duty within 100 microseconds." Signal Temporal Logic, or STL, is one common way to encode these.

> The safety island's job is to correlate intent and evidence and trigger a reaction if the policy is violated.

---

## Slide 4 — Example: PWM Actuation Integrity

> Here's a concrete example to make this tangible.

> We have the main CPU running a controller that sends commands to a PWM peripheral, which drives an actuation path out to the plant. The safety island sits below, receiving **intent records** from the controller side and **evidence** — measured waveform timing — from the actuation side.

> The point is: even if the control software is perfectly correct, faults or timing interference downstream can undermine the actuation. We need policies that relate what was *intended* with what was *realized*, with explicit deadlines and tolerances.

---

## Slide 5 — State of Practice: DMA/IPC Safety-Island Interfaces

> How do existing designs handle the data path to the safety island?

> Today, most safety islands ingest data through **IPC mailboxes** and DMA-friendly shared buffers. Arm's Kronos architecture documents HIPC cross-domain messaging; NVIDIA's DriveOS describes a functional safety island with controlled channels.

> The problem is that for fine-grained, step-by-step intent export — which is what policy monitoring needs — these paths require extra copies or explicit cache maintenance. That overhead and jitter competes directly with tight FTTI budgets.

> Our proposal: use a **small cache-coherent shared memory region** as the safety-island interface. The controller just writes; the island just reads — no copies, no cache flushes on the fast path.

---

## Slide 6 — Problem Statement

> Let me state the problem precisely.

> We need to check safety policies within FTTI, using intent and evidence that live in different protection domains. Four constraints matter:

> **Low latency** — the monitor must see new controller intent quickly, not after a DMA round-trip. **Low overhead** — intent export should not burden the control loop; ideally it's just a normal store. **Correctness** — the island must read a *consistent* controller record, not a mixed snapshot of old and new fields. And **predictability** — the worst-case export plus monitoring time must be bounded, even under contention from other cores.

---

## Slide 7 — Goal and Hypothesis

> Our hypothesis is that **cache-coherent shared memory** is the right substrate for this.

> The project goal is to define the **architecture contract** that makes coherent monitoring both correct and time-bounded. That means three things: choosing the right coherent interface for an MCU-like safety island, designing a synchronization discipline for multi-field records, and identifying predictability mechanisms to meet FTTI.

---

## Slide 8 — Why Cache-Coherent Shared Memory?

> Why coherence specifically?

> **Single-copy path**: the controller writes a record once into its cache; the island reads it via ordinary loads. The coherence protocol propagates the data — no message construction, no DMA descriptor, no explicit cache flush.

> Compared to IPC or DMA, this avoids extra copies and software-managed cache maintenance on the fast path. And it's a good fit for control workloads: frequent small records with tight deadlines.

> The key insight is that cache coherence already gives us per-location consistency for free. What this proposal adds is **snapshot correctness** across multiple fields and **bounded latency** for the coherent export path.

---

## Slide 9 — Related Work and Gap

> Let me position this relative to existing work across five areas.

> **Safety islands in practice**: Arm Kronos and NVIDIA DriveOS describe isolated islands, but their interfaces are IPC/DMA-style. **Coherent fabrics**: Arm AMBA ACE and CHI provide the hardware substrate — coherence-capable interconnects. **Correctness under weak ordering**: the Arm memory model work by Pulte et al. and heterogeneous consistency work like MemGlue give us the formal foundations. **Bounded latency**: predictable coherence work by Hassan, Kaushik, and mixed-criticality work by Chisholm address timing. **Monitoring foundations**: Simplex-style runtime assurance and tools like RTAMT provide the monitoring side.

> The **gap** is that nobody has put these pieces together: an end-to-end architecture for coherent intent export, time-aligned evidence, and bounded detection latency for safety-island policy monitoring.

---

## Slide 10 — Proposed Architecture

> Here's the architecture we propose.

> The main CPU controller — Arm A-profile — writes intent records into a **cache-coherent shared memory region**. The PWM peripheral drives the actuation path. An evidence tap captures timestamped measurements of the realized waveform.

> The safety island — an MCU-like core — reads the intent record via coherence and receives evidence, then evaluates the policy. If the policy is violated, it triggers a safety reaction, which feeds back as a fail-safe override.

> The key architectural question is the contract that governs that shared memory interface: what ordering guarantees does the island see, and how do we bound the latency?

---

## Slide 11 — Challenge 1: Consistent Records

> The first challenge is **snapshot consistency**.

> Under weak memory ordering — which is what Arm gives us by default — the safety island might observe the controller's stores in a different order than they were programmed. So the island could load a new timestamp but an old duty value — a **mixed snapshot** that doesn't correspond to any real controller state.

> We need an export record format and a synchronization discipline — barriers, release/acquire, or a sequence-lock pattern — so that every island read yields a consistent snapshot of the controller's intent.

---

## Slide 12 — Challenge 2: Bounded Detection Latency

> The second challenge is **bounded latency**.

> The total detection budget breaks into three pieces: **export latency** — the time for the coherent read to complete, which involves invalidations, cache line transfers, and directory lookups. **Monitor latency** — the time to evaluate the policy over the current signal window. And **react latency** — the time to trigger the fail-safe output.

> All three must sum to less than or equal to FTTI. The export phase is the most variable — contention from other cores inflates it. We need predictability mechanisms: cache partitioning, interconnect priorities, and careful protocol choices to bound the worst case.

---

## Slide 13 — Research Questions

> This leads to four research questions.

> **RQ1**: How should an MCU-like safety island participate in coherence with an A-profile main CPU? Full coherence agent, or coherent I/O? What access control?

> **RQ2**: What record format and synchronization rules guarantee consistent multi-field snapshots under Arm's weak ordering model?

> **RQ3**: What worst-case export and monitoring latency bounds are achievable under contention, and what mechanisms enforce them?

> **RQ4**: Where do we measure realized actuation — at the peripheral, at the pin, or at the plant? And how do we align evidence timestamps with controller intent records?

---

## Slide 14 — Case Study: PWM Actuation Integrity

> We'll ground this in a concrete case study: **PWM actuation integrity**.

> The intent signals come from the shared record: duty cycle, dead-time, update sequence, and timestamp. The evidence comes from edge timings and waveform-derived measurements.

> We have several illustrative policies: **tracking** — the realized duty converges to the intended duty within a deadline and stays within tolerance. **Glitch exclusion** — no pulses below a minimum width. **Safety envelope** — upon a safety condition, the PWM enters a conservative state within a deadline.

> These can be encoded in STL; robust monitoring can output not just pass/fail but a quantitative margin.

---

<!-- ## Slide 16 — Soundness: What Must Hold

> For the architecture to be sound, three assumptions must hold — and we will make them explicit and validate them.

> First, the **coherent export path** with our synchronization discipline must actually yield consistent snapshots — we'll validate this with litmus tests and memory-model tools.

> Second, there must be **bounded skew** between controller timestamps and evidence timestamps — we need a shared time base or a bounded drift analysis.

> Third, the **worst-case latency** of export plus monitor plus reaction must fit within FTTI — we'll characterize this through simulation or microbenchmarks. -->

---

## Slide 15 — Tools and Interfaces We Will Explore

> Let me briefly cover the tools.

> For **coherent interfaces**, we'll study Arm AMBA ACE and CHI specifications — specifically how to attach a safety island as a coherent agent or coherent I/O endpoint.

> For **ordering validation**, we'll use litmus tests and Herd7 to check that our record format and barrier placement actually prevent mixed snapshots under the Arm memory model.

> For **latency analysis**, we'll use microbenchmarks or gem5 simulation to characterize coherent access latency under contention.

> For **monitor prototyping**, we'll use RTAMT or a similar temporal monitoring library to prototype policy monitors on PWM traces.

---

## Slide 16 — Expected Contributions

> Four expected contributions:

> First, a **cache-coherent safety-island monitoring architecture** for low-latency CPS policy checks — the overall design.

> Second, a monitoring-oriented **shared-memory contract**: the record format, the ordering rules, the time-alignment assumptions.

> Third, a **predictability analysis** for coherent intent export under contention — worst-case bounds and the mechanisms that enforce them.

> Fourth, a **PWM actuation-integrity case study** that grounds the policies and evidence choices in a concrete, industrially-relevant scenario.

---

## Slide 17 — Wrap-Up / Questions

> To wrap up: we're pushing **cache-coherent shared memory** — not DMA, not IPC — as the safety-island interface for low-latency intent export.

> We'll define the coherent interface and synchronization contract so the island reads consistent controller records. We'll bound worst-case coherent-access latency so policy checks stay meaningful within FTTI. And we'll ground the design in a PWM actuation-integrity case study.

> Thank you. I'm happy to take questions.

---

*Timing checkpoint: if running long, compress Related Work and Tools slides into quick summaries. If running short, expand on the PWM case study policies and the coherence protocol details.*
