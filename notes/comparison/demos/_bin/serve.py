"""Static file server for local demos: 127.0.0.1 only, HTTP Range support, CORS for any origin.

Usage: python serve.py <dir> <port>
UCSC Cell Browser needs Range requests (one gene's bytes per request); Vitessce's hosted app
at vitessce.io reads zarr from here, which needs CORS.
"""
import os
import sys
from http.server import ThreadingHTTPServer

from RangeHTTPServer import RangeRequestHandler


class Handler(RangeRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length")
        # Chrome asks before a public page (vitessce.io) reads from 127.0.0.1.
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


os.chdir(sys.argv[1])
ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])), Handler).serve_forever()
