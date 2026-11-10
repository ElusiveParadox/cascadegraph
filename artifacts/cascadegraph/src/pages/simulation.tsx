import { useState } from "react";
import { Link, useLocation, useParams } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Dices, Play } from "lucide-react";
import { getGetReportQueryKey, useGetReport, useRunSimulation, ScenarioMode, type Analysis, type Scenario } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { WithAnalysis } from "@/components/analysis-loader";
import { ErrorPanel, PageHeader, Panel, Tag } from "@/components/common";
import { fmtDate, fmtNum, writeSelection } from "@/lib/workspace";

type NumField = { key: keyof Scenario; label: string; min: number; max: number; step?: number; unit?: string; hint?: string; int?: boolean };
const FIELDS: { group: string; fields: NumField[] }[] = [
  { group: "Load", fields: [
    { key: "requests", label: "Requests", min: 1, max: 500, int: true },
    { key: "arrival_rate", label: "Arrival rate", min: 0.1, max: 100, step: 0.1, unit: "req/s" },
    { key: "concurrency", label: "Concurrency per service", min: 1, max: 100, int: true },
    { key: "queue_limit", label: "Queue limit", min: 0, max: 1000, int: true },
  ] },
  { group: "Fault", fields: [
    { key: "service_time_ms", label: "Service time", min: 1, max: 5000, unit: "ms", int: true },
    { key: "fault_latency_ms", label: "Fault latency", min: 0, max: 10000, unit: "ms", int: true },
    { key: "failure_rate", label: "Failure rate", min: 0, max: 1, step: 0.01, hint: "0–1 probability" },
  ] },
  { group: "Timeouts", fields: [
    { key: "per_attempt_timeout_ms", label: "Per-attempt timeout", min: 1, max: 10000, unit: "ms", int: true },
    { key: "deadline_ms", label: "Request deadline", min: 1, max: 60000, unit: "ms", int: true },
  ] },
];
const CANDIDATE: NumField[] = [
  { key: "candidate_backoff_ms", label: "Candidate backoff", min: 0, max: 5000, unit: "ms", int: true },
  { key: "candidate_jitter_ms", label: "Candidate jitter", min: 0, max: 5000, unit: "ms", int: true },
];
const MODE_HELP: Record<string, string> = {
  healthy: "No injected faults; measures baseline retry overhead.",
  latency: "Adds fault latency to calls; timeouts may convert slowness into retries.",
  timeout: "Calls hang past their timeout.",
  intermittent: "Independent failures at the given rate.",
  correlated: "Failures cluster in time, like a dependency brownout.",
};

const DEFAULTS: Record<string, string> = {
  name: "intermittent-baseline", seed: "42", requests: "100", arrival_rate: "10", service_time_ms: "40", fault_latency_ms: "250", failure_rate: "0.2",
  per_attempt_timeout_ms: "500", deadline_ms: "3000", concurrency: "8", queue_limit: "50", candidate_attempts: "", candidate_backoff_ms: "100", candidate_jitter_ms: "50",
};

