# Measured validation protocol

Only the committed sample runs in Docker Compose on an ephemeral GitHub-hosted
Ubuntu runner. The product never executes an uploaded repository.

1. Freeze the commit, scenario inputs, library versions and model version.
2. Validate Compose, build non-root containers, and wait for all health checks.
3. Reset service counters before each scenario; health traffic is excluded.
4. Run ten sequential logical requests with stable logical request IDs.
5. Collect gateway outcomes, order/inventory physical HTTP counts and latencies.
6. Independently simulate equivalent policies/faults at low load with a 5-second
   fixed inter-arrival interval (no overlapping requests). Measured requests are
   sequential, not an exact reproduction of this arrival clock.
7. Compare all downstream attempts / logical requests and successful outcomes.
8. Preserve raw measurements, simulation assumptions, scenario, commit and workflow
   run URL. Never rewrite measured values to improve agreement.
9. Upload safe JSON and always tear down containers/networks.

Scenarios: healthy, 60ms leaf latency, keyed intermittent 503s, all-failing leaf,
one-attempt/no-retry alternative, and 250ms downstream latency causing read timeouts.
Jitter and correlated failure behavior have deterministic engine tests; their
real-system calibration is not claimed by these six count-focused experiments.

Gateway has three Tenacity total attempts with fixed 50ms wait; order has two
urllib3 retries (three total attempts), 25ms backoff factor and 100ms per-attempt
read timeout; gateway's client timeout is 500ms. Retry category budgets and GET
eligibility are retained. The unbound Istio example and optional custom-loop
alternative are extraction fixtures, not extra active retries in the default
sample topology.

The acceptance tolerance is at most 0.5 absolute downstream-amplification error
and one logical-success discrepancy per ten requests. This is not a latency
accuracy assertion. All-failing healthy-timeout-free nested retries should match
the exact count arithmetic. Timing-dependent scenarios may differ because the
model omits real scheduler and transport details. A single repetition is only
an initial calibration, not a statistical benchmark.

Measured artifacts can be reviewed and bundled by a maintainer after verifying
repository, workflow, successful conclusion, commit and artifact contents.
There is deliberately no public endpoint that labels an arbitrary JSON upload
as trusted measurements. Bundled measurements describe the sample only, not
an uploaded application or a changed candidate policy.
