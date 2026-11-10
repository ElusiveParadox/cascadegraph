"""Bounded discrete events; the core has no HTTP, database or LLM dependency."""

import hashlib
import heapq
import itertools
import math
from collections import defaultdict, deque

from .models import MODEL_VERSION, Analysis, Policy, Scenario
from .security import InputError

MAX_EVENTS = 200_000


def random_unit(seed, *parts):
    raw = hashlib.sha256(":".join(map(str, (seed, *parts))).encode()).digest()
    return int.from_bytes(raw[:8], "big") / 2**64


def retry_delay(policy: Policy, failed_attempt: int, jitter: float) -> float:
    b = policy.backoff
    if b.kind == "unknown" or b.delay_ms is None:
        raise InputError("Backoff is unknown; confirm a complete supported policy")
    if b.kind == "none":
        return 0
    if b.kind == "fixed":
        result = b.delay_ms
    elif policy.framework == "urllib3":
        # urllib3's first retry has no wait; subsequent waits are factor*2**n.
        result = 0 if failed_attempt == 1 else b.delay_ms * 2**(failed_attempt - 1)
    else:
        result = b.delay_ms * b.multiplier**(failed_attempt - 1)
    if b.cap_ms is not None:
        result = min(result, b.cap_ms)
    return result + jitter * b.jitter_ms


def eligible(policy, outcome):
    return (
        outcome in policy.retry_on
        or outcome.isdigit() and outcome.startswith("5") and "5xx" in policy.retry_on
        or outcome in {"503", "timeout", "connect"} and "exception" in policy.retry_on
    ) and (policy.allowed_methods is None or "GET" in policy.allowed_methods)


