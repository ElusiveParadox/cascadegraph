# Active work

Current user-requested work: add Google, GitHub and email sign-in, replace the
technical sidebar footer with account controls, and verify sign-out and
account/guest history isolation. Keep the public guest workbench usable.

| ID | Priority | Phase | Work | Depends on | Status | Acceptance |
|---|---|---|---|---|---|---|
| CG-CORE | P0 | 1 | Safe ingestion, parsers, normalization, graph | foundation | DONE | 52 Python tests include supported semantics, hostile inputs, ownership and simulation |
| CG-SIM | P0 | 1 | Deterministic simulation, comparisons and report | CG-CORE | DONE | Seeded outputs, retry/deadline tests and desktop/phone browser journeys pass |
| CG-AI | P0 | 1 | Real provider and evidence validation | CG-CORE | DONE | Actual provider extraction succeeded; mock only in automated tests |
| CG-VALIDATE | P0 | 2 | Three-service experiment and CI | CG-SIM | DONE | Six actual GitHub Actions scenarios compared with independent predictions |
| CG-RELEASE | P0 | 3 | Security, documentation and release | CG-VALIDATE | USER GATE | Implementation checks and docs complete; publication needs user approval |
| CG-FEEDBACK | P1 | 2 | Test with 3–5 campus developers | CG-SIM | BLOCKED | Actual participants provide feedback; none recruited yet |
| CG-SOURCE | P0 | 3 | Public repository URL, larger ZIPs and source-file fallback | CG-CORE | DONE | 86 Python tests and real URL-only browser journey pass; protected CI requires desktop/phone source and existing workflow checks |
| CG-STORAGE | P0 | 3 | Bound storage outage latency | CG-CORE | DONE | Shared finite process admission, hard deadlines, safe uncertain writes, isolated outage/cancellation/recovery tests |
| CG-HISTORY-RETRY | P1 | 3 | Space history reads during storage outages | CG-STORAGE | DONE | Retry-After minimum, jitter/caps, finite retries, no uncertain-session or mutation replay; focused frontend checks |
| CG-DESKTOP-ACCESS | P1 | 3 | Catch desktop layout and keyboard-access regressions | CG-SOURCE | DONE | Wide/compact/200%-zoom-equivalent browser assertions cover intake, skip navigation, visible focus, active pages and local overflow; existing ownership workflows retained |
| CG-NAV-FOCUS | P1 | 3 | Contain keyboard focus in compact navigation | CG-DESKTOP-ACCESS | DONE | Expanded/control announcements, bidirectional focus loop, Escape/toggle/link dismissal and focus return; desktop resize removes the trap |
| CG-FILE-DROP | P1 | 3 | Drag repository archives and source files into the workbench | CG-SOURCE | DONE | Shared drop feedback, atomic selection validation against server limits, retained path editing and explicit submission; desktop/phone keyboard and rejection checks |
| CG-FOLDER-INTAKE | P1 | 3 | Select or drop repository folders without retyping nested paths | CG-FILE-DROP | DONE | Optional native folder picker and bounded batched directory discovery; skipped-entry reporting, atomic source limits and nested-path checks; individual-file picker and explicit submission retained |
| CG-SOURCE-CONFLICTS | P1 | 3 | Resolve repeated source paths before adding a batch | CG-FOLDER-INTAKE | DONE | Explicit keep-existing, replace and cancel choices; edited paths and unaffected files retained; resolved source limits and explicit Analyze enforced; focused single-file and nested-folder checks |
