"""Reporting/model tests only: never start sample services or real HTTP workloads."""

import asyncio
import importlib.util
from pathlib import Path

import pytest

from cascadegraph_runtime.analysis import analyze
from cascadegraph_runtime.models import Scenario
from cascadegraph_runtime.security import sample_files
from cascadegraph_runtime.simulation import simulate

SPEC = importlib.util.spec_from_file_location("calibration_report",
    Path(__file__).resolve().parents[1] / "sample-app/calibration_report.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def test_nearest_rank_latency_distribution_keeps_tail_and_count():
    assert report.distribution([40, 10, 30, 20]) == dict(
        n=4, p50_ms=20, p95_ms=40, p99_ms=40, min_ms=10, max_ms=40, mean_ms=25)
    with pytest.raises(ValueError):
        report.distribution([])


def test_bootstrap_uses_repeated_trials_and_is_reproducible():
    assert report.interval([7] * 5) == dict(n_trials=5, mean=7, bootstrap_ci95=[7, 7])
    assert report.interval([1, 2, 4, 8, 16]) == report.interval([1, 2, 4, 8, 16])
    with pytest.raises(ValueError):
        report.interval([7])


def test_summary_reports_paired_errors_and_known_model_limits_without_fitting():
    trials = [dict(name="controlled", seed=seed, jitter_ms=40, scenario={"mode": "timeout"},
                   observed={"amplification": 3, "p95_ms": 300, "gateway.peak_queue": 1},
                   predicted={"amplification": 2, "p95_ms": 100, "gateway.peak_queue": 0})
              for seed in [11, 42, 73, 101, 211]]
    result = report.summarize(trials)[0]
    assert result["comparisons"]["amplification"]["paired_error"]["mean"] == 1
    assert result["comparisons"]["p95_ms"]["paired_error"]["mean"] == 200
    assert len(result["discrepancy_flags"]) == 2
    assert any("first retry" in note for note in result["investigation"])
    assert trials[0]["observed"]["amplification"] == 3


def test_model_integrates_worker_occupancy_without_deadline_timer_padding():
    analysis = asyncio.run(analyze(sample_files(), "Static trusted source", "sample"))
    result = simulate(analysis, Scenario(mode="healthy", requests=2, arrival_rate=100,
                                        concurrency=1, service_time_ms=20, deadline_ms=10000))
    services = {item["service_id"]: item for item in result["per_service"]}
    assert result["duration_ms"] == 120
    assert services["gateway"]["busy_ms"] == 120
    assert services["order"]["busy_ms"] == 80
    assert services["inventory"]["busy_ms"] == 40
    assert services["gateway"]["mean_occupancy"] == 1
    assert services["gateway"]["peak_queue"] == 1
    assert services["inventory"]["mean_occupancy"] == pytest.approx(1 / 3, abs=1e-6)
