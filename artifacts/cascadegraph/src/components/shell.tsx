import { type ReactNode, useEffect, useState } from "react";
import { Link, useLocation } from "wouter";
import { BookOpen, FileText, FlaskConical, GitCompare, Home, Network, ShieldCheck, SlidersHorizontal, Menu, X } from "lucide-react";
import { useGetSystemStatus } from "@workspace/api-client-react";
import { cn } from "@/lib/utils";
import { readSelection, type Selection } from "@/lib/workspace";

function useSelection(): Selection {
  const [sel, setSel] = useState<Selection>(readSelection);
  useEffect(() => {
    const h = () => setSel(readSelection());
    window.addEventListener("cg-selection", h);
    window.addEventListener("storage", h);
    return () => { window.removeEventListener("cg-selection", h); window.removeEventListener("storage", h); };
  }, []);
  return sel;
}

export function Shell({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const sel = useSelection();
  const [open, setOpen] = useState(false);
  const status = useGetSystemStatus();
  useEffect(() => setOpen(false), [location]);
  const a = sel.analysisId;
  const s = sel.simulationId;
  const items: { href: string | null; label: string; icon: typeof Home; match: string; hint?: string }[] = [
    { href: "/", label: "Overview", icon: Home, match: "/" },
    { href: a ? `/analyses/${a}` : null, label: "Service graph", icon: Network, match: "/analyses", hint: "select an analysis" },
    { href: a ? `/policies/${a}` : null, label: "Policies", icon: SlidersHorizontal, match: "/policies", hint: "select an analysis" },
    { href: a ? `/simulation/${a}` : null, label: "Simulation", icon: FlaskConical, match: "/simulation", hint: "select an analysis" },
    { href: s ? `/comparison/${s}` : null, label: "Comparison", icon: GitCompare, match: "/comparison", hint: "run a simulation" },
    { href: a ? `/reports/${a}` : null, label: "Report", icon: FileText, match: "/reports", hint: "select an analysis" },
    { href: "/validation", label: "Validation", icon: ShieldCheck, match: "/validation" },
    { href: "/help", label: "Scope & limits", icon: BookOpen, match: "/help" },
  ];
  const nav = (
    <nav aria-label="Workspace" className="flex flex-col gap-0.5 px-2">
      {items.map((it, i) => {
        const active = it.match === "/" ? location === "/" : location.startsWith(it.match);
        const Icon = it.icon;
        const inner = (
          <>
            <span className="num w-5 text-[10px] text-sidebar-foreground/40">{String(i + 1).padStart(2, "0")}</span>
            <Icon className="h-4 w-4" />
            <span className="flex-1">{it.label}</span>
          </>
        );
        if (!it.href) {
          return (
            <span key={it.label} aria-disabled="true" title={it.hint} className="flex cursor-not-allowed items-center gap-2.5 rounded-sm px-2.5 py-2 text-sm text-sidebar-foreground/35" data-testid={`link-nav-${it.match.replace("/", "") || "home"}`}>
              {inner}
            </span>
          );
        }
        return (
          <Link key={it.label} href={it.href} data-testid={`link-nav-${it.match.replace("/", "") || "home"}`}
            className={cn("relative flex items-center gap-2.5 rounded-sm px-2.5 py-2 text-sm transition-colors",
              active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground")}>
            {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-sidebar-primary" />}
            {inner}
          </Link>
        );
      })}
    </nav>
  );
  const side = (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <Link href="/" className="flex items-center gap-2.5 px-4 py-5" data-testid="link-brand">
        <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden>
          <circle cx="5" cy="14" r="3" fill="hsl(var(--sidebar-primary))" />
          <circle cx="23" cy="6" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="23" cy="22" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 13 L20 7 M8 15 L20 21" stroke="currentColor" strokeWidth="1.5" />
          <path d="M14 10 l2 -1 M14 18 l2 1" stroke="hsl(var(--sidebar-primary))" strokeWidth="2" />
        </svg>
        <div>
          <div className="font-display text-[17px] font-bold leading-none">CascadeGraph</div>
          <div className="num mt-1 text-[10px] uppercase tracking-[0.16em] text-sidebar-foreground/50">retry workbench</div>
        </div>
      </Link>
      {nav}
      <div className="mt-auto space-y-1 border-t border-sidebar-border px-4 py-3 text-[11px]">
        <div className="num flex justify-between text-sidebar-foreground/55"><span>api</span><span data-testid="text-api-version">{status.data ? `v${status.data.version}` : status.isError ? "unreachable" : "…"}</span></div>
        <div className="num flex justify-between text-sidebar-foreground/55"><span>model</span><span>{status.data?.model_version ?? "…"}</span></div>
        <div className="num flex justify-between text-sidebar-foreground/55"><span>ai</span><span data-testid="text-ai-availability">{status.data ? (status.data.ai_available ? `available · ${status.data.ai_provider}` : "not configured") : "…"}</span></div>
      </div>
    </div>
  );
  return (
    <div className="min-h-[100dvh] bg-background md:grid md:grid-cols-[232px_1fr]">
      <aside className="sticky top-0 hidden h-[100dvh] md:block">{side}</aside>
      <div className="flex items-center justify-between bg-sidebar px-4 py-3 text-sidebar-foreground md:hidden">
        <span className="font-display font-bold">CascadeGraph</span>
        <button onClick={() => setOpen(!open)} aria-label="Toggle navigation" data-testid="button-mobile-nav">{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
      </div>
      {open && <div className="fixed inset-x-0 top-12 bottom-0 z-40 md:hidden">{side}</div>}
      <main className="min-w-0 px-4 py-6 md:px-8 md:py-8"><div className="mx-auto max-w-[1280px] space-y-6">{children}</div></main>
    </div>
  );
}
