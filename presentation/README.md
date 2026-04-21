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
├── figures/                symlink to ../report/figures for slide assets
├── slides.md               source slides in markdown + HTML fragments
├── slides.html             generated reveal.js sections loaded at runtime
├── narration.md            full verbatim speaker script (also embedded
│                           as Note: blocks inside slides.md)
├── tools/
│   ├── build_slides.py     compiles slides.md into slides.html
│   ├── preview.sh          build + serve + open in default browser
│   └── capture_slides.py   snapshot every slide as PNG (headless Chrome)
└── css/
    └── custom.css          reveal-aware deck styling
```

`presentation/figures` is a symlink to `../report/figures`, so the deck
stays in sync with the paper while still working from a static server
rooted at `presentation/`.

## Running locally

reveal.js loads its JavaScript from a CDN, so any static file server
works. Easiest path (macOS):

```bash
./tools/preview.sh         # rebuilds slides.html, serves on :8000,
                           # and opens the deck in your default browser
```

Manual path:

```bash
python3 tools/build_slides.py
python3 -m http.server 8000
open http://localhost:8000/
```

Opening `index.html` directly from the filesystem does **not** work in
most browsers because the generated slide bundle (`slides.html`) is
fetched via `fetch()`, which is blocked on `file://` URLs. Always use a
local HTTP server.

## Verifying slide output (macOS)

For screenshot-based verification without Playwright, use headless Chrome:

```bash
python3 tools/capture_slides.py              # writes _captures/slide-NN.png
python3 tools/capture_slides.py --only 3     # single slide
```

The script spins up a local HTTP server, drives the system Chrome in
headless mode at the deck's native 1280×720, and writes one PNG per slide
into `_captures/`. The directory is wiped on each run; it is safe to
delete and not checked into git.

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

`slides.md` is the source of truth for slide content. Edit it, then
rebuild the generated reveal.js sections:

```bash
python3 tools/build_slides.py
```

The build step turns each `---`-delimited block into one `<section>` in
`slides.html`, carries over any `<!-- .slide: ... -->` attributes, and
converts `Note:` blocks into speaker notes.

If you add a new figure, drop it into `report/figures/` and reference
it as `../report/figures/your-figure.png`.
