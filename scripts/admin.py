#!/usr/bin/env python3
"""
Cluster admin server — manages the 3-node Akka cluster directly from Python.
No shell script delegation — handles Docker, Maven, and process management natively.

Usage: python scripts/admin.py [--port 8080]
"""

import http.server
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
STATIC_DIR = SCRIPT_DIR / "static"
PORT = 8080
BASE_PORT = 9000
NODE_COUNT = 3
MVN = "mvn.cmd" if sys.platform == "win32" else "mvn"

# Track node processes: {node_id: subprocess.Popen}
nodes = {}


def node_port(n):
    return BASE_PORT + n - 1


def is_postgres_running():
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", "akka-postgres"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


def start_postgres():
    if is_postgres_running():
        return "Postgres already running"

    subprocess.run(["docker", "rm", "-f", "akka-postgres"],
                   capture_output=True, timeout=10)
    result = subprocess.run(
        ["docker", "run", "-d", "--name", "akka-postgres",
         "-p", "5432:5432",
         "-e", "POSTGRES_USER=postgres",
         "-e", "POSTGRES_PASSWORD=postgres",
         "postgres:15"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return f"Failed to start Postgres: {result.stderr}"

    # Wait for ready
    for _ in range(30):
        check = subprocess.run(
            ["docker", "exec", "akka-postgres", "pg_isready", "-q", "-U", "postgres"],
            capture_output=True, timeout=5
        )
        if check.returncode == 0:
            return "Postgres started"
        time.sleep(1)
    return "Postgres started (may not be ready yet)"


def stop_postgres():
    subprocess.run(["docker", "rm", "-f", "akka-postgres"],
                   capture_output=True, timeout=10)
    return "Postgres stopped"


def ensure_compiled():
    classes = PROJECT_DIR / "target" / "classes"
    if not classes.is_dir():
        subprocess.run(
            [MVN, "-q", "compile"],
            cwd=str(PROJECT_DIR), capture_output=True, timeout=120
        )


def start_node(n):
    if n in nodes and nodes[n].poll() is None:
        return f"Node {n} already running (PID {nodes[n].pid})"

    start_postgres()
    ensure_compiled()

    port = node_port(n)
    log_path = SCRIPT_DIR / f"node-{n}.log"
    log_file = open(log_path, "w")

    env = os.environ.copy()
    proc = subprocess.Popen(
        [MVN, "-q", "exec:java",
         f"-Dconfig.resource=local-node{n}.conf",
         f"-Dakka.javasdk.dev-mode.http-port={BASE_PORT}",
         f"-Dakka.javasdk.dev-mode.service-name=resilience-{n}",
         "-Dakka.persistence.r2dbc.connection-factory.database=postgres"],
        cwd=str(PROJECT_DIR),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )

    nodes[n] = proc
    return f"Node {n} started (PID {proc.pid}, port {port})"


def stop_node(n):
    if n not in nodes or nodes[n].poll() is not None:
        # Try to find and kill by port
        port = node_port(n)
        killed = kill_by_port(port)
        nodes.pop(n, None)
        return f"Node {n} stopped" if killed else f"Node {n} was not running"

    proc = nodes[n]
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=5)
    except Exception:
        proc.kill()

    # Also kill any Java process lingering on the port
    kill_by_port(node_port(n))
    nodes.pop(n, None)
    return f"Node {n} stopped"


def kill_by_port(port):
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if f":{port} " in line and "LISTEN" in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True, timeout=5)
                    return True
        except Exception:
            pass
    return False


def stop_all():
    messages = []
    for n in range(1, NODE_COUNT + 1):
        messages.append(stop_node(n))
    messages.append(stop_postgres())
    return "\n".join(messages)


def probe_node(port):
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/hello/probe", timeout=2)
        return req.getcode() == 200
    except Exception:
        return False


def get_status():
    pg_running = is_postgres_running()
    node_list = []
    for n in range(1, NODE_COUNT + 1):
        port = node_port(n)
        running = n in nodes and nodes[n].poll() is None
        healthy = probe_node(port) if running else False
        # If not tracked but port responds, mark as running
        if not running and probe_node(port):
            running = True
            healthy = True
        entry = {"id": n, "port": port, "status": "RUNNING" if running else "STOPPED", "healthy": healthy}
        if running and n in nodes:
            entry["pid"] = nodes[n].pid
        node_list.append(entry)
    return {"postgres": "RUNNING" if pg_running else "STOPPED", "nodes": node_list}


def json_response(handler, status, data):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())


class AdminHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[admin] {args[0]}", flush=True)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/status":
            try:
                json_response(self, 200, get_status())
            except Exception as e:
                json_response(self, 200, {"postgres": "ERROR", "nodes": [], "error": str(e)})
            return

        # Static file serving
        if path == "/" or path == "":
            path = "/index.html"

        file_path = STATIC_DIR / path.lstrip("/")
        if file_path.is_file():
            content_types = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".png": "image/png",
                ".svg": "image/svg+xml",
            }
            self.send_response(200)
            self.send_header("Content-Type", content_types.get(file_path.suffix, "application/octet-stream"))
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            if path == "/api/stop-all":
                msg = stop_all()
                json_response(self, 200, {"ok": True, "output": msg})
                return

            if path == "/api/db/start":
                msg = start_postgres()
                json_response(self, 200, {"ok": True, "output": msg})
                return

            if path == "/api/db/stop":
                msg = stop_postgres()
                json_response(self, 200, {"ok": True, "output": msg})
                return

            # /api/node/{n}/start or /api/node/{n}/stop
            if path.startswith("/api/node/") and path.count("/") == 4:
                segments = path.strip("/").split("/")
                node_id_str = segments[2]
                action = segments[3]
                if node_id_str in ("1", "2", "3") and action in ("start", "stop"):
                    n = int(node_id_str)
                    if action == "start":
                        msg = start_node(n)
                    else:
                        msg = stop_node(n)
                    json_response(self, 200, {"ok": True, "output": msg})
                    return
        except Exception as e:
            json_response(self, 500, {"ok": False, "error": str(e)})
            return

        json_response(self, 404, {"error": "Not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])

    server = http.server.HTTPServer(("0.0.0.0", port), AdminHandler)
    print(f"Cluster admin server running at http://localhost:{port}", flush=True)
    print(f"Dashboard: http://localhost:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down — stopping all nodes...")
        stop_all()
        server.server_close()


if __name__ == "__main__":
    main()
