"""Bounded FIFO workers and independent observations for trusted CI only."""

import hashlib
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from http.server import ThreadingHTTPServer


def draw(seed, logical, edge, attempt):
    key = f"{seed}:{logical}:{edge}:0:{attempt}:jitter"
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") / 2**64


class Server(ThreadingHTTPServer):
    request_queue_size = 512
    daemon_threads = True


class Telemetry:
    def __init__(self):
        self.condition = threading.Condition(threading.RLock())
        self.lock = self.condition
        self.metrics = {}
        self.reset(4)

    def reset(self, capacity):
        if self.metrics.get("active") or self.metrics.get("queued"):
            raise ValueError("Cannot reset an active workload")
        self.capacity = capacity
        self.started = time.monotonic()
        self.waiting = deque()
        self.counts = defaultdict(int)
        self.metrics.clear()
        self.metrics.update(incoming=0, succeeded=0, failed=0, active=0, queued=0,
                            peak_concurrency=0, peak_queue=0, busy_ms=0.0,
                            queue_ms=0.0, retry_attempts=0, retry_schedules=0,
                            outgoing_attempts=0, retry_causes={}, latencies_ms=[], events=[])

    def event(self, kind, logical):
        self.metrics["events"].append(dict(event=kind, logical_id=str(logical),
            at_ms=(time.monotonic() - self.started) * 1000,
            active=self.metrics["active"], queued=self.metrics["queued"]))

    def outgoing(self, logical, retry=False):
        with self.lock:
            self.metrics["outgoing_attempts"] += 1
            self.metrics["retry_schedules"] += int(retry)
            self.event("retry_scheduled" if retry else "outgoing", logical)

    def cause(self, logical, cause):
        with self.lock:
            causes = self.metrics["retry_causes"]
            causes[cause] = causes.get(cause, 0) + 1
            self.event("cause:" + cause, logical)

    @contextmanager
    def work(self, logical):
        arrived = time.monotonic()
        ticket = object()
        with self.condition:
            self.metrics["incoming"] += 1
            self.counts[logical] += 1
            ordinal = self.counts[logical]
            self.metrics["retry_attempts"] += int(ordinal > 1)
            queued = bool(self.waiting or self.metrics["active"] >= self.capacity)
            if len(self.waiting) >= 500:
                raise RuntimeError("Trusted workload exceeded queue bound")
            self.waiting.append(ticket)
            self.metrics["queued"] += int(queued)
            self.metrics["peak_queue"] = max(self.metrics["peak_queue"], self.metrics["queued"])
            self.event("arrival", logical)
            while self.waiting[0] is not ticket or self.metrics["active"] >= self.capacity:
                self.condition.wait()
            self.waiting.popleft()
            self.metrics["queued"] -= int(queued)
            started = time.monotonic()
            self.metrics["queue_ms"] += (started - arrived) * 1000
            self.metrics["active"] += 1
            self.metrics["peak_concurrency"] = max(self.metrics["peak_concurrency"], self.metrics["active"])
            self.event("start", logical)
            self.condition.notify_all()
        try:
            yield ordinal
        finally:
            with self.condition:
                finished = time.monotonic()
                self.metrics["active"] -= 1
                self.metrics["busy_ms"] += (finished - started) * 1000
                self.metrics["latencies_ms"].append((finished - arrived) * 1000)
                self.event("finish", logical)
                self.condition.notify_all()
