import http.server
import socketserver
import webbrowser
import os

from f007_infrastructure.config import get as _cfg

os.chdir(os.path.dirname(__file__))
PORT = _cfg("server.tree_explorer_port", 8420)


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


with ReusableTCPServer(("", PORT), NoCacheHandler) as httpd:
    url = f"http://localhost:{PORT}/ui/tree_explorer.html"
    print(f"Tree Explorer: {url}")
    webbrowser.open(url)
    httpd.serve_forever()