def simulate(analysis: Analysis, scenario: Scenario, candidate=False) -> dict:
    nodes = {n.id for n in analysis.nodes}
    if not nodes or not analysis.edges:
        raise InputError("Simulation requires services and evidence-backed call edges")
    adjacency = {n: [] for n in sorted(nodes)}
    policies = {p.id: p.model_copy(deep=True) for p in analysis.policies}
    for edge in sorted(analysis.edges, key=lambda e: e.id):
        if edge.source not in nodes or edge.target not in nodes:
            raise InputError("Graph edge references an unknown service")
        if not edge.policy_ids:
            raise InputError(f"{edge.id}: no policy binding; declare policy_symbols before simulating")
        for pid in edge.policy_ids:
            p = policies[pid]
            if p.max_total_attempts is None or not 1 <= p.max_total_attempts <= 10 or not p.retry_on or p.backoff.kind == "unknown":
                raise InputError(f"{p.symbol}: attempts, retry conditions or backoff are unresolved")
            if p.unresolved and not p.confirmed:
                raise InputError(f"{p.symbol}: review unsupported policy fields before simulation")
            if candidate and scenario.candidate_attempts is not None:
                p.max_total_attempts = scenario.candidate_attempts
                p.category_limits = {}
                p.backoff.kind = "exponential"
                p.backoff.delay_ms = scenario.candidate_backoff_ms
                p.backoff.jitter_ms = scenario.candidate_jitter_ms
        adjacency[edge.source].append(edge)
    roots = nodes - {e.target for e in analysis.edges}
    entry = scenario.entry_service or (next(iter(roots)) if len(roots) == 1 else None)
    if entry not in nodes:
        raise InputError("Choose an entry service for this topology")
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise InputError("Cyclic call paths cannot be simulated in model des-1.0")
        if node in visited:
            return
        visiting.add(node)
        for e in adjacency[node]:
            visit(e.target)
        visiting.remove(node)
        visited.add(node)
    visit(entry)
    heap, seq = [], itertools.count()
    clock, events = 0.0, 0
    metrics = {n: dict(service_id=n, attempts=0, retries=0, failures=0, peak_concurrency=0, peak_queue=0,
                      busy_ms=0.0) for n in sorted(nodes)}
    active = {n: 0 for n in nodes}
    queues = {n: deque() for n in nodes}
    bins = defaultdict(lambda: [0, 0])
    counters = {"succeeded": 0, "failed": 0, "deadline_misses": 0}
    latencies, physical_counts = [], defaultdict(int)
    attempts_total, retries_total, leaf_total = 0, 0, 0
    last_work_ms = 0.0

    def schedule(at, callback, priority=0):
        if not math.isfinite(at) or len(heap) >= MAX_EVENTS:
            raise InputError("Simulation event or numeric bounds exceeded")
        heapq.heappush(heap, (at, priority, next(seq), callback))

    def physical(service, request, callback, is_retry=False, root=False):
        nonlocal attempts_total, retries_total, leaf_total
        busy_started = 0.0
        m = metrics[service]
        m["attempts"] += 1
        physical_counts[(request["id"], service)] += 1
        physical_number = physical_counts[(request["id"], service)]
        if not root:
            attempts_total += 1
            retries_total += int(is_retry)
            m["retries"] += int(is_retry)
            bucket = math.floor(clock / 100) * 100
            bins[bucket][0] += 1
            bins[bucket][1] += int(is_retry)
            if not adjacency[service]:
                leaf_total += 1

        def finish(outcome):
            nonlocal last_work_ms
            last_work_ms = max(last_work_ms, clock)
            m["busy_ms"] += clock - busy_started
            if outcome != "ok":
                m["failures"] += 1
            active[service] -= 1
            callback(outcome)
            if queues[service]:
                next_start = queues[service].popleft()
                next_start()

        def start():
            nonlocal busy_started
            busy_started = clock
            active[service] += 1
            m["peak_concurrency"] = max(m["peak_concurrency"], active[service])
            if request["deadline"] <= clock:
                schedule(clock, lambda: finish("deadline"))
                return
            delay = scenario.service_time_ms
            terminal = not adjacency[service]
            if terminal and scenario.mode == "latency":
                delay += scenario.fault_latency_ms
            if terminal and scenario.mode == "timeout":
                delay += max(scenario.fault_latency_ms, scenario.per_attempt_timeout_ms * 2)

            def processed():
                if terminal:
                    fail = (
                        scenario.mode == "intermittent"
                        and random_unit(scenario.seed, request["id"], service, physical_number, "failure") < scenario.failure_rate
                    ) or (
                        scenario.mode == "correlated" and
                        clock % 2000 < 2000 * scenario.failure_rate
                    )
                    finish("503" if fail else "ok")
                    return

                def next_edge(index, outcome="ok"):
                    if outcome != "ok" or index == len(adjacency[service]):
                        finish(outcome)
                        return
                    if clock >= request["deadline"]:
                        finish("deadline")
                        return
                    call_edge(adjacency[service][index], request, lambda result: next_edge(index + 1, result))
                next_edge(0)
            schedule(clock + delay, processed)

        if active[service] < scenario.concurrency:
            start()
        elif len(queues[service]) < scenario.queue_limit:
            queues[service].append(start)
            m["peak_queue"] = max(m["peak_queue"], len(queues[service]))
        else:
            m["failures"] += 1
            schedule(clock, lambda: callback("queue_full"))

    def call_edge(edge, request, callback):
        layers = [policies[pid] for pid in edge.policy_ids]

        def layer(index, done, inherited_retry=False):
            if index == len(layers):
                physical(edge.target, request, done, inherited_retry)
                return
            p = layers[index]
            count = 0
            category_used = defaultdict(int)
            layer_deadline = min(request["deadline"], clock + p.overall_deadline_ms) if p.overall_deadline_ms is not None else request["deadline"]
            completed = False

            def attempt():
                nonlocal count, completed
                if completed:
                    return
                if clock >= layer_deadline:
                    completed = True
                    done("deadline")
                    return
                count += 1
                token = {"settled": False}

                def settle(outcome):
                    nonlocal completed
                    if token["settled"] or completed:
                        return
                    token["settled"] = True
                    if outcome == "ok":
                        completed = True
                        done("ok")
                        return
                    cat = "read" if outcome == "timeout" else "status" if outcome.isdigit() else outcome
                    category_used[cat] += 1
                    limit = p.category_limits.get(cat)
                    may_retry = (
                        eligible(p, outcome) and count < p.max_total_attempts
                        and (limit is None or category_used[cat] <= limit)
                    )
                    if not may_retry:
                        completed = True
                        done(outcome)
                        return
                    delay = retry_delay(p, count, random_unit(scenario.seed, request["id"], edge.id, index, count, "jitter"))
                    if clock + delay >= layer_deadline:
                        completed = True
                        schedule(layer_deadline, lambda: done("deadline"), 2)
                    else:
                        schedule(clock + delay, attempt)
                timeout = p.per_attempt_timeout_ms or scenario.per_attempt_timeout_ms
                end = min(clock + timeout, layer_deadline)
                schedule(end, lambda: settle("deadline" if end == layer_deadline else "timeout"), 1)
                layer(index + 1, settle, inherited_retry or count > 1)
            attempt()
        layer(0, callback)

    def arrive(rid):
        arrival = clock
        request = {"id": rid, "deadline": arrival + scenario.deadline_ms}
        done = False

        def finish(outcome):
            nonlocal done, last_work_ms
            if done:
                return
            done = True
            last_work_ms = max(last_work_ms, clock)
            counters["succeeded" if outcome == "ok" else "failed"] += 1
            counters["deadline_misses"] += int(outcome == "deadline")
            latencies.append(clock - arrival)
        schedule(request["deadline"], lambda: finish("deadline"), 2)
        physical(entry, request, finish, root=True)

    for rid in range(scenario.requests):
        schedule(rid * 1000 / scenario.arrival_rate, lambda rid=rid: arrive(rid))
    while heap:
        clock, _, _, callback = heapq.heappop(heap)
        events += 1
        if events > MAX_EVENTS or clock > 10_000_000:
            raise InputError("Simulation exceeded its event/time budget; reduce requests or retries")
        callback()
    latencies.sort()

    def percentile(q):
        return round(latencies[max(0, math.ceil(len(latencies) * q) - 1)], 3)
    initial = attempts_total - retries_total
    for m in metrics.values():
        m["mean_occupancy"] = round(m["busy_ms"] / last_work_ms, 6) if last_work_ms else 0
        m["busy_ms"] = round(m["busy_ms"], 3)
    return dict(
        incoming_requests=scenario.requests, downstream_attempts=attempts_total,
        retry_attempts=retries_total, leaf_attempts=leaf_total,
        amplification=round(attempts_total / scenario.requests, 6),
        retry_ratio=round(retries_total / initial, 6) if initial else 0,
        **counters, p50_ms=percentile(0.5), p95_ms=percentile(0.95), p99_ms=percentile(0.99),
        duration_ms=round(last_work_ms, 3), event_count=events,
        per_service=list(metrics.values()),
        timeline=[dict(time_ms=t, attempts=v[0], retries=v[1]) for t, v in sorted(bins.items())],
        assumptions=[
            f"Model {MODEL_VERSION}: virtual-time discrete events; completion wins ties with timeout.",
            "All calls use GET. Fan-out executes sequentially in stable edge order. Cyclic call paths are rejected.",
            "Arrival intervals are fixed; service time is a scenario assumption, not extracted fact.",
            "Workers remain occupied while awaiting synchronous downstream calls; FIFO bounded queues.",
            "A timed-out physical operation continues consuming capacity; late responses cannot settle a completed attempt.",
            "Global request deadlines suppress new retries; already-started physical operations may finish late.",
            "No Retry-After headers, redirects, idempotency/deduplication, TCP or network connection-pool model.",
            "Failure and jitter draws are keyed by seed/request/attempt identity for reproducible comparisons.",
            "Correlated failures use periodic 2-second windows with the supplied failure-rate duty cycle.",
            "Amplification = all downstream physical attempts / logical incoming requests; retry ratio = retries / initial downstream attempts.",
            "These are model predictions, not a guarantee of production behavior.",
        ],
    )
