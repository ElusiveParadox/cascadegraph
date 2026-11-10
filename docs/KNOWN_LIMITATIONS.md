# Known limitations

- Supported syntax only: literal Tenacity stop/wait/exception configurations,
  literal urllib3 retry counts/category budgets/methods/statuses, Istio retry
  fields, Compose services and explicit call declarations.
- Complex dynamic Python expressions, unbounded stops, tuple timeouts, arbitrary
  custom retry predicates, unsupported mesh defaults and opaque helpers remain
  unresolved. Backoff/condition/count unknowns block bound-policy simulation.
- Public GitHub root URLs, ZIPs and supported individual source files are accepted.
  Private GitHub credential access is not enabled; upload the relevant files/ZIP.
  Downloads are pinned to a commit and never follow redirects or execute source.
  Large repositories can exceed the whole-snapshot download/entry limits even
  when a small project folder is selected; upload a relevant subset instead.
- General HTTP call inference, Kubernetes support and trace import are excluded.
  Startup dependencies and shared networks never become request edges.
- Custom AI extraction supports the bundled `custom_retry_request` pattern, not
  arbitrary code. It can fail; deterministic analysis remains available.
- Graphs may retain cycles, but simulation rejects cyclic reachable call paths
  explicitly. Fan-out is sequential, workload arrivals are fixed interval, service
  times are scenario assumptions, and queues are a simplified blocking model.
- Source timeouts override scenario fallback per-attempt timeouts. Deadlines and
  backoff cannot be interpreted as guarantees of production cancellation.
- No Retry-After headers, redirects, TCP, connection-pool contention, deduplication,
  request idempotency inference or production safety score.
- Single-process rate limiting and job bounds are suitable for a bounded demo,
  not a horizontally scaled abuse-control system.
- Anonymous cookie sessions do not provide account recovery or private-team
  collaboration. SQLite and bundled files are not durable writable production
  storage. Export reports; analyses expire after 24 hours.
- Real CI validation is low-load, six-scenario, count-focused sample calibration.
  It is not measurement of user uploads, jitter calibration, a statistical latency
  benchmark, or proof against real production cascades.
- Production publication and testing with real campus developers require the
  user's participation; neither is represented as already completed.
