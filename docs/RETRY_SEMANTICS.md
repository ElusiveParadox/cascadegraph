# Normalized retry semantics

`max_total_attempts` always includes the first call:
- Tenacity `stop_after_attempt(3)` → three total attempts.
- urllib3 `Retry(total=2)` → at most three total attempts. Connect, read and status
  retry budgets, allowed methods and status-forcelist remain separate constraints.
- Istio `attempts: 2` → two retries / three total attempts.

Never erase `source_semantics`, `source_value` or source evidence when a user
confirms/corrects a policy. Corrections have reviewer notes and are distinct from
source facts. Earlier simulation snapshots do not change.

Supported waits are fixed and bounded exponential configurations; urllib3's
first retry wait is zero, with subsequent exponential delays. Jitter is seeded
and bounded. Unsupported expressions and implicit mesh backoff remain unknown,
not silently converted into zero wait. Multiple bound wrappers nest in explicit
manifest order.

An attempt timeout limits one client wait. An overall policy deadline limits
its retry operation; the scenario deadline limits the logical request. Source
timeout/deadline values take precedence over scenario fallback values. A timeout
does not imply physical downstream work stopped.
