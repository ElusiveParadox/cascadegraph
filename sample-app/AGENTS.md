# Sample validation boundary
This trusted code runs only in GitHub Actions or an explicitly controlled external
Docker host. Never run it through the web application or substitute user code.
Keep declared bindings aligned with the actual client call boundaries. Runtime
configuration overrides in experiments must match the simulation candidate.
Collect observations independently; never rewrite them to match predictions.
Health checks do not count as workload requests. Fault-control ports are loopback
only and must not be exposed as a production service.