function SimForm({ analysis }: { analysis: Analysis }) {
  const qc = useQueryClient();
  const [, nav] = useLocation();
  const [v, setV] = useState<Record<string, string>>(DEFAULTS);
  const [mode, setMode] = useState<Scenario["mode"]>("intermittent");
  const [entry, setEntry] = useState<string>("auto");
  const run = useRunSimulation({ mutation: { onSuccess: (sim) => {
    qc.invalidateQueries({ queryKey: getGetReportQueryKey(analysis.id) });
    writeSelection({ analysisId: analysis.id, simulationId: sim.id });
    nav(`/comparison/${sim.id}`);
  } } });
  const set = (k: string, val: string) => setV((p) => ({ ...p, [k]: val }));
  const all: NumField[] = [...FIELDS.flatMap((g) => g.fields), ...CANDIDATE, { key: "seed", label: "Seed", min: 0, max: 2147483647, int: true }];
  const errors: Record<string, string> = {};
  for (const f of all) {
    const n = Number(v[f.key as string]);
    if (v[f.key as string].trim() === "" || !Number.isFinite(n) || n < f.min || n > f.max || (f.int && !Number.isInteger(n))) errors[f.key as string] = `${f.int ? "integer " : ""}${f.min}–${f.max}`;
  }
  if (v.candidate_attempts.trim() !== "") { const n = Number(v.candidate_attempts); if (!Number.isInteger(n) || n < 1 || n > 10) errors.candidate_attempts = "integer 1–10, or blank"; }
  if (!v.name.trim() || v.name.length > 80) errors.name = "1–80 chars";
  const ok = Object.keys(errors).length === 0;
  const submit = () => {
    const num = (k: string) => Number(v[k]);
    const data: Scenario = {
      name: v.name.trim(), mode, seed: num("seed"), requests: num("requests"), arrival_rate: num("arrival_rate"), service_time_ms: num("service_time_ms"),
      fault_latency_ms: num("fault_latency_ms"), failure_rate: num("failure_rate"), per_attempt_timeout_ms: num("per_attempt_timeout_ms"), deadline_ms: num("deadline_ms"),
      concurrency: num("concurrency"), queue_limit: num("queue_limit"), candidate_attempts: v.candidate_attempts.trim() === "" ? null : num("candidate_attempts"),
      candidate_backoff_ms: num("candidate_backoff_ms"), candidate_jitter_ms: num("candidate_jitter_ms"), entry_service: entry === "auto" ? null : entry,
    };
    run.mutate({ analysisId: analysis.id, data });
  };
  const field = (f: NumField) => (
    <label key={f.key as string} className="block text-xs font-medium">
      <span className="flex justify-between gap-2">{f.label}{f.unit && <span className="num font-normal text-muted-foreground">{f.unit}</span>}</span>
      <Input type="number" min={f.min} max={f.max} step={f.step ?? 1} value={v[f.key as string]} onChange={(e) => set(f.key as string, e.target.value)}
        aria-invalid={!!errors[f.key as string]} className="num mt-1 aria-[invalid=true]:border-destructive" data-testid={`input-${f.key as string}`} />
      <span className={`num text-[10.5px] font-normal ${errors[f.key as string] ? "text-destructive" : "text-muted-foreground"}`}>{errors[f.key as string] ?? f.hint ?? `${f.min}–${f.max}`}</span>
    </label>
  );
  const unconfirmed = analysis.policies.filter((p) => !p.confirmed).length;
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (ok) submit(); }} className="space-y-4">
      <Panel title="Scenario">
        <div className="grid gap-3 md:grid-cols-[2fr_1fr_1fr_1fr]">
          <label className="block text-xs font-medium">Name<Input value={v.name} maxLength={80} onChange={(e) => set("name", e.target.value)} className="mt-1" data-testid="input-name" />
            <span className="text-[10.5px] text-destructive">{errors.name}</span></label>
          <div className="text-xs font-medium">Mode
            <Select value={mode} onValueChange={(x) => setMode(x as Scenario["mode"])}><SelectTrigger className="mt-1" data-testid="select-mode"><SelectValue /></SelectTrigger>
              <SelectContent>{Object.values(ScenarioMode).map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent></Select></div>
          <div className="text-xs font-medium">Entry service
            <Select value={entry} onValueChange={setEntry}><SelectTrigger className="mt-1" data-testid="select-entry"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="auto">auto (graph root)</SelectItem>{analysis.nodes.map((n) => <SelectItem key={n.id} value={n.id}>{n.name}</SelectItem>)}</SelectContent></Select></div>
          <div className="flex items-end gap-1">
            <div className="flex-1">{field({ key: "seed", label: "Seed", min: 0, max: 2147483647, int: true })}</div>
            <Button type="button" variant="ghost" size="icon" className="mb-5" aria-label="Random seed" data-testid="button-random-seed" onClick={() => set("seed", String(Math.floor(Math.random() * 2147483647)))}><Dices className="h-4 w-4" /></Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{MODE_HELP[mode]} Same seed and inputs reproduce identical results.</p>
      </Panel>
      <div className="grid gap-4 md:grid-cols-3">
        {FIELDS.map((g) => <Panel key={g.group} title={g.group}><div className="space-y-3">{g.fields.map(field)}</div></Panel>)}
      </div>
      <Panel title="Candidate policy" meta="optional">
        <p className="mb-3 text-xs text-muted-foreground">Leave attempts blank to run only the baseline using extracted policies. Set it to override every retry policy with a uniform candidate and compare.</p>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="block text-xs font-medium">Candidate total attempts
            <Input type="number" min={1} max={10} value={v.candidate_attempts} placeholder="baseline only" onChange={(e) => set("candidate_attempts", e.target.value)} className="num mt-1" data-testid="input-candidate_attempts" />
            <span className={`text-[10.5px] ${errors.candidate_attempts ? "text-destructive" : "text-muted-foreground"}`}>{errors.candidate_attempts ?? "1–10, includes first call"}</span></label>
          {CANDIDATE.map(field)}
        </div>
      </Panel>
      {unconfirmed > 0 && <div className="rounded-sm border border-chart-3/50 bg-chart-3/10 px-3 py-2 text-xs">{unconfirmed} of {analysis.policies.length} policies are unconfirmed; the baseline uses their extracted values as-is. <Link href={`/policies/${analysis.id}`} className="font-medium underline">Review policies</Link></div>}
      {run.isError && <ErrorPanel error={run.error} title="Simulation rejected" />}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!ok || run.isPending} data-testid="button-run-simulation"><Play className="mr-1.5 h-4 w-4" />{run.isPending ? "Running deterministic simulation…" : "Run simulation"}</Button>
        {!ok && <span className="text-xs text-destructive">Fix highlighted fields.</span>}
      </div>
    </form>
  );
}

