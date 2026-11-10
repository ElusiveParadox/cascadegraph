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

Deadline misses in measurements mean logical workload elapsed time at least the
declared 10-second budget; the sample does not implement distributed cancellation
at that budget. These scenarios have ample budget, so they calibrate zero misses,
not nonzero deadline/cancellation behavior. Outgoing and retry counts are derived
from independent receiving-service counters for this one-child chain.

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

## Concurrent extension (separate evidence)

The original `validation/verified-sample.json` is frozen historical evidence.
Neither the experiment nor CI replaces it. The workflow hashes it before running
and verifies the same bytes afterward. New artifacts are reviewed independently;
the application's existing six-case validation page is **not** silently promoted
to a concurrent-latency accuracy claim.

The entry point rejects execution outside this repository's GitHub-hosted Actions
environment. Compose uses an Ubuntu 24.04 ephemeral runner, non-root containers,
loopback control ports, read-only filesystems and dropped capabilities. Never
run these services on Replit, execute an uploaded repository, or substitute an
unreviewed repository/checkout for the trusted sample. The environment guard
prevents accidental local execution; it is not remote attestation or a sandbox.

### Workloads and reproducibility

After the six legacy controls, run eight concurrent scenarios with five seeds
each: 11, 42, 73, 101, 211. The 40-trial order is shuffled with a fixed 20261110
schedule seed. Every trial dispatches 24 logical requests at a nominal 50/s
(20 ms spacing), with an independent client thread available for every request.
This is an open-loop arrival schedule, not a closed-loop concurrency pool.
Scheduled offsets, actual dispatch lag, transport errors, statuses and individual
client latencies are retained. OS scheduling can delay arrivals; seed equality
does not imply identical wall-clock execution.

All three services use four FIFO worker slots and an explicit 20 ms processing
delay. A slot remains occupied through synchronous child requests, retry waits
and response handling. Pending worker admission is bounded at 500. The model
uses the same capacity, processing delay and queue bound. The original service
build contexts remain unchanged; Compose's named instrumentation build context
supplies the shared observer without changing source-to-service attribution.

Scenarios:

| Scenario | Fault | Retry alternative |
|---|---|---|
| Healthy | none | gateway fixed 50 ms; order urllib3 factor 25 ms |
| Leaf latency | extra 60 ms | same |
| Intermittent fixed | keyed 50% leaf 503s | gateway fixed; order exponential |
| Intermittent exponential | same keyed faults | gateway exponential; order exponential |
| Intermittent additive jitter | same keyed faults | exponential plus up to 40 ms additive jitter |
| No-retry alternative | same keyed 50% faults | one attempt on both edges |
| All-failing leaf | 100% leaf 503s | baseline three attempts on both edges |
| Downstream timeouts | extra 250 ms | baseline retries and real client read timeouts |

Gateway's real Tenacity attempts/waits and order's real urllib3 attempts/waits
remain in use; instrumentation does not replace them with a simulated HTTP
client. The configured runtime overrides are also applied to a deep copy of the
extracted model. Fault draws use seed/logical request/service/physical ordinal;
jitter draws use seed/logical request/edge/layer/retry ordinal. Health probes
never enter workload counters.

### Observations and comparison

Before resetting a trial, wait up to 45 seconds for **all** services' active and
queued work to reach zero, including late operations whose callers timed out.
Do not discard late work or configure another scenario while work is active.
Each service independently records:

- incoming/completed/success/failure counts, peak active workers and peak queue;
- integrated occupied-worker milliseconds, aggregate queue wait and per-request
  latency samples including admission wait;
- timestamped arrival/start/finish/outgoing/retry/cause events;
- receiving-side repeated physical requests per logical ID, distinct from
  library-level outgoing attempts and retry hooks.

The one-child chain allows independent reconciliation: gateway outgoing attempts
must equal order incoming attempts, and order outgoing attempts must equal leaf
incoming attempts. Receiving-side repeated requests count repeats across ancestor
layers. This does **not** equal the model's immediate-edge retry count: replaying
a parent call creates another initial child call. Use the immediate caller's
library retry-hook count for comparison (gateway hooks for order, order hooks
for inventory). Preserve repeated receiving-side IDs as separate raw diagnostics.
Client transport failures are recorded, not fabricated as HTTP responses.

The model now additionally exposes optional `busy_ms` and `mean_occupancy` per
service. Its busy time includes late physical work, and its denominator is the
last physical completion, not inactive deadline timers left on the event heap.
Observed mean occupancy uses the external workload horizon through drain
observation; this includes network/measurement overhead and up to one 100 ms
poll interval. Peaks and means therefore have different sensitivities.

Compare amplification, successes, deadline misses, immediate-edge retries,
logical p50/p95/p99 and each service's peak/mean occupancy, queue peak and busy
time. Keep raw client and per-service latency samples, not only percentiles.
Healthy controls must overlap, succeed without extra calls and respect capacity;
incomplete counters, failed delivery, non-draining work or send/receive count
mismatches fail the run. They are not silently excluded from successful trials.

### Uncertainty and discrepancy handling

For every metric, report the mean across five trials and a deterministic
2,000-resample percentile-bootstrap 95% interval. Also report **paired**
observed-minus-predicted errors for the same scenario/seed. Resample whole trials,
not correlated requests within a trial. These are exploratory intervals
conditional on one runner/environment, not guaranteed population coverage.
At 24 requests, nearest-rank p99 is the maximum; five trials cannot establish
stable extreme-tail performance.

Keep legacy count tolerances as the six-control gate. New concurrent count errors
over 0.5 and p95 errors over `max(50 ms, 25% of predicted p95)` are flagged for
investigation, not relabeled as agreement or corrected by editing observations.
Occupied-worker time errors over 10% and queue-peak errors over
`max(2 slots, 25% of predicted peak)` are also flagged: matching amplification
must not conceal a substantially wrong work-duration/queue prediction.
Integrity failures fail CI independently of model agreement. A successful
measurement run may expose an inaccurate model.

Known structural limits to investigate alongside measured errors:

- des-1.0 adds additive jitter on urllib3's first retry, whereas real urllib3
  skips that first wait/jitter. The real implementation preserves urllib3's
  behavior rather than changing it to improve agreement.
- Timeout-mode virtual leaf duration is service time plus
  `max(fault_latency_ms, 2 * scenario.per_attempt_timeout_ms)`. The real leaf
  sleeps only its declared fault delay plus processing time. Both keep timed-out
  work alive, but their occupied time and resulting queues can differ substantially.
- Real HTTP read/connect timeouts, scheduler overhead and accept/transport queues
  are not identical to virtual timers, FIFO workers or completion-wins-ties.
- The real sample has no distributed deadline cancellation. A measured deadline
  miss means client elapsed latency at least 10 seconds; the simulator suppresses
  new work at its logical deadline. Do not treat zero measured misses as proof
  of correct nonzero deadline/cancellation behavior.
- Correlated outage windows, heterogeneous capacities, external connection pools,
  production traces and between-runner variability remain uncalibrated.

Artifacts: `validation.json` / `raw-validation.json` retain the legacy controls;
`concurrent-validation.json` contains uncertainty and discrepancy summaries;
`raw-concurrent-validation.json` contains every completed trial's independent
observations, predictions and inputs. Container image IDs are retained separately.
The metadata identifies source commit, actual workflow run, model version,
Python/library versions and runner image. Interrupted runs are marked incomplete.
Review repository, source commit, workflow path, hosted runner and successful
conclusion before describing a dataset as trusted measured evidence.
