import type { ReactNode } from "react";
import "./_group.css";

// Extracted from the app's common.tsx before the visual refresh.
function PageHeader({ kicker, title, children, actions }: { kicker: string; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="rise flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <div className="num text-[11px] uppercase tracking-[0.18em] text-primary">{kicker}</div>
        <h1 className="font-display mt-1 [overflow-wrap:anywhere] text-2xl font-bold md:text-3xl" data-testid="text-page-title">{title}</h1>
        {children && <div className="mt-2 max-w-3xl text-sm text-muted-foreground">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Current() {
  return (
    <div className="cg-current min-h-screen p-8">
      <PageHeader kicker="00 / overview" title="Where do your retries multiply?">
        Point CascadeGraph at service source. It extracts retry policies with file and line evidence, builds the call graph, and replays seeded failure scenarios so you can compare a baseline against a candidate policy.
      </PageHeader>
    </div>
  );
}