function History({ analysisId }: { analysisId: string }) {
  const r = useGetReport(analysisId, { query: { enabled: !!analysisId, queryKey: getGetReportQueryKey(analysisId) } });
  if (r.isLoading) return <div className="text-xs text-muted-foreground">Loading previous runs…</div>;
  if (r.isError) return <ErrorPanel error={r.error} onRetry={() => r.refetch()} title="Could not load previous runs" />;
  const sims = r.data?.simulations ?? [];
  if (!sims.length) return <div className="text-xs text-muted-foreground">No simulations yet for this analysis.</div>;
  return (
    <ul className="space-y-1">{sims.map((s) => (
      <li key={s.id}><Link href={`/comparison/${s.id}`} onClick={() => writeSelection({ simulationId: s.id })} className="flex items-center justify-between gap-2 rounded-sm border border-border px-2.5 py-1.5 text-xs hover:border-primary" data-testid={`link-simulation-${s.id}`}>
        <span className="truncate"><span className="font-medium">{s.scenario.name}</span> <span className="num text-muted-foreground">· {s.scenario.mode} · seed {s.scenario.seed}</span></span>
        <span className="num shrink-0">{fmtNum(s.baseline.amplification, 2)}×{s.candidate ? ` → ${fmtNum(s.candidate.amplification, 2)}×` : ""} <Tag>{fmtDate(s.created_at)}</Tag></span>
      </Link></li>))}</ul>
  );
}

export default function SimulationPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <WithAnalysis id={id}>{(a) => (
      <>
        <PageHeader kicker="simulation" title="Scenario editor">
          Discrete-event simulation of <Link href={`/analyses/${a.id}`} className="font-medium text-foreground underline-offset-2 hover:underline">{a.name}</Link>. Bounded and synchronous: results return with the request.
        </PageHeader>
        <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
          <SimForm analysis={a} />
          <Panel title="Previous runs" className="xl:self-start"><History analysisId={a.id} /></Panel>
        </div>
      </>
    )}</WithAnalysis>
  );
}
