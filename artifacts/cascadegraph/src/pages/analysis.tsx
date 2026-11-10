import { useState } from "react";
import { Link, useParams } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, SlidersHorizontal } from "lucide-react";
import { useConfirmEdge, type Analysis } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { WithAnalysis } from "@/components/analysis-loader";
import { EmptyState, ErrorPanel, EvidenceList, KV, PageHeader, Panel, Tag, Unknown, severityTone } from "@/components/common";
import { ServiceGraph, type GraphSelection } from "@/components/service-graph";
import { refreshAnalysis } from "@/lib/invalidate";
import { fmtDate } from "@/lib/workspace";

function EdgeConfirm({ analysis, edgeId }: { analysis: Analysis; edgeId: string }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const m = useConfirmEdge({ mutation: { onSuccess: (a) => { refreshAnalysis(qc, analysis.id, a); setNote(""); } } });
  const valid = note.trim().length >= 3 && note.length <= 300;
  return (
    <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (valid) m.mutate({ analysisId: analysis.id, edgeId, data: { note: note.trim() } }); }}>
      <label htmlFor="edge-note" className="text-xs font-medium">Confirmation note <span className="text-muted-foreground">(required, 3–300 chars)</span></label>
      <Textarea id="edge-note" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Verified call in checkout/client.go during on-call review" data-testid="input-edge-note" rows={2} />
      {m.isError && <ErrorPanel error={m.error} title="Edge confirmation failed" />}
      <Button type="submit" size="sm" disabled={!valid || m.isPending} data-testid="button-confirm-edge">{m.isPending ? "Confirming…" : "Confirm edge"}</Button>
    </form>
  );
}

function Inspector({ analysis, sel }: { analysis: Analysis; sel: GraphSelection }) {
  if (!sel) return <EmptyState title="Select a node or edge">Click a service or a connection in the graph to inspect its source evidence.</EmptyState>;
  if (sel.kind === "node") {
    const n = analysis.nodes.find((x) => x.id === sel.id);
    if (!n) return null;
    const pols = analysis.policies.filter((p) => p.service_id === n.id);
    return (
      <div className="space-y-4" data-testid="panel-node-inspector">
        <div><Tag>service</Tag><div className="font-display mt-1 text-xl font-bold">{n.name}</div><div className="num text-xs text-muted-foreground">{n.id}</div></div>
        <dl><KV k="Startup dependencies">{n.startup_dependencies.length ? <span className="num text-xs">{n.startup_dependencies.join(", ")}</span> : <span className="text-muted-foreground">none declared</span>}</KV>
          <KV k="Outgoing edges"><span className="num">{analysis.edges.filter((e) => e.source === n.id).length}</span></KV>
          <KV k="Policies in service"><span className="num">{pols.length}</span></KV></dl>
        {pols.length > 0 && <div className="space-y-1">{pols.map((p) => <Link key={p.id} href={`/policies/${analysis.id}?policy=${encodeURIComponent(p.id)}`} className="num block truncate rounded-sm border border-border px-2 py-1 text-xs hover:border-primary" data-testid={`link-policy-${p.id}`}>{p.framework} · {p.symbol}</Link>)}</div>}
        <div><div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Evidence</div><EvidenceList evidence={n.evidence} testPrefix="node-evidence" /></div>
      </div>
    );
  }
  const e = analysis.edges.find((x) => x.id === sel.id);
  if (!e) return null;
  const name = (id: string) => analysis.nodes.find((n) => n.id === id)?.name ?? id;
  return (
    <div className="space-y-4" data-testid="panel-edge-inspector">
      <div><Tag tone={e.confirmed ? "ok" : "warn"}>{e.confirmed ? "confirmed edge" : "unconfirmed edge"}</Tag>
        <div className="font-display mt-1 text-xl font-bold">{name(e.source)} <span className="text-muted-foreground">→</span> {name(e.target)}</div>
        <div className="num text-xs text-muted-foreground">{e.id}</div></div>
      <dl><KV k="Evidence kind"><Tag tone={e.evidence_kind === "inferred" ? "warn" : "info"}>{e.evidence_kind}</Tag></KV>
        <KV k="Retry policies on edge"><span className="num">{e.policy_ids.length}</span></KV></dl>
      {e.policy_ids.length > 0 && <div className="space-y-1">{e.policy_ids.map((pid) => {
        const p = analysis.policies.find((x) => x.id === pid);
        return <Link key={pid} href={`/policies/${analysis.id}?policy=${encodeURIComponent(pid)}`} className="num flex items-center justify-between gap-2 rounded-sm border border-border px-2 py-1 text-xs hover:border-primary" data-testid={`link-edge-policy-${pid}`}>
          <span className="truncate">{p ? `${p.framework} · ${p.symbol}` : pid}</span><span>{p?.max_total_attempts ?? "?"} attempts</span></Link>;
      })}</div>}
      <div><div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Evidence</div><EvidenceList evidence={e.evidence} testPrefix="edge-evidence" /></div>
      {e.confirmed ? <div className="flex items-center gap-2 text-sm text-chart-2"><CheckCircle2 className="h-4 w-4" />Confirmed by reviewer</div> : <EdgeConfirm analysis={analysis} edgeId={e.id} />}
    </div>
  );
}

