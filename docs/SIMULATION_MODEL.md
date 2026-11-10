# Discrete-event model

Stable heap events advance virtual milliseconds. At equal timestamps completion
is processed before timeout/deadline. Sequence numbers stabilize other ties.
The core has no HTTP, database, LLM, wall-clock or global random dependency.
Seeded SHA-derived choices key failures and jitter by logical request, service
and attempt rather than consuming a variable-length global random stream.

Fixed-interval arrivals enter a selected service. Each service has scenario
worker capacity and a bounded FIFO queue. A worker holds its slot while awaiting
sequential downstream calls. A full queue rejects work. Retry wrappers honor
eligible outcomes, total/category budgets, timeout, overall deadline and backoff.
Retries cannot start beyond the remaining logical/policy deadline. Timed-out
physical work can continue; a late result cannot settle an already-failed call.

Leaf faults support healthy, added latency, timeout, independent keyed intermittent
failures and time-window-correlated failures. Cyclic reachable call paths are
rejected. Fan-out is sequential, not parallel. Source-model unknowns block bound
policies instead of inventing values.

Reports expose logical outcomes, physical downstream/leaf attempts, amplification
(all downstream attempts / incoming logical requests), retry ratio, latency
percentiles, per-service work/retries/queue peaks and timeline bins. This aggregate
amplification is not the same as leaf-only `3^depth`. A hypothetical fully failing
five-retrying-hop chain with three attempts at every hop has 243 leaf attempts,
only when deadlines, capacity and eligibility do not truncate it.

Results are deterministic predictions under these assumptions, not calibrated
models of DNS, TLS, operating-system scheduling or transport cancellation.
