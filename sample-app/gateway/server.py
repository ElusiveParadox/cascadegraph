"""Trusted validation service, never launched by the web application."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from tenacity import stop_after_attempt, wait_exponential, wait_fixed

from client import call_order

lock = threading.Lock()
metrics = {"incoming": 0, "succeeded": 0, "failed": 0, "latencies_ms": []}
config = {"attempts": 3, "backoff_ms": 50, "exponential": False}


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
            config.update(data)
            metrics.update(incoming=0, succeeded=0, failed=0, latencies_ms=[])
        self.respond(200, {"status": "configured"})

    def do_GET(self):
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path == "/metrics":
            with lock:
                return self.respond(200, metrics)
        if self.path != "/checkout":
            return self.respond(404, {})
        started = time.monotonic()
        with lock:
            metrics["incoming"] += 1
        try:
            wait = (wait_exponential(multiplier=config["backoff_ms"] / 1000)
                    if config["exponential"] else wait_fixed(config["backoff_ms"] / 1000))
            operation = call_order.retry_with(stop=stop_after_attempt(config["attempts"]), wait=wait)
            result = operation(self.headers.get("X-CascadeGraph-Run-ID", "local"),
                               self.headers.get("X-CascadeGraph-Logical-Request-ID", "0"))
            outcome, status = "succeeded", 200
        except requests.RequestException:
            result, outcome, status = {"error": "downstream failure"}, "failed", 503
        with lock:
            metrics[outcome] += 1
            metrics["latencies_ms"].append((time.monotonic() - started) * 1000)
        self.respond(status, result)


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
