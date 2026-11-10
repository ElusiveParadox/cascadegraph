# Controlled validation sample
Gateway → order → inventory communicate over the Compose network. Tenacity and
urllib3 implement real supported retry policies. `order/custom_retry.py` is an
optional alternate call implementation and the opt-in AI extraction fixture.
`cascadegraph.yaml` declares call boundaries; Compose depends_on is startup only.

Run only trusted sample code with `docker compose -f sample-app/compose.yaml up
--build --wait -d` on an isolated development Linux host/GitHub runner, then
`uv run --frozen python sample-app/experiment.py`. Always tear down with `down
--volumes`. Do not expose the sample `/configure` endpoints publicly.

The experiment controls latency and keyed failures, collects independent counters
and records exact provenance. See `docs/VALIDATION_PROTOCOL.md` before interpreting
results. Real service times and logical arrival timing are not claimed to match
the simplified simulator exactly.
