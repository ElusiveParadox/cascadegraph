import { type ReactNode, useState } from "react";
import { AlertTriangle, ChevronRight, FileCode2, HelpCircle, RotateCw } from "lucide-react";
import type { Evidence } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { errorMessage } from "@/lib/workspace";

export function PageHeader({ kicker, title, children, actions }: { kicker: string; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="rise flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <div className="num text-[11px] uppercase tracking-[0.18em] text-primary">{kicker}</div>
        <h1 className="font-display mt-1 text-2xl font-bold md:text-3xl" data-testid="text-page-title">{title}</h1>
        {children && <div className="mt-2 max-w-3xl text-sm text-muted-foreground">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Panel({ title, meta, children, className, id }: { title?: ReactNode; meta?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn("rise min-w-0 max-w-full rounded-md border border-card-border bg-card", className)}>
      {title && (
        <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-foreground/80">{title}</h2>
          {meta && <div className="num text-[11px] text-muted-foreground">{meta}</div>}
        </div>
      )}
      <div className="min-w-0 p-4">{children}</div>
    </section>
  );
}

export function ErrorPanel({ error, onRetry, title = "Request failed" }: { error: unknown; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" data-testid="status-error" className="rise rounded-md border border-destructive/40 bg-destructive/5 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-destructive">{title}</div>
          <pre className="num mt-1 whitespace-pre-wrap break-words text-xs text-foreground/80">{errorMessage(error)}</pre>
        </div>
        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry} data-testid="button-retry"><RotateCw className="mr-1.5 h-3.5 w-3.5" />Retry</Button>
        )}
      </div>
    </div>
  );
}

export function LoadingBlock({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-1/3" />
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="grid-paper rounded-md border border-dashed border-border px-6 py-10 text-center">
      <div className="font-display text-lg font-semibold">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function Unknown({ children = "unknown" }: { children?: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-sm border border-dashed border-chart-3/70 bg-chart-3/10 px-1.5 py-px text-[11px] font-medium text-[hsl(38_80%_30%)] dark:text-chart-3">
      <HelpCircle className="h-3 w-3" />{children}
    </span>
  );
}

export function Value({ v, unit }: { v: number | null | undefined; unit?: string }) {
  if (v === null || v === undefined) return <Unknown />;
  return <span className="num">{v.toLocaleString()}{unit ? <span className="text-muted-foreground"> {unit}</span> : null}</span>;
}

const toneMap: Record<string, string> = {
  ok: "border-chart-2/40 bg-chart-2/10 text-chart-2",
  warn: "border-chart-3/50 bg-chart-3/10 text-[hsl(38_80%_30%)] dark:text-chart-3",
  bad: "border-destructive/40 bg-destructive/10 text-destructive",
  info: "border-border bg-muted text-muted-foreground",
  hot: "border-primary/40 bg-primary/10 text-primary",
};
export function Tag({ tone = "info", children, testId }: { tone?: keyof typeof toneMap; children: ReactNode; testId?: string }) {
  return <span data-testid={testId} className={cn("num inline-flex items-center rounded-sm border px-1.5 py-px text-[10.5px] uppercase tracking-wide", toneMap[tone])}>{children}</span>;
}

export function severityTone(s: string): keyof typeof toneMap {
  const v = s.toLowerCase();
  if (["critical", "high", "error", "failed", "failure"].includes(v)) return "bad";
  if (["medium", "warning", "warn", "partial", "unavailable"].includes(v)) return "warn";
  if (["ok", "passed", "pass", "complete", "completed", "success", "low"].includes(v)) return "ok";
  return "info";
}

export function EvidenceList({ evidence, testPrefix = "evidence" }: { evidence: Evidence[]; testPrefix?: string }) {
  const [open, setOpen] = useState<number | null>(evidence.length ? 0 : null);
  if (!evidence.length) return <div className="text-xs text-muted-foreground"><Unknown>no source evidence</Unknown> This item is not backed by a file excerpt.</div>;
  return (
    <ul className="min-w-0 max-w-full space-y-1.5">
      {evidence.map((ev, i) => (
        <li key={`${ev.path}:${ev.line_start}:${i}`} className="min-w-0 max-w-full overflow-hidden rounded-sm border border-border">
          <button
            type="button"
            onClick={() => setOpen(open === i ? null : i)}
            aria-expanded={open === i}
            data-testid={`button-${testPrefix}-${i}`}
            className="flex w-full items-center gap-2 bg-muted/60 px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-muted"
          >
            <ChevronRight className={cn("h-3.5 w-3.5 shrink-0 transition-transform", open === i && "rotate-90")} />
            <FileCode2 className="h-3.5 w-3.5 shrink-0 text-chart-2" />
            <span className="num min-w-0 flex-1 truncate">{ev.path}</span>
            <span className="num shrink-0 text-muted-foreground">L{ev.line_start}{ev.line_end !== ev.line_start ? `–${ev.line_end}` : ""}</span>
          </button>
          {open === i && (
            <div className="bg-[hsl(215_36%_11%)] text-[hsl(40_25%_88%)]">
              <pre className="num max-w-full overflow-x-auto px-0 py-2 text-[11.5px] leading-5">
                {ev.excerpt.split("\n").map((line, j) => (
                  <div key={j} className="flex"><span className="w-12 shrink-0 select-none pr-3 text-right text-[hsl(215_14%_50%)]">{ev.line_start + j}</span><span className="pr-3">{line || " "}</span></div>
                ))}
              </pre>
              <div className="num truncate border-t border-white/10 px-3 py-1 text-[10px] text-[hsl(215_14%_60%)]" title={ev.sha256}>sha256 {ev.sha256}</div>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

export function KV({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-dashed border-border py-1.5 text-sm last:border-0">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="min-w-0 break-words text-right">{children}</dd>
    </div>
  );
}
