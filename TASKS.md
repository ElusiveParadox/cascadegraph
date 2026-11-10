# Active work

| ID | Priority | Phase | Work | Depends on | Status | Acceptance |
|---|---|---|---|---|---|---|
| CG-CORE | P0 | 1 | Safe ingestion, parsers, normalization, graph | foundation | IN PROGRESS | Sample/archive source-backed extraction and hostile input tests pass |
| CG-SIM | P0 | 1 | Deterministic simulation, comparisons and report | CG-CORE | TODO | Seeded outputs, retry/deadline tests and end-to-end UI flow pass |
| CG-AI | P0 | 1 | Real provider and evidence validation | CG-CORE | TODO | Actual sample extraction verified; mock only in tests |
| CG-VALIDATE | P0 | 2 | Three-service experiment and CI | CG-SIM | TODO | Actual GitHub Actions measurements compared with predictions |
| CG-RELEASE | P0 | 3 | Security, documentation and release | CG-VALIDATE | TODO | Checks pass; user approves publication |
| CG-FEEDBACK | P1 | 2 | Test with 3–5 campus developers | CG-SIM | BLOCKED | Actual participants provide feedback; none recruited yet |
