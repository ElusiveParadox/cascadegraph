"""Real HTTP measurements compared with separately computed predictions."""

import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import requests

from cascadegraph_runtime.analysis import analyze, utcnow
from cascadegraph_runtime.models import Scenario
from cascadegraph_runtime.security import sample_files
from cascadegraph_runtime.simulation import simulate

PORTS = {"gateway": 18080, "order": 18081, "inventory": 18082}


def get(service, path):
    return requests.get(f"http://127.0.0.1:{PORTS[service]}{path}", timeout=15)


def configure(service, data):
    response = requests.post(f"http://127.0.0.1:{PORTS[service]}/configure", json=data, timeout=5)
    response.raise_for_status()


async def main():
    analysis = await analyze(sample_files(), "Trusted CI sample", "sample")
    rows, raw = [], []
    cases = [
        ("Healthy baseline", "healthy", 0, 0, 3),
        ("Fixed downstream latency", "latency", 60, 0, 3),
        ("Intermittent 503s", "intermittent", 0, 0.5, 3),
        ("All leaf requests fail", "intermittent", 0, 1, 3),
        ("No retries alternative", "intermittent", 0, 1, 1),
        ("Downstream timeouts", "timeout", 250, 0, 3),
    ]
    for label, mode, delay, failure_rate, attempts in cases:
        configure("gateway", {"attempts": attempts, "backoff_ms": 50, "exponential": False})
        configure("order", {"attempts": attempts, "backoff_ms": 25, "custom_loop": False})
        configure("inventory", {"mode": mode, "delay_ms": delay, "failure_rate": failure_rate, "seed": 42})
        model = analysis.model_copy(deep=True)
        for p in model.policies:
            if p.edge_id:
                p.max_total_attempts = attempts
                p.category_limits = {}
        scenario = Scenario(name=label, mode=mode, requests=10, arrival_rate=0.2,
                            failure_rate=failure_rate, fault_latency_ms=delay,
                            deadline_ms=10000, concurrency=50)
        prediction = simulate(model, scenario)
        outcomes = []
        latencies = []
        for index in range(10):
            start = time.monotonic()
            response = requests.get("http://127.0.0.1:18080/checkout", timeout=12,
                headers={"X-CascadeGraph-Run-ID": label, "X-CascadeGraph-Logical-Request-ID": str(index)})
            outcomes.append(response.status_code == 200)
            latencies.append((time.monotonic() - start) * 1000)
            # Sequential low-load runs remove queue/capacity variance; simulator
            # arrivals are spaced 5s, so the failure cases cannot overlap.
        time.sleep(0.5)  # collect operations finishing after client timeout
        actual = {s: get(s, "/metrics").json() for s in PORTS}
        logical = actual["gateway"]["incoming"]
        downstream = actual["order"]["incoming"] + actual["inventory"]["incoming"]
        amplification = downstream / logical
        error = abs(prediction["amplification"] - amplification)
        row = dict(name=label, predicted_amplification=prediction["amplification"],
                   measured_amplification=amplification, absolute_error=round(error, 6),
                   predicted_successes=prediction["succeeded"], measured_successes=sum(outcomes),
                   logical_requests=logical)
        rows.append(row)
        raw.append(dict(case=row, prediction=prediction, observed=actual,
                        observed_latency_median_ms=statistics.median(latencies), scenario=scenario.model_dump()))
        if logical != 10:
            raise AssertionError("Workload did not reach gateway")
        # Count/error gates, not an assertion of perfect latency realism.
        if error > 0.5 or abs(prediction["succeeded"] - sum(outcomes)) > 1:
            raise AssertionError(f"Prediction discrepancy exceeds declared tolerance: {row}")
    out = Path("generated-artifacts")
    out.mkdir(exist_ok=True)
    report = dict(status="measured", detail="Six controlled, low-load CI sample experiments. Counts are compared; production latency accuracy is not claimed.",
        workflow_url=f"https://github.com/ElusiveParadox/cascadegraph/actions/runs/{os.getenv('GITHUB_RUN_ID', 'unavailable')}",
        commit_sha=os.getenv("GITHUB_SHA"), measured_at=utcnow(), cases=rows)
    (out / "validation.json").write_text(json.dumps(report, indent=2))
    (out / "raw-validation.json").write_text(json.dumps(raw, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
