import { Link, useParams } from "wouter";
import { Download } from "lucide-react";
import { getGetReportQueryKey, useGetReport } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorPanel, KV, LoadingBlock, PageHeader, Panel, Tag, Unknown, severityTone } from "@/components/common";
import { ValidationView } from "@/components/validation-view";
import { fmtDate, fmtNum } from "@/lib/workspace";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const q = useGetReport(id, { query: { enabled: !!id, queryKey: getGetReportQueryKey(id) } });
  if (q.isLoading) return <LoadingBlock rows={5} />;
  if (q.isError) return <ErrorPanel error={q.error} onRetry={() => q.refetch()} title="Could not build report" />;
  const r = q.data;
  if (!r) return null;
  const a = r.analysis;
  const download = () => {
    const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `cascadegraph-report-${a.id.slice(0, 8)}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <>
      <PageHeader kicker={`report · schema ${r.schema_version}`} title={`Evidence report: ${a.name}`}
        actions={<Button size="sm" onClick={download} data-testid="button-download-report"><Download className="mr-1.5 h-4 w-4" />Download JSON</Button>}>
        <span className="num text-xs">generated {fmtDate(r.generated_at)} · fingerprint {a.fingerprint.slice(0, 16)}</span>
      </PageHeader>
      <Panel title="Policies" meta={`${a.policies.filter((p) => p.confirmed).length} / ${a.policies.length} confirmed`}>
        {a.policies.length ? <div className="overflow-x-auto"><table className="w-full text-xs">
          <thead><tr className="text-left text-[10.5px] uppercase tracking-wider text-muted-foreground"><th className="py-1.5 font-medium">Policy</th><th className="font-medium">Source</th><th className="font-medium">Total attempts</th><th className="font-medium">First evidence</th><th className="font-medium">Unresolved</th><th className="font-medium">State</th></tr></thead>
          <tbody>{a.policies.map((p) => (
            <tr key={p.id} className="border-t border-dashed border-border align-top">
              <td className="py-1.5 pr-2"><Link href={`/policies/${a.id}?policy=${encodeURIComponent(p.id)}`} className="num hover:text-primary">{p.symbol}</Link><div className="text-muted-foreground">{p.framework}</div></td>
              <td className="num pr-2">{p.source_semantics} = {p.source_value ?? "?"}</td>
              <td className="num pr-2">{p.max_total_attempts ?? <Unknown />}</td>
              <td className="num pr-2">{p.evidence[0] ? `${p.evidence[0].path}:${p.evidence[0].line_start}` : <Unknown>none</Unknown>}</td>
              <td className="pr-2">{p.unresolved.length ? p.unresolved.join("; ") : "none"}</td>
              <td>{p.confirmed ? <Tag tone="ok">confirmed</Tag> : <Tag tone="warn">extracted</Tag>}</td>
            </tr>))}</tbody></table></div> : <p className="text-sm text-muted-foreground">No policies extracted.</p>}
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Findings">{a.findings.length ? <ul className="space-y-2">{a.findings.map((f, i) => <li key={i} className="text-sm"><Tag tone={severityTone(f.severity)}>{f.severity}</Tag> <span className="font-medium">{f.title}</span><div className="text-xs text-muted-foreground">{f.detail}</div></li>)}</ul> : <p className="text-sm text-muted-foreground">None.</p>}</Panel>
        <Panel title="Graph"><dl><KV k="Services">{a.nodes.length}</KV><KV k="Edges">{a.edges.length}</KV><KV k="Confirmed edges">{a.edges.filter((e) => e.confirmed).length}</KV><KV k="Files analyzed">{a.file_count}</KV></dl></Panel>
      </div>
      <Panel title="Simulations" meta={r.simulations.length}>
        {r.simulations.length ? <div className="overflow-x-auto"><table className="w-full text-xs">
          <thead><tr className="text-left text-[10.5px] uppercase tracking-wider text-muted-foreground"><th className="py-1.5 font-medium">Scenario</th><th className="font-medium">Seed</th><th className="text-right font-medium">Baseline amp.</th><th className="text-right font-medium">Candidate amp.</th><th className="text-right font-medium">Baseline failed</th><th className="text-right font-medium">Candidate failed</th></tr></thead>
          <tbody>{r.simulations.map((s) => <tr key={s.id} className="border-t border-dashed border-border">
            <td className="py-1.5"><Link href={`/comparison/${s.id}`} className="hover:text-primary" data-testid={`link-report-sim-${s.id}`}>{s.scenario.name}</Link> <span className="text-muted-foreground">({s.scenario.mode})</span></td>
            <td className="num">{s.scenario.seed}</td><td className="num text-right">{fmtNum(s.baseline.amplification, 2)}×</td><td className="num text-right">{s.candidate ? `${fmtNum(s.candidate.amplification, 2)}×` : "n/a"}</td>
            <td className="num text-right">{s.baseline.failed}</td><td className="num text-right">{s.candidate ? s.candidate.failed : "n/a"}</td></tr>)}</tbody></table></div>
          : <EmptyState title="No simulations in report" action={<Button asChild size="sm" variant="outline"><Link href={`/simulation/${a.id}`}>Run a scenario</Link></Button>} />}
      </Panel>
      <Panel title="Measured validation"><ValidationView v={r.measured_validation} /></Panel>
      <Panel title="Limitations"><ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">{r.limitations.map((l) => <li key={l}>{l}</li>)}</ul></Panel>
    </>
  );
}