function AnalysisView({ analysis }: { analysis: Analysis }) {
  const [sel, setSel] = useState<GraphSelection>(analysis.edges[0] ? { kind: "edge", id: analysis.edges[0].id } : analysis.nodes[0] ? { kind: "node", id: analysis.nodes[0].id } : null);
  const unresolved = analysis.policies.filter((p) => p.unresolved.length > 0 || p.max_total_attempts === null).length;
  const hot = new Set(analysis.policies.map((p) => p.service_id).filter((x): x is string => !!x));
  return (
    <>
      <PageHeader kicker={`01 / analysis · ${analysis.source_type}`} title={analysis.name}
        actions={<>
          <Button asChild variant="outline" size="sm"><Link href={`/policies/${analysis.id}`} data-testid="link-to-policies"><SlidersHorizontal className="mr-1.5 h-4 w-4" />Policies</Link></Button>
          <Button asChild size="sm"><Link href={`/simulation/${analysis.id}`} data-testid="link-to-simulation"><FlaskConical className="mr-1.5 h-4 w-4" />Simulate</Link></Button>
        </>}>
        <span className="num text-xs">fingerprint {analysis.fingerprint.slice(0, 16)} · created {fmtDate(analysis.created_at)} · expires {fmtDate(analysis.expires_at)}</span>
      </PageHeader>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border md:grid-cols-5">
        {[["status", <Tag key="s" tone={severityTone(analysis.status)}>{analysis.status}</Tag>], ["files", analysis.file_count], ["services", analysis.nodes.length], ["edges", analysis.edges.length], ["policies", `${analysis.policies.length}${unresolved ? ` · ${unresolved} unresolved` : ""}`]].map(([k, v]) => (
          <div key={k as string} className="bg-card px-4 py-3"><div className="num text-[10.5px] uppercase tracking-wider text-muted-foreground">{k as string}</div><div className="num mt-1 text-lg font-semibold" data-testid={`text-stat-${k}`}>{v}</div></div>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <Panel title="Service graph" meta="click to inspect">
          {analysis.nodes.length ? <ServiceGraph nodes={analysis.nodes} edges={analysis.edges} selected={sel} onSelect={setSel} hot={hot} /> :
            <EmptyState title="No services detected">The parsers found no service boundaries in this source. See assumptions below and the supported scope.</EmptyState>}
          {analysis.edges.length > 0 && (
            <div className="mt-3 max-h-56 overflow-auto">
              <table className="w-full text-xs"><caption className="sr-only">Edges</caption>
                <thead><tr className="text-left text-[10.5px] uppercase tracking-wider text-muted-foreground"><th className="py-1 font-medium">Edge</th><th className="font-medium">Evidence</th><th className="font-medium">Policies</th><th className="font-medium">State</th></tr></thead>
                <tbody>{analysis.edges.map((e) => (
                  <tr key={e.id} onClick={() => setSel({ kind: "edge", id: e.id })} className={`cursor-pointer border-t border-dashed border-border hover:bg-muted/50 ${sel?.kind === "edge" && sel.id === e.id ? "bg-accent/50" : ""}`} data-testid={`row-edge-${e.id}`}>
                    <td className="num py-1">{e.source} → {e.target}</td><td>{e.evidence_kind}</td><td className="num">{e.policy_ids.length}</td><td>{e.confirmed ? <Tag tone="ok">confirmed</Tag> : <Tag tone="warn">unconfirmed</Tag>}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
        </Panel>
        <Panel title="Inspector"><Inspector analysis={analysis} sel={sel} /></Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Findings" meta={analysis.findings.length} className="lg:col-span-2">
          {analysis.findings.length ? <ul className="space-y-2">{analysis.findings.map((f, i) => (
            <li key={i} className="flex gap-3 rounded-sm border border-border p-3" data-testid={`card-finding-${i}`}>
              <div className="pt-0.5"><Tag tone={severityTone(f.severity)}>{f.severity}</Tag></div>
              <div><div className="text-sm font-semibold">{f.title}</div><div className="mt-0.5 text-sm text-muted-foreground">{f.detail}</div></div>
            </li>))}</ul> : <p className="text-sm text-muted-foreground">No findings reported. That is not proof of safe retry behaviour; check unresolved policies.</p>}
        </Panel>
        <div className="space-y-4">
          <Panel title="Pipeline stages">
            {analysis.stages.length ? <ol className="space-y-1">{analysis.stages.map((s, i) => <li key={i} className="num flex gap-2 text-xs"><span className="text-primary">{String(i + 1).padStart(2, "0")}</span>{s}</li>)}</ol> : <Unknown>no stages reported</Unknown>}
          </Panel>
          <Panel title="Assumptions">
            {analysis.assumptions.length ? <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">{analysis.assumptions.map((s, i) => <li key={i}>{s}</li>)}</ul> : <span className="text-xs text-muted-foreground">None reported.</span>}
          </Panel>
        </div>
      </div>
    </>
  );
}

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  return <WithAnalysis id={id}>{(a) => <AnalysisView analysis={a} />}</WithAnalysis>;
}
