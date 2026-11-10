# Trusted sample evidence

`verified-sample.json` is the small safe display bundle reviewed from the successful
**Real Compose validation** workflow for its exact recorded commit. Case names
and every numeric field match the downloaded artifact; only the display detail
adds limitations. The source `raw-validation.json` remains a workflow artifact.

Provenance review: repository/feature branch, successful experiment job, exact
head SHA, workflow URL, artifact name, six cases, independent raw service counters,
comparison gates and no source/credentials in the artifact. This bundle does not
verify user uploads or later candidate scenarios.

To replace it, download a successful trusted run through the authorized GitHub
proxy, compare raw observations with summary metrics, record exact provenance and
review the diff in a PR. Do not accept metrics sent through the public web app.
