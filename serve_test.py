"""Serve dist/ under /phonon-studio/ exactly as GitHub Pages will.

Two modes via argv[1]:
  iso    — with cross-origin isolation headers (threaded WASM)
  plain  — without them (what GitHub Pages can actually send)
"""
import http.server
import os
import socketserver
import sys

PORT = 5192
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
PREFIX = '/phonon-studio'
MODE = sys.argv[1] if len(sys.argv) > 1 else 'plain'


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        p = self.path.split('?')[0]
        if p.startswith(PREFIX):
            self.path = p[len(PREFIX):] or '/'
        return super().do_GET()

    def end_headers(self):
        if MODE == 'iso':
            self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
            self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'cross-origin')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
print(f'serving {ROOT} at http://127.0.0.1:{PORT}{PREFIX}/ (mode={MODE})', flush=True)
socketserver.TCPServer(('127.0.0.1', PORT), H).serve_forever()
