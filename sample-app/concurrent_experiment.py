"""Real, open-loop HTTP trials. Invoked only by the guarded GitHub runner entry."""

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from calibration_report import distribution, edge_retries, summarize

from cascadegraph_runtime.models import Scenario
from cascadegraph_runtime.simulation import simulate

PORTS = {"gateway": 18080, "order": 18081, "inventory": 18082}
SEEDS = [11, 42, 73, 101, 211]
CASES = [
    ("Concurrent healthy", "healthy", 0, 0, 3, False, 0),
    ("Concurrent leaf latency", "latency", 60, 0, 3, False, 0),
    ("Concurrent intermittent fixed", "intermittent", 0, 0.5, 3, False, 0),
    ("Concurrent intermittent exponential", "intermittent", 0, 0.5, 3, True, 0),
    ("Concurrent intermittent additive jitter", "intermittent", 0, 0.5, 3, True, 40),
    ("Concurrent no-retry alternative", "intermittent", 0, 0.5, 1, False, 0),
    ("Concurrent all-failing leaf", "intermittent", 0, 1, 3, False, 0),
    ("Concurrent downstream timeouts", "timeout", 250, 0, 3, False, 0),
]


def configure(service, data):
    response = requests.post(f"http://127.0.0.1:{PORTS[service]}/configure", json=data, timeout=5)
    response.raise_for_status()


def metrics():
    observed = {}
    for service, port in PORTS.items():
        response = requests.get(f"http://127.0.0.1:{port}/metrics", timeout=5)
        response.raise_for_status()
        observed[service] = response.json()
    return observed


