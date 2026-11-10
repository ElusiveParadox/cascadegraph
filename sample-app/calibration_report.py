"""Pure reporting functions; no services, network, model fitting or observations."""

import math
import random
import statistics


def percentile(values, fraction):
    if not values:
        raise ValueError("Cannot summarize an empty distribution")
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def distribution(values):
    return dict(n=len(values), p50_ms=percentile(values, .5),
                p95_ms=percentile(values, .95), p99_ms=percentile(values, .99),
                min_ms=min(values), max_ms=max(values), mean_ms=statistics.mean(values))


def interval(values):
    """Seeded percentile bootstrap over independent trials, not nested requests."""
    if len(values) < 2:
        raise ValueError("Uncertainty requires repeated independent trials")
    rng = random.Random(20261110)
    means = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(2000)]
    return dict(n_trials=len(values), mean=statistics.mean(values),
                bootstrap_ci95=[percentile(means, .025), percentile(means, .975)])


def edge_retries(actual):
    """des-1.0 counts retry-layer invocations, not all repeated logical receipts."""
    return {"gateway": 0, "order": actual["gateway"]["retry_schedules"],
            "inventory": actual["order"]["retry_schedules"]}


def summarize(trials):
    groups = {}
    for trial in trials:
        groups.setdefault(trial["name"], []).append(trial)
    result = []
    for name, rows in groups.items():
        keys = list(rows[0]["observed"])
        comparisons = {}
        for key in keys:
            observed = [r["observed"][key] for r in rows]
            predicted = [r["predicted"][key] for r in rows]
            comparisons[key] = dict(observed=interval(observed), predicted=interval(predicted),
                paired_error=interval([o - p for o, p in zip(observed, predicted, strict=True)]))
        flags = []
        amp = comparisons["amplification"]["paired_error"]
        latency = comparisons["p95_ms"]["paired_error"]
        if max(abs(v) for v in amp["bootstrap_ci95"]) > .5:
            flags.append("Amplification discrepancy exceeds the legacy 0.5 count tolerance.")
        if abs(latency["mean"]) > max(50, .25 * comparisons["p95_ms"]["predicted"]["mean"]):
            flags.append("p95 latency differs by over 50 ms or 25%; this is not calibrated latency accuracy.")
        for service in ("gateway", "order", "inventory"):
            key = service + ".busy_ms"
            if key in comparisons:
                busy = comparisons[key]
                if abs(busy["paired_error"]["mean"]) > .1 * max(1, busy["predicted"]["mean"]):
                    flags.append(f"{service} occupied-worker time differs by more than 10%.")
            key = service + ".peak_queue"
            if key in comparisons:
                queue = comparisons[key]
                if abs(queue["paired_error"]["mean"]) > max(2, .25 * queue["predicted"]["mean"]):
                    flags.append(f"{service} peak worker queue differs by more than 25% or two slots.")
        notes = [
            "Model service times are controlled inputs, not fitted to observations.",
            "Real transport/scheduler overhead and 100 ms drain-poll resolution are absent from virtual time.",
            "Compared retries are the immediate caller's retry-hook counts. Repeated receiving-side logical IDs also include ancestor replays and remain separate raw diagnostics.",
        ]
        if rows[0]["scenario"]["mode"] == "timeout":
            notes.append("Model timeout faults use max(fault latency, twice scenario timeout); actual leaf sleeps the declared delay. Both leave physical work running, but durations differ.")
        if rows[0]["jitter_ms"]:
            notes.append("urllib3 skips its first retry wait/jitter; des-1.0 adds jitter on that retry. Repeated parent calls reuse keyed jitter. This known structural discrepancy is not fitted away.")
        if any(r["observed"]["gateway.peak_queue"] > 0 for r in rows):
            notes.append("Gateway FIFO worker queue was exercised. HTTP accept/connection queues and cancellation are not represented by the model.")
        result.append(dict(name=name, seeds=[r["seed"] for r in rows], comparisons=comparisons,
                           discrepancy_flags=flags, investigation=notes))
    return result
