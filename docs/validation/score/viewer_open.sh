#!/usr/bin/env bash
# viewer_open.sh <scene dir> [port]: serve a viewer_pics.py scene dir (pb/, scenes/) with CORS on localhost and print the
# viewer URL of each case. Needs the viewer running: `cd session/session_viewer && trunk serve` (port 8770).
set -eu
DIR=$(cd "$1" && pwd); PORT=${2:-8799}
for f in "$DIR"/scenes/*.yaml; do
  echo "http://localhost:8770/?scene=$(basename "$f" .yaml)&data=http://localhost:$PORT/"
done
cd "$DIR" && exec python3 -c '
import http.server, sys
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Cache-Control", "no-store"); super().end_headers()
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()' "$PORT"
