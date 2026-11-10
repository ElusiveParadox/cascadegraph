import { useEffect, useState } from "react";
import { Link, useParams, useSearch, useLocation } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useConfirmPolicy, type Analysis, type Policy } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { WithAnalysis } from "@/components/analysis-loader";
import { EmptyState, ErrorPanel, EvidenceList, KV, PageHeader, Panel, Tag, Unknown, Value } from "@/components/common";
import { refreshAnalysis } from "@/lib/invalidate";
import { cn } from "@/lib/utils";

function numOrNull(s: string): number | null { const t = s.trim(); if (!t) return null; const n = Number(t); return Number.isFinite(n) ? n : NaN; }

function ConfirmForm({ analysisId, policy }: { analysisId: string; policy: Policy }) {
  const qc = useQueryClient();
  const [attempts, setAttempts] = useState(String(policy.max_total_attempts ?? ""));
  const [timeout, setTimeoutMs] = useState(policy.per_attempt_timeout_ms?.toString() ?? "");
  const [deadline, setDeadline] = useState(policy.overall_deadline_ms?.toString() ?? "");
  const [note, setNote] = useState(policy.confirmation_note ?? "");
  useEffect(() => {
    setAttempts(String(policy.max_total_attempts ?? "")); setTimeoutMs(policy.per_attempt_timeout_ms?.toString() ?? "");
    setDeadline(policy.overall_deadline_ms?.toString() ?? ""); setNote(policy.confirmation_note ?? "");
  }, [policy.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const m = useConfirmPolicy({ mutation: { onSuccess: (a) => refreshAnalysis(qc, analysisId, a) } });
  const a = Number(attempts), t = numOrNull(timeout), d = numOrNull(deadline);
  const errs: string[] = [];
  if (!Number.isInteger(a) || a < 1 || a > 10) errs.push("Total attempts must be an integer 1–10.");
  if (t !== null && (Number.isNaN(t) || t < 1 || t > 60000)) errs.push("Per-attempt timeout must be 1–60000 ms.");
  if (d !== null && (Number.isNaN(d) || d < 1 || d > 120000)) errs.push("Deadline must be 1–120000 ms.");
  if (note.trim().length < 3 || note.length > 300) errs.push("Note must be 3–300 characters.");
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (!errs.length) m.mutate({ analysisId, policyId: policy.id, data: { max_total_attempts: a, note: note.trim(), per_attempt_timeout_ms: t, overall_deadline_ms: d } }); }}>
      <p className="text-xs text-muted-foreground">Your values are recorded as a reviewer correction. Original source facts (semantics, raw value, evidence) are preserved and remain visible.</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="text-xs font-medium">Max total attempts<Input type="number" min={1} max={10} step={1} value={attempts} onChange={(e) => setAttempts(e.target.value)} className="num mt-1" data-testid="input-max-attempts" /><span className="text-[10.5px] font-normal text-muted-foreground">includes first call</span></label>
        <label className="text-xs font-medium">Per-attempt timeout (ms)<Input type="number" min={1} max={60000} value={timeout} onChange={(e) => setTimeoutMs(e.target.value)} placeholder="optional" className="num mt-1" data-testid="input-policy-timeout" /></label>
        <label className="text-xs font-medium">Overall deadline (ms)<Input type="number" min={1} max={120000} value={deadline} onChange={(e) => setDeadline(e.target.value)} placeholder="optional" className="num mt-1" data-testid="input-policy-deadline" /></label>
      </div>
      <label className="block text-xs font-medium">Reviewer note<Textarea value={note} maxLength={300} rows={2} onChange={(e) => setNote(e.target.value)} className="mt-1" placeholder="Why these values are correct" data-testid="input-policy-note" /></label>
      {errs.length > 0 && <ul className="space-y-0.5 text-xs text-muted-foreground">{errs.map((x) => <li key={x}>· {x}</li>)}</ul>}
      {m.isError && <ErrorPanel error={m.error} title="Policy confirmation failed" />}
      {m.isSuccess && <div className="flex items-center gap-1.5 text-xs text-chart-2"><CheckCircle2 className="h-3.5 w-3.5" />Saved. Future simulations use these values; earlier run snapshots remain unchanged.</div>}
      <Button type="submit" size="sm" disabled={errs.length > 0 || m.isPending} data-testid="button-confirm-policy">{m.isPending ? "Saving…" : policy.confirmed ? "Update confirmation" : "Confirm policy"}</Button>
    </form>
  );
}

