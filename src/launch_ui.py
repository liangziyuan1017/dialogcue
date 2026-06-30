import argparse
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from f007_infrastructure.config import get as _cfg

BASE_DIR = Path(__file__).resolve().parent
TREE_UI_DIR = BASE_DIR / "f004_decision_tree"

TREE_PORT = _cfg("server.tree_explorer_port", 8420)
API_PORT = int(os.environ.get("API_PORT", _cfg("server.api_port", 8000)))

procs = []


def _launch_tree_ui() -> subprocess.Popen:
    tree_url = f"http://localhost:{TREE_PORT}/f004_decision_tree/ui/tree_explorer.html"
    print(f"  Tree Explorer  → {tree_url}")
    server_code = (
        "import http.server, socketserver, os\n"
        f"os.chdir({str(BASE_DIR)!r})\n"
        f"PORT = {TREE_PORT}\n"
        "class NoCacheHandler(http.server.SimpleHTTPRequestHandler):\n"
        "    def end_headers(self):\n"
        "        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')\n"
        "        self.send_header('Pragma', 'no-cache')\n"
        "        self.send_header('Expires', '0')\n"
        "        super().end_headers()\n"
        "class ReusableTCPServer(socketserver.TCPServer):\n"
        "    allow_reuse_address = True\n"
        "with ReusableTCPServer(('', PORT), NoCacheHandler) as httpd:\n"
        "    httpd.serve_forever()\n"
    )
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=str(BASE_DIR))
    tmp.write(server_code)
    tmp.close()
    proc = subprocess.Popen(
        [sys.executable, tmp.name],
        cwd=str(BASE_DIR),
    )
    proc._tmp_script = tmp.name
    procs.append(proc)
    return proc


def _launch_api_server() -> subprocess.Popen:
    print(f"  API Server     → http://localhost:{API_PORT}")
    print(f"  API Docs       → http://localhost:{API_PORT}/docs")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "f009_api_server.server:app",
            "--host", "0.0.0.0",
            "--port", str(API_PORT),
            "--reload",
        ],
        cwd=str(BASE_DIR.parent),
        env={
            **os.environ,
            "PYTHONPATH": str(BASE_DIR),
        },
    )
    procs.append(proc)
    return proc


def _shutdown(signum=None, frame=None):
    print("\nShutting down...")
    for proc in procs:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        tmp = getattr(proc, "_tmp_script", None)
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    print("All servers stopped.")
    sys.exit(0)


def run(args) -> None:
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    launch_tree = not args.api_only
    launch_api = not args.tree_only

    print("=" * 60)
    print("Launching UI servers")
    print("=" * 60)

    if launch_tree:
        _launch_tree_ui()

    if launch_api:
        _launch_api_server()

    time.sleep(1)

    if args.open and launch_tree:
        webbrowser.open(f"http://localhost:{TREE_PORT}/f004_decision_tree/ui/tree_explorer.html")
    if args.open and launch_api:
        webbrowser.open(f"http://localhost:{API_PORT}/ui")

    print(f"\nServers running. Press Ctrl+C to stop.")
    print("=" * 60)

    while True:
        for proc in procs:
            ret = proc.poll()
            if ret is not None:
                print(f"Process {proc.pid} exited with code {ret}. Stopping all.")
                _shutdown()
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch the Tree Explorer UI and/or the API server"
    )
    parser.add_argument(
        "--tree-only", action="store_true",
        help="Launch only the Tree Explorer UI",
    )
    parser.add_argument(
        "--api-only", action="store_true",
        help="Launch only the API server",
    )
    parser.add_argument(
        "--no-open", dest="open", action="store_false",
        help="Do not auto-open browser tabs",
    )
    parser.set_defaults(open=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
