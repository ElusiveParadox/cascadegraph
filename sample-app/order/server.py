"""Retrying order service; leaf attempts are counted at inventory."""
import json
import os
import time
from http.server import BaseHTTPRequestHandler

import requests
from client import INVENTORY_RETRY
from custom_retry import custom_retry_request
from requests.adapters import HTTPAdapter
from telemetry import Server, Telemetry, draw
from urllib3.util import Retry

telemetry = Telemetry()
lock, metrics = telemetry.lock, telemetry.metrics
config = {"attempts": 3, "backoff_ms": 25, "custom_loop": False,
          "jitter_ms": 0, "service_time_ms": 0, "capacity": 4, "seed": 42, "edge": ""}


class MeasuredRetry(Retry):
    def __init__(self, *args, logical="0", **kwargs):
        self.logical = logical
        super().__init__(*args, **kwargs)

    def new(self, **kwargs):
        return super().new(logical=self.logical, **kwargs)

    def increment(self, *args, **kwargs):
        result = super().increment(*args, **kwargs)
        response, error = kwargs.get("response"), kwargs.get("error")
        telemetry.cause(self.logical, f"HTTP_{response.status}" if response is not None else type(error).__name__)
        telemetry.outgoing(self.logical, retry=True)
        return result

    def get_backoff_time(self):
        base = super().get_backoff_time()
        # urllib3 intentionally has no wait, including jitter, on its first retry.
        if len(self.history) <= 1:
            return base
        return base + draw(config["seed"], self.logical, config["edge"], len(self.history)) * config["jitter_ms"] / 1000


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
        if self.path != "/order":
            return self.respond(404, {})
        logical = self.headers.get("X-CascadeGraph-Logical-Request-ID", "0")
        with telemetry.work(logical):
            return self.order(logical)

    def order(self, logical):
        time.sleep(config["service_time_ms"] / 1000)
        try:
            if config["custom_loop"]:
                response = custom_retry_request(os.environ["INVENTORY_URL"] + "/inventory")
            else:
                policy = MeasuredRetry(logical=logical, total=config["attempts"] - 1, connect=config["attempts"] - 1,
                                             read=config["attempts"] - 1, status=config["attempts"] - 1,
                                             backoff_factor=config["backoff_ms"] / 1000,
                                             status_forcelist=INVENTORY_RETRY.status_forcelist,
                                             allowed_methods=INVENTORY_RETRY.allowed_methods)
                telemetry.outgoing(logical)
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
        self.respond(status, result)


Server(("0.0.0.0", 8000), Handler).serve_forever()
