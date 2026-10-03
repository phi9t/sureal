"""Serve the built viewer (web/dist) and the bundle cache from one local origin.

Usage: python -m export.serve --dist DIR --bundles DIR [--port 8420] [--host 127.0.0.1]

Bundles are Waymo-derived data under the Waymo Open Dataset terms: keep this
server bound to localhost or a trusted network. Supports HTTP Range requests and
sends permissive CORS headers so the GitHub Pages build of the viewer can load
bundles from this local server via ?bundle=http://127.0.0.1:PORT/bundles/...
"""
import argparse
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MIME = {".json": "application/json", ".wpc": "application/octet-stream", ".jpg": "image/jpeg", ".png": "image/png",
        ".js": "text/javascript", ".css": "text/css", ".html": "text/html; charset=utf-8"}


def make_handler(dist, bundles):
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path.startswith("/bundles/"):
                rel = path[len("/bundles/"):]
                if rel in ("", "index.json"):
                    return self._json(self._index())
                target = (bundles / rel).resolve()
                if not str(target).startswith(str(bundles.resolve()) + os.sep) or not target.is_file():
                    return self.send_error(404)
                return self._file(target)
            target = (dist / (path.lstrip("/") or "index.html")).resolve()
            if not str(target).startswith(str(dist.resolve())) or not target.is_file():
                target = dist / "index.html"
            return self._file(target)

        def _index(self):
            scenes = []
            if bundles.is_dir():
                for slice_dir in sorted(p for p in bundles.iterdir() if p.is_dir()):
                    for ctx in sorted(p for p in slice_dir.iterdir() if (p / "scene.json").is_file()):
                        scenes.append({"slice": slice_dir.name, "context": ctx.name, "url": "/bundles/%s/%s/" % (slice_dir.name, ctx.name)})
            return {"root": str(bundles), "scenes": scenes}

        def _json(self, obj):
            data = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _file(self, target):
            size = target.stat().st_size
            start, end = 0, size - 1
            status = 200
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                a, _, b = rng[6:].partition("-")
                start = int(a) if a else max(0, size - int(b))
                end = int(b) if b and a else end
                status = 206
            self.send_response(status)
            self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(end - start + 1))
            if status == 206:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.end_headers()
            with open(target, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

        def log_message(self, fmt, *args):
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dist", required=True)
    ap.add_argument("--bundles", required=True)
    ap.add_argument("--port", type=int, default=8420)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)
    dist, bundles = Path(a.dist), Path(a.bundles)
    if not (dist / "index.html").is_file():
        raise SystemExit("no build at %s; run 'run.sh build' first" % dist)
    server = ThreadingHTTPServer((a.host, a.port), make_handler(dist, bundles))
    print("serving %s and %s at http://%s:%d/" % (dist, bundles, a.host, a.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
