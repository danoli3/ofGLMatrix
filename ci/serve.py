#!/usr/bin/env python3
"""Serve Emscripten output with the isolation headers required by pthreads."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import sys


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8765), partial(Handler, directory=sys.argv[1])).serve_forever()
