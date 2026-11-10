"""Trusted validation service, never launched by the web application."""
import json
import time
from http.server import BaseHTTPRequestHandler

import requests
from client import call_order
from telemetry import Server, Telemetry, draw
from tenacity import stop_after_attempt

telemetry = Telemetry()
lock, metrics = telemetry.lock, telemetry.metrics
config = {"attempts": 3, "backoff_ms": 50, "exponential": False,
          "jitter_ms": 0, "service_time_ms": 0, "capacity": 4, "seed": 42, "edge": ""}


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
        raw = self.rfile.read(min(4096, int(self.headers.get("Content-Length", "0"))))
        data = json.loads(raw)
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
        if self.path != "/checkout":
            return self.respond(404, {})
        logical = self.headers.get("X-CascadeGraph-Logical-Request-ID", "0")
        with telemetry.work(logical):
            return self.checkout(logical)

    def checkout(self, logical):
        time.sleep(config["service_time_ms"] / 1000)

        def wait(state):
            attempt = state.attempt_number
            base = config["backoff_ms"] * (2 ** (attempt - 1) if config["exponential"] else 1)
            return (base + draw(config["seed"], logical, config["edge"], attempt) * config["jitter_ms"]) / 1000

        def before(state):
            telemetry.outgoing(logical, state.attempt_number > 1)

        def before_sleep(state):
            error = state.outcome.exception()
            response = getattr(error, "response", None)
            cause = f"HTTP_{response.status_code}" if response is not None else type(error).__name__
            telemetry.cause(logical, cause)

        try:
            operation = call_order.retry_with(stop=stop_after_attempt(config["attempts"]), wait=wait,
                                             before=before, before_sleep=before_sleep)
            result = operation(self.headers.get("X-CascadeGraph-Run-ID", "local"),
                               self.headers.get("X-CascadeGraph-Logical-Request-ID", "0"))
            outcome, status = "succeeded", 200
        except requests.RequestException:
            result, outcome, status = {"error": "downstream failure"}, "failed", 503
        with lock:
            metrics[outcome] += 1
        self.respond(status, result)


Server(("0.0.0.0", 8000), Handler).serve_forever()
