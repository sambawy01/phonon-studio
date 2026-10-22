"""Serve the built app locally with the cross-origin-isolation headers.

Those headers let Phonon use the threaded WASM build. GitHub Pages cannot send them,
so this is the optimistic case; the real test is without them.
"""
import http.server
import socketserver

PORT = 5192


class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'cross-origin')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer(('127.0.0.1', PORT), H).serve_forever()
