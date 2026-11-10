"""Retrying order service; leaf attempts are counted at inventory."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from requests.adapters import HTTPAdapter

from client import INVENTORY_RETRY
from custom_retry import custom_retry_request

lock = threading.Lock()
metrics = {"incoming": 0, "succeeded": 0, "failed": 0, "latencies_ms": []}
config = {"attempts": 3, "backoff_ms": 25, "custom_loop": False}


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
            metrics.update(incoming=0, succeeded=0, failed=0, latencies_ms=[])
        self.respond(200, {"status": "configured"})

    def do_GET(self):
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path == "/metrics":
            with lock:
                return self.respond(200, metrics)
        if self.path != "/order":
            return self.respond(404, {})
        started = time.monotonic()
        with lock:
            metrics["incoming"] += 1
        try:
            if config["custom_loop"]:
                response = custom_retry_request(os.environ["INVENTORY_URL"] + "/inventory")
            else:
                policy = INVENTORY_RETRY.new(total=config["attempts"] - 1, connect=config["attempts"] - 1,
                                             read=config["attempts"] - 1, status=config["attempts"] - 1,
                                             backoff_factor=config["backoff_ms"] / 1000)
                with requests.Session() as session:
                    session.mount("http://", HTTPAdapter(max_retries=policy))
                    response = session.get(os.environ["INVENTORY_URL"] + "/inventory", timeout=0.1,
                        headers={"X-CascadeGraph-Run-ID": self.headers.get("X-CascadeGraph-Run-ID", "local"),
                                 "X-CascadeGraph-Logical-Request-ID": self.headers.get("X-CascadeGraph-Logical-Request-ID", "0")})
            response.raise_for_status()
            result, outcome, status = response.json(), "succeeded", 200
        except requests.RequestException:
            result, outcome, status = {"error": "inventory failure"}, "failed", 503
        with lock:
            metrics[outcome] += 1
            metrics["latencies_ms"].append((time.monotonic() - started) * 1000)
        self.respond(status, result)


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
