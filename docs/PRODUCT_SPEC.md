# Product specification
CascadeGraph helps backend/platform engineers inspect nested retry policies before
deployment. Its MVP outcome is source-backed extraction, an honest call graph,
reproducible baseline/candidate simulations and sample-only measured calibration.

Primary journey: bundled sample or ZIP → graph/evidence → policy review →
scenario → baseline/candidate comparison → downloadable JSON report.
Analyses are owned by one anonymous browser session and can be deleted.
Unknowns and assumptions are visible; unresolved bound policies block simulation.

Success means testable extraction semantics and measured experiment agreement
within declared tolerances, not a universal production safety score.
The tool does not edit repositories, run uploads, or replace observability,
runtime retry controls or chaos experiments. See KNOWN_LIMITATIONS.md for scope.
