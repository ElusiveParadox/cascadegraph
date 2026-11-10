import { useGetSystemStatus, useHealthCheck } from "@workspace/api-client-react";
import { ErrorPanel, KV, LoadingBlock, PageHeader, Panel, Tag } from "@/components/common";

export default function HelpPage() {
  const s = useGetSystemStatus();
  const h = useHealthCheck();
  return (
    <>
      <PageHeader kicker="07 / scope" title="What CascadeGraph does, and does not, claim">
        A static extractor plus a deterministic simulator. It shows where retries can multiply under stated assumptions; it is not a production load test.
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Panel title="Workflow">
            <ol className="space-y-2 text-sm">
              {[
                ["Ingest", "Paste a public GitHub root URL, upload a ZIP or supported source files, or use the sample. Public snapshots are commit-pinned; missing files are requested explicitly. Private repositories require file uploads, not credentials."],
                ["Extract", "Deterministic parsers locate retry configuration and call sites, recording file, line range, excerpt and sha256 for each fact."],
                ["Normalize", "Framework counts (retries vs attempts) become max total attempts including the first call. Anything that cannot be determined is marked unknown, never guessed."],
                ["Confirm", "Reviewers confirm or correct policies (attempts, timeout, deadline, note) and confirm inferred edges with a note. Source facts are kept alongside corrections."],
                ["Simulate", "Seeded discrete-event runs over the graph. Same seed and inputs give the same output."],
                ["Report", "A JSON evidence report bundles analysis, simulations, measured validation and limitations."],
              ].map(([t, d], i) => <li key={t} className="flex gap-3"><span className="num text-primary">{String(i + 1).padStart(2, "0")}</span><div><span className="font-medium">{t}.</span> <span className="text-muted-foreground">{d}</span></div></li>)}
            </ol>
          </Panel>
          <Panel title="AI assistance">
            <p className="text-sm text-muted-foreground">Off by default. Only when you tick the opt-in checkbox for a specific analysis are source excerpts sent to the external provider, and the call is billed to your credits. The sample analysis never enables it on its own.</p>
          </Panel>
          <Panel title="Data and retention">
            <p className="text-sm text-muted-foreground">Analyses are tied to an anonymous browser session, survive reloads in that session, and expire after a short retention window. Delete removes the analysis and its simulations immediately.</p>
          </Panel>
          <Panel title="Server-declared limitations">
            {s.isLoading ? <LoadingBlock rows={2} /> : s.isError ? <ErrorPanel error={s.error} onRetry={() => s.refetch()} /> :
              <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground" data-testid="list-limitations">{s.data?.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
          </Panel>
        </div>
        <Panel title="System status" className="lg:self-start">
          {s.isLoading ? <LoadingBlock rows={2} /> : s.isError ? <ErrorPanel error={s.error} /> : s.data && (
            <dl>
              <KV k="API health">{h.isError ? <Tag tone="bad">unreachable</Tag> : <Tag tone={h.data?.status === "ok" ? "ok" : "info"}>{h.data?.status ?? "checking"}</Tag>}</KV>
              <KV k="Version"><span className="num">{s.data.version}</span></KV>
              <KV k="Model version"><span className="num">{s.data.model_version}</span></KV>
              <KV k="AI">{s.data.ai_available ? <Tag tone="warn">{s.data.ai_provider}</Tag> : <Tag>not configured</Tag>}</KV>
              <KV k="Storage"><span className="text-xs">{s.data.storage}</span></KV>
              <KV k="Max archive"><span className="num">{s.data.max_archive_mb} MiB</span></KV>
              <KV k="Max expanded"><span className="num">{s.data.max_expanded_mb} MiB</span></KV>
              <KV k="Supported source"><span className="num">{s.data.max_source_mb} MiB</span></KV>
              <KV k="Each source file"><span className="num">{s.data.max_file_kb} KiB</span></KV>
              <KV k="Direct source files"><span className="num">{s.data.max_source_files}</span></KV>
              <KV k="Max files"><span className="num">{s.data.max_files}</span></KV>
              <KV k="Parsers"><span className="flex flex-wrap justify-end gap-1">{s.data.supported_parsers.map((p) => <Tag key={p}>{p}</Tag>)}</span></KV>
            </dl>
          )}
        </Panel>
      </div>
    </>
  );
}
