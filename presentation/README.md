# Presentation — reveal.js deck

A ground-up presentation of *Correct and Efficient Publication of
Multi-Field Control Records over Coherent Memory for CPS Monitoring*.

The deck is designed to be understandable to an audience that is
comfortable with computer architecture (caches, multicore, coherence)
but **not** necessarily with CPS monitoring, Signal Temporal Logic,
sequence locks, or DMA engines. Each of those concepts is demystified
on its own slide before it is used.

## Contents

```
presentation/
├── README.md               this file
├── index.html              reveal.js entry point (loads from CDN)
├── slides.md               single source of truth for slide content
├── narration.md            full verbatim speaker script (also embedded
│                           as Note: blocks inside slides.md)
└── css/
    └── custom.css          Okabe–Ito accent palette + typography tweaks
```

Figures are referenced directly from `../report/figures/` so the deck
stays in sync with the paper.

## Running locally

reveal.js loads its JavaScript from a CDN, so any static file server
works. From the repository root:

```bash
cd presentation
python3 -m http.server 8000
```

Then open <http://localhost:8000/> in a browser.

Opening `index.html` directly from the filesystem does **not** work in
most browsers because the external markdown file (`slides.md`) is
fetched via `fetch()`, which is blocked on `file://` URLs. Always use a
local HTTP server.

## Speaker view

Press `S` while the deck is focused to open the speaker notes window.
Each slide's `Note:` block renders there verbatim. Narration is
deliberate — read slowly; the deck is paced for a 18–20 minute talk.

## PDF export

Append `?print-pdf` to the URL and use the browser's Print dialog with
*Save as PDF*. Set margins to *None* and background graphics on.

```
http://localhost:8000/?print-pdf
```

## Structure of the talk

The deck has six acts, not labeled in the slides but visible in the
flow:

1. **Why are we here?** (slides 1–3) — safety islands, the witness
   record, a one-sentence motivation.
2. **The trap** (slides 4–7) — why "just put it in shared memory"
   does not work. Coherence vs. consistency, a torn-read timeline,
   why tearing is a correctness failure.
3. **The design space** (slides 8–12) — transport × primitive as a
   2×3 grid, the two transports, the two primitives, why a generation
   counter beats a binary flag.
4. **How we test** (slides 13–15) — the five architectures, the gem5
   testbed, the matrix and the metrics.
5. **Results** (slides 16–21) — correctness, CPU-side traffic,
   whole-workload time, the retry cliff, the accepted-read cliff,
   workload and contention sensitivity.
6. **Takeaway** (slides 22–24) — the headline, the design
   implications, and an honest limitations slide.

## Editing

`slides.md` is the only file you need to edit for slide content.
Reveal.js splits it into slides on `\n---\n` (horizontal) and
`\n--\n` (vertical). Speaker notes for a slide go into a `Note:`
block at the bottom of the slide.

If you add a new figure, drop it into `report/figures/` and reference
it as `../report/figures/your-figure.png`.
