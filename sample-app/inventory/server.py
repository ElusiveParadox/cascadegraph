"""Deterministic app-level fault injection in the trusted sample only."""
import hashlib
import json
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

lock = threading.Lock()
metrics = {"incoming": 0, "succeeded": 0, "failed": 0, "latencies_ms": []}
counts = defaultdict(int)
config = {"mode": "healthy", "delay_ms": 0, "failure_rate": 0, "seed": 42}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if self.path != "/configure":
            return self.respond(404, {})
        data = json.loads(self.rfile.read(min(4096, int(self.headers.get("Content-Length", "0")))))
        with lock:
            config.update(data)
            counts.clear()
            metrics.update(incoming=0, succeeded=0, failed=0, latencies_ms=[])
        self.respond(200, {"status": "configured"})

    def do_GET(self):
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path == "/metrics":
            with lock:
                return self.respond(200, metrics)
        if self.path != "/inventory":
            return self.respond(404, {})
        started = time.monotonic()
        logical = self.headers.get("X-CascadeGraph-Logical-Request-ID", "0")
        with lock:
            metrics["incoming"] += 1
            counts[logical] += 1
            ordinal = counts[logical]
        if config["delay_ms"]:
            time.sleep(config["delay_ms"] / 1000)
        key = f"{config['seed']}:{logical}:inventory:{ordinal}:failure"
        draw = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") / 2**64
        fail = config["mode"] == "intermittent" and draw < config["failure_rate"]
        with lock:
            metrics["failed" if fail else "succeeded"] += 1
            metrics["latencies_ms"].append((time.monotonic() - started) * 1000)
        self.respond(503 if fail else 200, {"available": not fail})


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
