import type { SimulationResult } from "@workspace/api-client-react";
import { cn } from "@/lib/utils";
import { delta, fmtNum } from "@/lib/workspace";

const rows: { key: keyof SimulationResult; label: string; digits?: number; unit?: string; worseWhenHigher?: boolean }[] = [
  { key: "incoming_requests", label: "Incoming requests" },
  { key: "downstream_attempts", label: "Downstream attempts", worseWhenHigher: true },
  { key: "retry_attempts", label: "Retry attempts", worseWhenHigher: true },
  { key: "leaf_attempts", label: "Leaf attempts", worseWhenHigher: true },
  { key: "amplification", label: "Amplification", digits: 2, unit: "×", worseWhenHigher: true },
  { key: "retry_ratio", label: "Retry ratio", digits: 3, worseWhenHigher: true },
  { key: "succeeded", label: "Succeeded", worseWhenHigher: false },
  { key: "failed", label: "Failed", worseWhenHigher: true },
  { key: "deadline_misses", label: "Deadline misses", worseWhenHigher: true },
  { key: "p50_ms", label: "p50 latency", unit: "ms", worseWhenHigher: true },
  { key: "p95_ms", label: "p95 latency", unit: "ms", worseWhenHigher: true },
  { key: "p99_ms", label: "p99 latency", unit: "ms", worseWhenHigher: true },
  { key: "duration_ms", label: "Simulated duration", unit: "ms" },
  { key: "event_count", label: "Events processed" },
];

export function ResultsTable({ baseline, candidate }: { baseline: SimulationResult; candidate: SimulationResult | null }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="table-results">
        <thead>
          <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
            <th className="py-2 pr-3 font-medium">Metric</th>
            <th className="py-2 pr-3 text-right font-medium">Baseline</th>
            {candidate && <th className="py-2 pr-3 text-right font-medium">Candidate</th>}
            {candidate && <th className="py-2 text-right font-medium">Δ</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const b = baseline[r.key] as number;
            const c = candidate ? (candidate[r.key] as number) : null;
            const better = c !== null && r.worseWhenHigher !== undefined && c !== b ? (r.worseWhenHigher ? c < b : c > b) : null;
            return (
              <tr key={r.key} className="border-b border-dashed border-border last:border-0 hover:bg-muted/40">
                <td className="py-1.5 pr-3">{r.label}</td>
                <td className="num py-1.5 pr-3 text-right" data-testid={`text-baseline-${r.key}`}>{fmtNum(b, r.digits ?? 0)}{r.unit && <span className="text-muted-foreground"> {r.unit}</span>}</td>
                {candidate && <td className="num py-1.5 pr-3 text-right" data-testid={`text-candidate-${r.key}`}>{fmtNum(c, r.digits ?? 0)}{r.unit && <span className="text-muted-foreground"> {r.unit}</span>}</td>}
                {candidate && <td className={cn("num py-1.5 text-right", better === true && "text-chart-2", better === false && "text-destructive")}>{delta(b, c!)}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function PerServiceTable({ result, label }: { result: SimulationResult; label: string }) {
  if (!result.per_service.length) return <div className="text-sm text-muted-foreground">No per-service metrics returned for {label}.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
          {["Service", "Attempts", "Retries", "Failures", "Peak conc.", "Peak queue"].map((h, i) => <th key={h} className={cn("py-2 pr-3 font-medium", i && "text-right")}>{h}</th>)}
        </tr></thead>
        <tbody>
          {result.per_service.map((s) => (
            <tr key={s.service_id} className="border-b border-dashed border-border last:border-0">
              <td className="num py-1.5 pr-3">{s.service_id}</td>
              {[s.attempts, s.retries, s.failures, s.peak_concurrency, s.peak_queue].map((v, i) => <td key={i} className="num py-1.5 pr-3 text-right">{fmtNum(v)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TimelineTable({ result }: { result: SimulationResult }) {
  if (!result.timeline.length) return <div className="text-sm text-muted-foreground">No timeline points returned.</div>;
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-card"><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
          <th className="py-2 pr-3 font-medium">t (ms)</th><th className="py-2 pr-3 text-right font-medium">Attempts</th><th className="py-2 text-right font-medium">Retries</th>
        </tr></thead>
        <tbody>{result.timeline.map((t) => (
          <tr key={t.time_ms} className="border-b border-dashed border-border last:border-0">
            <td className="num py-1 pr-3">{fmtNum(t.time_ms)}</td><td className="num py-1 pr-3 text-right">{fmtNum(t.attempts)}</td><td className="num py-1 text-right">{fmtNum(t.retries)}</td>
          </tr>))}
        </tbody>
      </table>
    </div>
  );
}
