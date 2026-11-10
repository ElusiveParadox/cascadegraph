import { useEffect } from "react";
import { Link, useParams } from "wouter";
import { RotateCcw } from "lucide-react";
import { getGetSimulationQueryKey, useGetSimulation, type SimulationResult } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorPanel, KV, LoadingBlock, PageHeader, Panel, Tag } from "@/components/common";
import { PerServiceTable, ResultsTable, TimelineTable } from "@/components/results-table";
import { fmtDate, fmtNum, writeSelection } from "@/lib/workspace";

function Headline({ label, r, tone }: { label: string; r: SimulationResult; tone: string }) {
  return (
    <div className={`rounded-md border p-4 ${tone}`}>
      <div className="num text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-baseline gap-2"><span className="num font-display text-4xl font-bold" data-testid={`text-amplification-${label.toLowerCase()}`}>{fmtNum(r.amplification, 2)}×</span><span className="text-xs text-muted-foreground">amplification</span></div>
      <div className="num mt-2 grid grid-cols-3 gap-2 text-xs">
        <div><div className="text-muted-foreground">ok / fail</div>{r.succeeded} / {r.failed}</div>
        <div><div className="text-muted-foreground">deadline miss</div>{r.deadline_misses}</div>
        <div><div className="text-muted-foreground">p99</div>{fmtNum(r.p99_ms)} ms</div>
      </div>
    </div>
  );
}

export default function ComparisonPage() {
  const { id } = useParams<{ id: string }>();
  const q = useGetSimulation(id, { query: { enabled: !!id, queryKey: getGetSimulationQueryKey(id) } });
  useEffect(() => { if (q.data) writeSelection({ analysisId: q.data.analysis_id, simulationId: q.data.id }); }, [q.data]);
  if (q.isLoading) return <LoadingBlock rows={5} />;
  if (q.isError) return (q.error as { status?: number })?.status === 404
    ? <EmptyState title="Simulation not found" action={<Button asChild variant="outline"><Link href="/">Back to overview</Link></Button>}>It may have expired with its analysis.</EmptyState>
    : <ErrorPanel error={q.error} onRetry={() => q.refetch()} />;
  const s = q.data;
  if (!s) return null;
  const sc = s.scenario;
  const assumptions = Array.from(new Set([...s.baseline.assumptions, ...(s.candidate?.assumptions ?? [])]));
  return (
    <>
      <PageHeader kicker={`04 / comparison · model ${s.model_version}`} title={sc.name}
        actions={<Button asChild size="sm" variant="outline"><Link href={`/simulation/${s.analysis_id}`} data-testid="link-new-scenario"><RotateCcw className="mr-1.5 h-4 w-4" />New scenario</Link></Button>}>
        <span className="num text-xs">{sc.mode} · seed {sc.seed} · {sc.requests} req @ {sc.arrival_rate}/s · entry {sc.entry_service ?? "auto"} · {fmtDate(s.created_at)}</span>
      </PageHeader>
      <div className={`grid gap-4 ${s.candidate ? "md:grid-cols-2" : ""}`}>
        <Headline label="Baseline" r={s.baseline} tone="border-border bg-card" />
        {s.candidate ? <Headline label="Candidate" r={s.candidate} tone="border-primary/40 bg-primary/5" /> : null}
      </div>
      {!s.candidate && <div className="rounded-sm border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">No candidate policy was set for this run, so only the baseline is shown. Set candidate attempts in a new scenario to compare.</div>}
      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <Panel title="Results" meta="deterministic for this seed"><ResultsTable baseline={s.baseline} candidate={s.candidate} /></Panel>
        <Panel title="Scenario inputs">
          <dl>{Object.entries(sc).map(([k, val]) => <KV key={k} k={k}><span className="num text-xs">{val === null || val === undefined ? "null" : String(val)}</span></KV>)}</dl>
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Per service · baseline"><PerServiceTable result={s.baseline} label="baseline" /></Panel>
        {s.candidate && <Panel title="Per service · candidate"><PerServiceTable result={s.candidate} label="candidate" /></Panel>}
        <Panel title="Timeline · baseline"><TimelineTable result={s.baseline} /></Panel>
        {s.candidate && <Panel title="Timeline · candidate"><TimelineTable result={s.candidate} /></Panel>}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Policy snapshot" meta={`${s.policies.length} at run time`}>
          {s.policies.length ? <table className="w-full text-xs"><thead><tr className="text-left text-[10.5px] uppercase tracking-wider text-muted-foreground"><th className="py-1 font-medium">Policy</th><th className="font-medium">Attempts</th><th className="font-medium">Backoff</th><th className="font-medium">State</th></tr></thead>
            <tbody>{s.policies.map((p) => <tr key={p.id} className="border-t border-dashed border-border"><td className="num py-1">{p.symbol}</td><td className="num">{p.max_total_attempts ?? "unknown"}</td><td className="num">{p.backoff.kind}{p.backoff.delay_ms !== null ? ` ${p.backoff.delay_ms}ms` : ""}</td><td>{p.confirmed ? <Tag tone="ok">confirmed</Tag> : <Tag tone="warn">extracted</Tag>}</td></tr>)}</tbody></table>
            : <p className="text-xs text-muted-foreground">No policies were in effect.</p>}
        </Panel>
        <Panel title="Model assumptions">{assumptions.length ? <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">{assumptions.map((a) => <li key={a}>{a}</li>)}</ul> : <p className="text-xs text-muted-foreground">None reported.</p>}</Panel>
      </div>
      <div className="flex gap-2"><Button asChild variant="outline" size="sm"><Link href={`/reports/${s.analysis_id}`} data-testid="link-report">Open evidence report</Link></Button></div>
    </>
  );
}