function PolicyDetail({ analysis, policy }: { analysis: Analysis; policy: Policy }) {
  const b = policy.backoff;
  return (
    <div className="min-w-0 space-y-4" data-testid={`panel-policy-${policy.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><div className="num text-xs text-muted-foreground">{policy.framework}</div><div className="font-display text-xl font-bold">{policy.symbol}</div>
          <div className="num text-[11px] text-muted-foreground">service {policy.service_id ?? "unattributed"} · edge {policy.edge_id ?? "unattributed"}</div></div>
        <div className="flex flex-wrap gap-1"><Tag tone={policy.confirmed ? "ok" : "warn"}>{policy.confirmed ? "confirmed" : "unconfirmed"}</Tag><Tag>{policy.resolution_status}</Tag><Tag>{policy.extraction_method}</Tag><Tag>confidence {policy.confidence}</Tag></div>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-sm border border-border p-3">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">As written in source</div>
          <dl><KV k="Semantics"><span className="num text-xs">{policy.source_semantics}</span></KV><KV k="Raw value"><Value v={policy.source_value} /></KV></dl>
        </div>
        <div className="rounded-sm border border-primary/40 bg-primary/5 p-3">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-primary">Normalized for simulation</div>
          <dl><KV k="Max total attempts"><span data-testid="text-max-total-attempts"><Value v={policy.max_total_attempts} /></span></KV>
            <KV k="Per-attempt timeout"><Value v={policy.per_attempt_timeout_ms} unit="ms" /></KV>
            <KV k="Overall deadline"><Value v={policy.overall_deadline_ms} unit="ms" /></KV></dl>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div><div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Backoff</div>
          <dl><KV k="Kind">{b.kind === "unknown" ? <Unknown /> : <span className="num">{b.kind}</span>}</KV><KV k="Delay"><Value v={b.delay_ms} unit="ms" /></KV>
            <KV k="Multiplier"><span className="num">{b.multiplier}</span></KV><KV k="Cap"><Value v={b.cap_ms} unit="ms" /></KV><KV k="Jitter"><span className="num">{b.jitter_ms} ms</span></KV></dl></div>
        <div><div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Retries on</div>
          {policy.retry_on.length ? <div className="flex flex-wrap gap-1">{policy.retry_on.map((r) => <Tag key={r}>{r}</Tag>)}</div> : <Unknown>conditions not determined</Unknown>}
          {policy.allowed_methods && <p className="num mt-2 text-xs">Methods: {policy.allowed_methods.join(", ")}</p>}
          {policy.category_limits && Object.keys(policy.category_limits).length > 0 && <p className="num mt-2 text-xs">Retry budgets: {Object.entries(policy.category_limits).map(([k, v]) => `${k}=${v ?? "unknown"}`).join(" · ")}</p>}
          <div className="mb-1 mt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Unresolved</div>
          {policy.unresolved.length ? <ul className="space-y-1">{policy.unresolved.map((u) => <li key={u}><Unknown>{u}</Unknown></li>)}</ul> : <span className="text-xs text-muted-foreground">Nothing unresolved.</span>}
        </div>
      </div>
      {policy.confirmed && policy.confirmation_note && <div className="rounded-sm border-l-2 border-chart-2 bg-chart-2/5 px-3 py-2 text-sm"><span className="text-xs text-muted-foreground">Reviewer note: </span>{policy.confirmation_note}</div>}
      <div><div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Source evidence</div><EvidenceList evidence={policy.evidence} testPrefix="policy-evidence" /></div>
      <Panel title={policy.confirmed ? "Correct confirmation" : "Confirm or correct"}><ConfirmForm analysisId={analysis.id} policy={policy} /></Panel>
    </div>
  );
}

function PoliciesView({ analysis }: { analysis: Analysis }) {
  const search = useSearch();
  const [, nav] = useLocation();
  const wanted = new URLSearchParams(search).get("policy");
  const current = analysis.policies.find((p) => p.id === wanted) ?? analysis.policies[0];
  return (
    <>
      <PageHeader kicker="policies" title="Retry policy inspection">
        Source counts are framework-specific (retries vs attempts). Every policy is normalized to <span className="font-medium text-foreground">total attempts including the first call</span>; check the normalization against evidence before trusting a simulation. <Link href={`/analyses/${analysis.id}`} className="text-primary underline-offset-2 hover:underline">Back to graph</Link>
      </PageHeader>
      {!analysis.policies.length ? <EmptyState title="No retry policies extracted">Nothing matched the supported parsers. See Scope & limits for what is recognised.</EmptyState> : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Panel title="Policies" meta={analysis.policies.length} className="lg:sticky lg:top-6 lg:self-start">
            <ul className="-m-2 space-y-0.5">
              {analysis.policies.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => nav(`/policies/${analysis.id}?policy=${encodeURIComponent(p.id)}`, { replace: true })} data-testid={`button-select-policy-${p.id}`}
                    className={cn("w-full rounded-sm px-2 py-2 text-left transition-colors hover:bg-muted", current?.id === p.id && "bg-accent")}>
                    <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{p.symbol}</span>
                      <span className="num shrink-0 text-xs">{p.max_total_attempts ?? "?"}×</span></div>
                    <div className="mt-0.5 flex items-center gap-1.5"><span className="num truncate text-[10.5px] text-muted-foreground">{p.framework}</span>
                      {p.confirmed ? <Tag tone="ok">ok</Tag> : p.unresolved.length ? <Tag tone="warn">{p.unresolved.length} open</Tag> : null}</div>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
          <Panel>{current && <PolicyDetail analysis={analysis} policy={current} />}</Panel>
        </div>
      )}
    </>
  );
}

export default function PoliciesPage() {
  const { id } = useParams<{ id: string }>();
  return <WithAnalysis id={id}>{(a) => <PoliciesView analysis={a} />}</WithAnalysis>;
}
