# Active work

| ID | Priority | Phase | Work | Depends on | Status | Acceptance |
|---|---|---|---|---|---|---|
| CG-CORE | P0 | 1 | Safe ingestion, parsers, normalization, graph | foundation | DONE | 52 Python tests include supported semantics, hostile inputs, ownership and simulation |
| CG-SIM | P0 | 1 | Deterministic simulation, comparisons and report | CG-CORE | DONE | Seeded outputs, retry/deadline tests and desktop/phone browser journeys pass |
| CG-AI | P0 | 1 | Real provider and evidence validation | CG-CORE | DONE | Actual provider extraction succeeded; mock only in automated tests |
| CG-VALIDATE | P0 | 2 | Three-service experiment and CI | CG-SIM | DONE | Six actual GitHub Actions scenarios compared with independent predictions |
| CG-RELEASE | P0 | 3 | Security, documentation and release | CG-VALIDATE | USER GATE | Implementation checks and docs complete; publication needs user approval |
| CG-FEEDBACK | P1 | 2 | Test with 3–5 campus developers | CG-SIM | BLOCKED | Actual participants provide feedback; none recruited yet |
