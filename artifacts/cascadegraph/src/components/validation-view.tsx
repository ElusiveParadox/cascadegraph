import type { ValidationStatus } from "@workspace/api-client-react";
import { EmptyState, KV, Tag, severityTone } from "@/components/common";
import { fmtDate, fmtNum } from "@/lib/workspace";

export function ValidationView({ v }: { v: ValidationStatus }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start gap-3">
        <Tag tone={severityTone(v.status)} testId="status-validation">{v.status}</Tag>
        <p className="flex-1 text-sm text-muted-foreground">{v.detail}</p>
      </div>
      <dl className="max-w-xl">
        <KV k="Commit">{v.commit_sha ? <span className="num text-xs">{v.commit_sha.slice(0, 12)}</span> : <span className="text-muted-foreground">not recorded</span>}</KV>
        <KV k="Measured at">{v.measured_at ? fmtDate(v.measured_at) : <span className="text-muted-foreground">not recorded</span>}</KV>
        <KV k="CI workflow">{v.workflow_url ? <a href={v.workflow_url} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline" data-testid="link-workflow">open run</a> : <span className="text-muted-foreground">not linked</span>}</KV>
      </dl>
      {v.cases.length === 0 ? (
        <EmptyState title="No measured cases available">The simulator has not been checked against a live harness in this deployment. No measurements are shown in their place.</EmptyState>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="table-validation">
            <thead><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              {["Case", "Logical req", "Predicted amp.", "Measured amp.", "Abs. error", "Predicted ok", "Measured ok"].map((h, i) => <th key={h} className={`py-2 pr-3 font-medium ${i ? "text-right" : ""}`}>{h}</th>)}
            </tr></thead>
            <tbody>{v.cases.map((c) => (
              <tr key={c.name} className="border-b border-dashed border-border last:border-0">
                <td className="py-1.5 pr-3">{c.name}</td>
                <td className="num py-1.5 pr-3 text-right">{c.logical_requests}</td>
                <td className="num py-1.5 pr-3 text-right">{fmtNum(c.predicted_amplification, 3)}</td>
                <td className="num py-1.5 pr-3 text-right">{fmtNum(c.measured_amplification, 3)}</td>
                <td className="num py-1.5 pr-3 text-right">{fmtNum(c.absolute_error, 3)}</td>
                <td className="num py-1.5 pr-3 text-right">{c.predicted_successes}</td>
                <td className="num py-1.5 text-right">{c.measured_successes}</td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