def drain(timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        observed = metrics()
        if all(m["active"] == 0 and m["queued"] == 0 for m in observed.values()):
            return observed
        time.sleep(0.1)
    raise RuntimeError("Physical work did not drain; refusing to reset/contaminate the next trial")


def request(index, target, started, run_id):
    actual_start = time.monotonic()
    status, error = None, None
    try:
        response = requests.get(
            "http://127.0.0.1:18080/checkout",
            timeout=30,
            headers={"X-CascadeGraph-Run-ID": run_id, "X-CascadeGraph-Logical-Request-ID": str(index)},
        )
        status = response.status_code
    except requests.RequestException as exc:
        error = type(exc).__name__  # Never invent an HTTP outcome.
    return dict(
        logical_id=index,
        status=status,
        transport_error=error,
        scheduled_ms=(target - started) * 1000,
        start_lag_ms=(actual_start - target) * 1000,
        latency_ms=(time.monotonic() - actual_start) * 1000,
    )


def workload(scenario, run_id):
    # One client thread per logical request, no closed-loop worker bottleneck.
    started = time.monotonic() + 0.1
    with ThreadPoolExecutor(max_workers=scenario.requests) as pool:
        futures = []
        for index in range(scenario.requests):
            target = started + index / scenario.arrival_rate
            time.sleep(max(0, target - time.monotonic()))
            futures.append(pool.submit(request, index, target, started, run_id))
        outcomes = [future.result() for future in futures]
    actual = drain()
    return outcomes, actual, (time.monotonic() - started) * 1000


def run(analysis, metadata):
    if (
        os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("RUNNER_ENVIRONMENT") != "github-hosted"
        or os.getenv("GITHUB_REPOSITORY") != "ElusiveParadox/cascadegraph"
    ):
        raise RuntimeError("Concurrent measurements require the trusted GitHub-hosted runner")
    raw, summary, failures = [], [], []
    out = Path("generated-artifacts")
    out.mkdir(exist_ok=True)
    try:
        plan = [(case, seed) for case in CASES for seed in SEEDS]
        random.Random(20261110).shuffle(plan)
        for case, seed in plan:
            label, mode, delay, rate, attempts, exponential, jitter = case
            drain()
            model = analysis.model_copy(deep=True)
            edges = {edge.source: edge.id for edge in model.edges}
            for policy in model.policies:
                if not policy.edge_id:
                    continue
                policy.max_total_attempts = attempts
                policy.category_limits = {}
                policy.backoff.delay_ms = 50 if policy.service_id == "gateway" else 25
                policy.backoff.kind = "exponential" if policy.service_id != "gateway" or exponential else "fixed"
                policy.backoff.jitter_ms = jitter
            scenario = Scenario(
                name=label,
                mode=mode,
                requests=24,
                arrival_rate=50,
                service_time_ms=20,
                fault_latency_ms=delay,
                failure_rate=rate,
                seed=seed,
                deadline_ms=10000,
                concurrency=4,
                queue_limit=500,
            )
            prediction = simulate(model, scenario)
            for service in PORTS:
                config = dict(capacity=4, service_time_ms=20, seed=seed)
                if service == "inventory":
                    config.update(mode=mode, delay_ms=delay, failure_rate=rate)
                else:
                    config.update(
                        attempts=attempts,
                        backoff_ms=50 if service == "gateway" else 25,
                        jitter_ms=jitter,
                        edge=edges[service],
                    )
                    if service == "gateway":
                        config.update(exponential=exponential)
                    else:
                        config.update(custom_loop=False)
                configure(service, config)
            outcomes, actual, horizon = workload(scenario, f"{label}:{seed}")
            latency = distribution([item["latency_ms"] for item in outcomes])
            logical = actual["gateway"]["incoming"]
            downstream = actual["order"]["incoming"] + actual["inventory"]["incoming"]
            retries = edge_retries(actual)
            observed = dict(
                amplification=downstream / logical if logical else 0,
                succeeded=sum(o["status"] == 200 for o in outcomes),
                deadline_misses=sum(o["latency_ms"] >= scenario.deadline_ms for o in outcomes),
                retry_attempts=sum(retries.values()),
                **{key: latency[key] for key in ("p50_ms", "p95_ms", "p99_ms")},
            )
            predicted = {key: prediction[key] for key in observed}
            for service, values in actual.items():
                p = next(p for p in prediction["per_service"] if p["service_id"] == service)
                for key in ("peak_concurrency", "peak_queue", "busy_ms", "retry_attempts", "attempts", "failures"):
                    observed[f"{service}.{key}"] = (
                        retries[service]
                        if key == "retry_attempts"
                        else values["incoming" if key == "attempts" else "failed" if key == "failures" else key]
                    )
                    predicted[f"{service}.{key}"] = p["retries" if key == "retry_attempts" else key]
                observed[f"{service}.mean_occupancy"] = values["busy_ms"] / horizon
                predicted[f"{service}.mean_occupancy"] = p["mean_occupancy"]
            integrity = []
            if logical != scenario.requests or any(o["transport_error"] for o in outcomes):
                integrity.append("Workload delivery/transport failure")
            for parent, child in (("gateway", "order"), ("order", "inventory")):
                if actual[parent]["outgoing_attempts"] != actual[child]["incoming"]:
                    integrity.append(f"{parent} outbound counts do not match {child} receiving counts")
            if mode == "healthy" and actual["gateway"]["peak_concurrency"] < 2:
                integrity.append("Concurrent healthy control did not overlap")
            if mode == "healthy" and (observed["succeeded"] != scenario.requests or downstream != 2 * logical):
                integrity.append("Healthy control had unexpected failures or extra calls")
            if any(
                m["incoming"] != m["succeeded"] + m["failed"] or m["peak_concurrency"] > scenario.concurrency
                for m in actual.values()
            ):
                integrity.append("Incomplete counters or capacity violation")
            record = dict(
                name=label,
                seed=seed,
                jitter_ms=jitter,
                scenario=scenario.model_dump(),
                observed=observed,
                predicted=predicted,
                prediction=prediction,
                actual=actual,
                client_outcomes=outcomes,
                client_latency=latency,
                service_latency={s: distribution(m["latencies_ms"]) for s, m in actual.items()},
                observed_horizon_ms=horizon,
                max_start_lag_ms=max(o["start_lag_ms"] for o in outcomes),
                integrity_failures=integrity,
            )
            raw.append(record)
            if integrity:
                failures.append(dict(name=label, seed=seed, errors=integrity))
            print(
                json.dumps(
                    dict(
                        case=label,
                        seed=seed,
                        measured=observed["amplification"],
                        predicted=predicted["amplification"],
                        integrity=integrity,
                    )
                ),
                flush=True,
            )
        summary = summarize(raw)
    finally:
        complete = len(raw) == len(CASES) * len(SEEDS) and len(summary) == len(CASES) and not failures
        (out / "raw-concurrent-validation.json").write_text(
            json.dumps(
                dict(
                    **metadata, status="measured" if complete else "incomplete", trials=raw, integrity_failures=failures
                ),
                indent=2,
            )
        )
        (out / "concurrent-validation.json").write_text(
            json.dumps(
                dict(
                    **metadata,
                    status="measured" if complete else "incomplete",
                    cases=summary,
                    uncertainty="2000 seeded bootstrap resamples of five independent trials; exploratory intervals, not production coverage.",
                    integrity_failures=failures,
                ),
                indent=2,
            )
        )
    if failures:
        raise AssertionError("Concurrent trial integrity failures; inspect preserved raw artifacts")
