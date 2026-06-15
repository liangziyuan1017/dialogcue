import http.server
import socketserver
import webbrowser
import os

os.chdir(os.path.dirname(__file__))
PORT = 8420

Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    url = f"http://localhost:{PORT}/tree_explorer.html"
    print(f"Tree Explorer: {url}")
    webbrowser.open(url)
    httpd.serve_forever()
