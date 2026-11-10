"""Deterministic app-level fault injection in the trusted sample only."""
import hashlib
import json
import time
from http.server import BaseHTTPRequestHandler

from telemetry import Server, Telemetry

telemetry = Telemetry()
lock, metrics = telemetry.lock, telemetry.metrics
config = {"mode": "healthy", "delay_ms": 0, "failure_rate": 0, "seed": 42,
          "capacity": 4, "service_time_ms": 0}


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
            if metrics["active"] or metrics["queued"]:
                return self.respond(409, {"error": "Workload still active"})
            config.update(data)
            telemetry.reset(config["capacity"])
        self.respond(200, {"status": "configured"})

    def do_GET(self):
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path == "/metrics":
            with lock:
                return self.respond(200, metrics)
        if self.path != "/inventory":
            return self.respond(404, {})
        logical = self.headers.get("X-CascadeGraph-Logical-Request-ID", "0")
        with telemetry.work(logical) as ordinal:
            return self.inventory(logical, ordinal)

    def inventory(self, logical, ordinal):
        time.sleep((config["delay_ms"] + config["service_time_ms"]) / 1000)
        key = f"{config['seed']}:{logical}:inventory:{ordinal}:failure"
        draw = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") / 2**64
        fail = config["mode"] == "intermittent" and draw < config["failure_rate"]
        with lock:
            metrics["failed" if fail else "succeeded"] += 1
        self.respond(503 if fail else 200, {"available": not fail})


Server(("0.0.0.0", 8000), Handler).serve_forever()
