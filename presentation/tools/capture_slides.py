#!/usr/bin/env python3
"""Render every slide to a PNG using headless Chrome.

macOS-native: drives /Applications/Google Chrome.app. Lets us verify slide
output without depending on Playwright.

Usage:
    python3 tools/capture_slides.py [--port 8765] [--out _captures]
    python3 tools/capture_slides.py --width 1920 --height 1080 --scale 2
"""
from __future__ import annotations

import argparse
import http.server
import shutil
import socketserver
import subprocess
import threading
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def serve(port: int) -> socketserver.TCPServer:
    handler = http.server.SimpleHTTPRequestHandler

    class Silent(handler):
        def log_message(self, *_args, **_kwargs):
            return

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), Silent)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def count_slides() -> int:
    html = (ROOT / "slides.html").read_text()
    return html.count("<section")


def fragment_counts() -> list[int]:
    """Count `.fragment` elements per slide, returning a list indexed by slide."""
    import re

    html = (ROOT / "slides.html").read_text()
    # Split on <section ...> boundaries; drop the pre-first-section prefix
    parts = re.split(r"<section\b", html)[1:]
    counts = []
    for body in parts:
        # Stop at the next `</section>` so we only count fragments in this slide
        end = body.find("</section>")
        if end != -1:
            body = body[:end]
        counts.append(len(re.findall(r'class="[^"]*\bfragment\b', body)))
    return counts


def wait_for(port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(f"http://127.0.0.1:{port}/", timeout=0.5).close()
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"local server did not come up on :{port}")


def snapshot(
    index: int,
    port: int,
    out_dir: Path,
    width: int,
    height: int,
    scale: float,
    fragment: int | None = None,
) -> Path:
    if fragment is None:
        url = f"http://127.0.0.1:{port}/#/{index}"
        target = out_dir / f"slide-{index:02d}.png"
    else:
        url = f"http://127.0.0.1:{port}/#/{index}/0/{fragment}"
        target = out_dir / f"slide-{index:02d}-f{fragment}.png"
    subprocess.run(
        [
            str(CHROME),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--force-device-scale-factor={scale}",
            "--virtual-time-budget=3500",
            f"--screenshot={target}",
            url,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=ROOT,
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--out", default="_captures")
    parser.add_argument("--only", type=int, help="capture just this slide index")
    parser.add_argument("--width", type=int, default=1920,
                        help="viewport width (reveal scales its 1280 canvas up to fit)")
    parser.add_argument("--height", type=int, default=1080,
                        help="viewport height (reveal scales its 720 canvas up to fit)")
    parser.add_argument("--scale", type=float, default=2.0,
                        help="device scale factor (2 -> 2x pixels, so 1920x1080 becomes 3840x2160)")
    args = parser.parse_args()

    if not CHROME.exists():
        raise SystemExit(f"Chrome not found at {CHROME}")

    subprocess.run(["python3", "tools/build_slides.py"], check=True, cwd=ROOT)

    out_dir = ROOT / args.out
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    httpd = serve(args.port)
    emitted = 0
    try:
        wait_for(args.port)
        total = count_slides()
        frags = fragment_counts()
        indices = [args.only] if args.only is not None else range(total)
        px_w = int(args.width * args.scale)
        px_h = int(args.height * args.scale)
        print(f"  viewport {args.width}x{args.height} @ {args.scale}x  ->  {px_w}x{px_h} PNG")
        for i in indices:
            n = frags[i] if i < len(frags) else 0
            # Always take the initial frame
            snapshot(i, args.port, out_dir, args.width, args.height, args.scale)
            print(f"  slide {i:02d} -> {out_dir.relative_to(ROOT)}/slide-{i:02d}.png")
            emitted += 1
            # Then one frame per fragment step so animated reveals get their own page
            for f in range(1, n + 1):
                snapshot(i, args.port, out_dir, args.width, args.height, args.scale, fragment=f)
                print(f"  slide {i:02d} f{f} -> {out_dir.relative_to(ROOT)}/slide-{i:02d}-f{f}.png")
                emitted += 1
    finally:
        httpd.shutdown()

    print(f"\n{emitted} frame(s) captured in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
