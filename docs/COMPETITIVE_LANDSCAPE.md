# Verified related work

Reviewed 2026-11-10. These are descriptions of primary sources, not reproduced
competitor benchmarks or claims of CascadeGraph superiority. Read scope and
assumptions before comparing results. CascadeGraph is not the first retry analyzer
and is not a production retry-control mechanism.

| Approach | Verified capability and evidence | Relationship to CascadeGraph |
|---|---|---|
| RetryGuard | The abstract and introduction of arXiv:2511.23278v2 describe distributed, per-service runtime retry suppression when retries become counterproductive during sustained service miscoordination. The work includes analytical modelling, simulation and Kubernetes/Istio experiments. | Overlap: retry amplification and policy interaction. Difference: CascadeGraph inspects supported repository source before deployment and offers limited what-if analysis; it does not implement RetryGuard's detection/control or establish comparable performance. |
| DiffTry | arXiv:2610.20567v1, “Prioritizing Microservice Requests via Retries,” defines differential class-specific retry limits as stateless distributed rejection prioritization. Its abstract/introduction describe analytical tandem/network models, simulation and a live service-mesh deployment. | CascadeGraph does not implement traffic classes, prioritization, DiffTry's analytical guarantees or its plugin. Configurable attempt limits are a narrower what-if input, not equivalent DiffTry support. |
| Chaos engineering | Principles of Chaos Engineering describes hypothesis-driven controlled experiments on running systems, steady-state metrics and minimized blast radius. It explicitly discusses retry-storm weaknesses. | The committed sample experiment is a small controlled fault test; offline source inspection and simulation complement, not replace, actual running-system experiments. No user production faults are injected. |
| Envoy runtime retries/budgets | The current HTTP routing documentation describes retry conditions, exponential/feedback backoff, overall timeout containment and budgets limiting active retries. Circuit-breaker configuration documents runtime configurable retry budgets. | Runtime mechanisms enforce real traffic limits. CascadeGraph extracts a narrow Istio configuration subset, does not model shared Envoy budgets, and keeps unresolved proxy defaults unknown. |
| Retry/backoff engineering | AWS Builders' Library explains retries increasing load, timeout tradeoffs, idempotency and jitter. | These established techniques motivate candidate scenarios. CascadeGraph cannot infer side-effect safety or recommend a candidate without showing modeled consequences. |
| Metastability research | Bronson et al., HotOS 2021, “Metastable Failures in Distributed Systems,” defines trigger and sustaining feedback, including retry work amplification that prevents recovery after a trigger disappears. | CascadeGraph's finite-horizon queues and controlled failure scenarios can illustrate amplification, but do not establish general metastable-state detection or recovery guarantees. |

## Sources and research notes
- RetryGuard abstract/version: https://arxiv.org/abs/2511.23278 ; reviewed v2
  introduction: https://arxiv.org/html/2511.23278v2 . Authors' benchmark claims
  have not been independently reproduced here.
- DiffTry abstract/version: https://arxiv.org/abs/2610.20567 ; reviewed v1
  introduction and class-specific retry description:
  https://arxiv.org/html/2610.20567v1 .
- Chaos principles: https://principlesofchaos.org/ .
- Envoy retry semantics:
  https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/http/http_routing.html .
- Envoy runtime budget example:
  https://www.envoyproxy.io/docs/envoy/latest/configuration/upstream/cluster_manager/cluster_circuit_breakers.html .
- AWS: https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ .
- HotOS 2021 paper, introduction and request-retry case study:
  https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf .

## Uncertainty and positioning
This is a focused review of primary abstracts, introductions, documented mechanisms
and one metastability case study—not a systematic literature review, exhaustive
product survey or independent benchmark. Runtime library/mesh versions and paper
revisions can change. No absence-of-feature claim about other tools is inferred
from absence in these passages.

The demonstrated product distinction is the combination of bounded repository-aware
source evidence, inspectable normalized policies, deterministic what-if simulation
and independently measured calibration on one committed three-service sample.
Its supported syntax, finite model and low-load experiments remain significantly
narrower than general production reliability analysis.
