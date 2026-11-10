import asyncio

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cascadegraph_runtime.analysis import analyze
from cascadegraph_runtime.models import Backoff, DependencyEdge, Policy, Scenario, ServiceNode
from cascadegraph_runtime.security import InputError, sample_files
from cascadegraph_runtime.simulation import retry_delay, simulate


@pytest.fixture
def analysis():
    return asyncio.run(analyze(sample_files(), "sample", "sample"))


def test_healthy_and_reproducible(analysis):
    scenario = Scenario(requests=10)
    assert simulate(analysis, scenario) == simulate(analysis, scenario)
    r = simulate(analysis, Scenario(mode="healthy", requests=10))
    assert r["succeeded"] == 10
    assert r["retry_attempts"] == 0
    assert r["amplification"] == 2


def test_five_hops_three_total_attempts_is_243_leaf_attempts(analysis):
    # Five nested retrying boundaries; every call fails, all attempts reach leaf,
    # no cutoff, queue suppression, sharing or deduplication.
    analysis.nodes = [ServiceNode(id=str(i), name=str(i)) for i in range(6)]
    analysis.edges, analysis.policies = [], []
    for i in range(5):
        p = Policy(id=f"p{i}", framework="tenacity", symbol=f"f{i}", source_semantics="total_attempts",
                   max_total_attempts=3, retry_on=["503"], backoff=Backoff(kind="none", delay_ms=0))
        analysis.policies.append(p)
        analysis.edges.append(DependencyEdge(id=str(i), source=str(i), target=str(i+1),
                              evidence_kind="explicit_topology", policy_ids=[p.id]))
    r = simulate(analysis, Scenario(mode="intermittent", requests=1, failure_rate=1,
                                    service_time_ms=1, per_attempt_timeout_ms=10000, deadline_ms=60000))
    assert r["leaf_attempts"] == 243
    assert r["downstream_attempts"] == sum(3**n for n in range(1, 6))


def test_no_retries_candidate(analysis):
    s = Scenario(mode="intermittent", requests=5, failure_rate=1, candidate_attempts=1)
    base, candidate = simulate(analysis, s), simulate(analysis, s, candidate=True)
    assert base["leaf_attempts"] == 45
    assert candidate["leaf_attempts"] == 5
    assert candidate["downstream_attempts"] == 10


def test_deadlines_and_timeouts(analysis):
    s = Scenario(mode="latency", requests=5, fault_latency_ms=1000, deadline_ms=40)
    r = simulate(analysis, s)
    assert r["deadline_misses"] == 5 and r["succeeded"] == 0
    assert r["p95_ms"] == 40


def test_conditions_methods_categories(analysis):
    order = next(p for p in analysis.policies if p.framework == "urllib3")
    order.category_limits["status"] = 0
    r = simulate(analysis, Scenario(mode="intermittent", requests=1, failure_rate=1))
    assert r["leaf_attempts"] == 3  # gateway retries, order does not
    order.category_limits.clear()
    order.allowed_methods = ["POST"]
    r = simulate(analysis, Scenario(mode="intermittent", requests=1, failure_rate=1))
    assert r["leaf_attempts"] == 3


def test_cycles_and_unknowns_explicit(analysis):
    analysis.edges.append(DependencyEdge(id="cycle", source="inventory", target="gateway",
                                        evidence_kind="explicit_topology", policy_ids=[analysis.policies[0].id]))
    with pytest.raises(InputError, match="Cyclic"):
        simulate(analysis, Scenario(entry_service="gateway"))
    analysis.edges.pop()
    analysis.policies[0].max_total_attempts = None
    with pytest.raises(InputError, match="unresolved"):
        simulate(analysis, Scenario())


def test_urllib3_wait_sequence():
    p = Policy(id="p", framework="urllib3", symbol="x", source_semantics="retries_after_initial",
               backoff=Backoff(kind="exponential", delay_ms=25))
    assert [retry_delay(p, n, 0) for n in [1, 2, 3]] == [0, 50, 100]


@given(st.integers(min_value=0, max_value=10000))
def test_jitter_bounds(seed):
    p = Policy(id="p", framework="tenacity", symbol="x", source_semantics="total_attempts",
               backoff=Backoff(kind="exponential", delay_ms=50, jitter_ms=25))
    assert 50 <= retry_delay(p, 1, seed / 10000) <= 75


def test_seed_changes_stochastic_outcomes(analysis):
    a = simulate(analysis, Scenario(seed=2))
    b = simulate(analysis, Scenario(seed=7))
    assert a != b


def test_capacity_and_queue_metrics(analysis):
    r = simulate(analysis, Scenario(mode="healthy", requests=20, arrival_rate=100,
                                    concurrency=1, queue_limit=1))
    assert r["succeeded"] + r["failed"] == 20
    assert all(m["peak_concurrency"] <= 1 and m["peak_queue"] <= 1 for m in r["per_service"])
