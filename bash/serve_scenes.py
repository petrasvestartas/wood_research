#!/usr/bin/env python3
"""Serve wood/data/output so the session viewer can watch it while you work.

    bash/serve_scenes.py                 # serves wood/data/output on :8000
    bash/serve_scenes.py --port 8100 --root wood/data/output

Then open the URL it prints. The page polls the manifest AND the files it lists every few
seconds, so re-running an example redraws the scene without a reload, a commit, or a deploy -
the canvas, the GPU device and the camera all survive the swap.

Two headers are the whole reason this is not `python3 -m http.server`:

  Access-Control-Allow-Origin        the viewer is on another origin (github.io, or :8770);
                                     without it the browser drops the answer.
  Access-Control-Allow-Private-Network  Chrome's Private Network Access check: a public https
                                     page reaching something on this machine is preflighted,
                                     and a server that does not opt in is refused.

Everything is served no-store: a build that rewrites a .pb must not be hidden by a cache.
"""
import argparse
import functools
import http.server
import pathlib
import urllib.parse


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, fmt, *args):  # one line per request, without the date noise
        print(f"  {fmt % args}")


def main():
    root_default = pathlib.Path(__file__).resolve().parent.parent / "wood" / "data" / "output"
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=pathlib.Path, default=root_default, help="directory holding pb/ and scenes/")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--scene", default="scenes/face_to_face_viewer.toml", help="manifest to open, relative to --root")
    p.add_argument("--viewer", default="https://petrasvestartas.github.io/session/",
                   help="viewer page; use http://localhost:8770/ for a local trunk serve")
    args = p.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"{root} does not exist - build and run an example first")

    manifest = f"http://localhost:{args.port}/{args.scene}"
    query = urllib.parse.urlencode({"live": manifest})
    print(f"serving {root} on http://localhost:{args.port}\n")
    print(f"  {args.viewer}?{query}\n")
    print("re-run an example and the page redraws within a poll. Ctrl-C to stop.\n")

    handler = functools.partial(Handler, directory=str(root))
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
