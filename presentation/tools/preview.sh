#!/usr/bin/env bash
# Local preview for the deck on macOS.
#
# Usage: tools/preview.sh [port]
#
# - Rebuilds slides.html from slides.md
# - Starts python3 -m http.server in the presentation/ directory
# - Opens the deck in the default browser
#
# Stop the server with Ctrl-C.

set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
port="${1:-8000}"

python3 "$here/tools/build_slides.py"

cd "$here"
python3 -m http.server "$port" >/dev/null 2>&1 &
server_pid=$!
trap 'kill $server_pid 2>/dev/null || true' EXIT

sleep 0.4
open "http://localhost:$port/"
echo "Serving $here on http://localhost:$port/ (pid $server_pid). Ctrl-C to stop."
wait "$server_pid"
