import { type ReactNode, useEffect, useId, useRef, useState } from "react";
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
  const navigationId = useId();
  const compactNavigation = useRef<HTMLDivElement>(null);
  const navigationToggle = useRef<HTMLButtonElement>(null);
  const status = useGetSystemStatus();
  useEffect(() => setOpen(false), [location]);
  useEffect(() => {
    if (!open) return;
    const container = compactNavigation.current!;
    const toggle = navigationToggle.current!;
    const desktop = window.matchMedia("(min-width: 768px)");
    const links = () => Array.from(container.querySelectorAll<HTMLAnchorElement>("a[href]"));
    // The close toggle stays in the focus loop alongside the enabled links.
    const focusable = () => [toggle, ...links()];
    const focusFirstLink = () => (links()[0] ?? toggle).focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      } else if (event.key === "Tab") {
        const targets = focusable();
        const index = targets.indexOf(document.activeElement as HTMLButtonElement | HTMLAnchorElement);
        if (index === -1 || (!event.shiftKey && index === targets.length - 1) || (event.shiftKey && index === 0)) {
          event.preventDefault();
          (event.shiftKey ? targets[targets.length - 1] : targets[0]).focus();
        }
      }
    };
    const onFocusIn = (event: FocusEvent) => {
      if (!container.contains(event.target as Node)) focusFirstLink();
    };
    const onResize = () => {
      if (desktop.matches) setOpen(false);
    };
    focusFirstLink();
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("focusin", onFocusIn);
    desktop.addEventListener("change", onResize);
    onResize();
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("focusin", onFocusIn);
      desktop.removeEventListener("change", onResize);
      // Never return focus to the hidden compact toggle on a desktop resize.
      if (!desktop.matches) toggle.focus();
    };
  }, [open]);
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
    <nav aria-label="Workspace" className="flex flex-col gap-0.5 px-3">
      <div className="px-2.5 pb-2 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-sidebar-foreground/55">Workflow</div>
      {items.map((it, i) => {
        const active = it.match === "/" ? location === "/" : location.startsWith(it.match);
        const Icon = it.icon;
        const inner = (
          <>
            <span className="num w-5 text-[10px] text-sidebar-foreground/50">{String(i + 1).padStart(2, "0")}</span>
            <Icon className="h-4 w-4" />
            <span className="flex-1">{it.label}</span>
          </>
        );
        if (!it.href) {
          return (
            <span key={it.label} aria-disabled="true" title={it.hint} className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-sidebar-foreground/45" data-testid={`link-nav-${it.match.replace("/", "") || "home"}`}>
              {inner}
            </span>
          );
        }
        return (
          <Link key={it.label} href={it.href} data-testid={`link-nav-${it.match.replace("/", "") || "home"}`} aria-current={active ? "page" : undefined}
            className={cn("relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors duration-150",
              active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground")}>
            {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-sidebar-primary" />}
            {inner}
          </Link>
        );
      })}
    </nav>
  );
  const side = (
    <div className="flex h-full flex-col overflow-y-auto bg-sidebar text-sidebar-foreground">
      <Link href="/" className="flex items-center gap-2.5 px-4 py-5" data-testid="link-brand">
        <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden>
          <circle cx="5" cy="14" r="3" fill="hsl(var(--sidebar-primary))" />
          <circle cx="23" cy="6" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="23" cy="22" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 13 L20 7 M8 15 L20 21" stroke="currentColor" strokeWidth="1.5" />
          <path d="M14 10 l2 -1 M14 18 l2 1" stroke="hsl(var(--sidebar-primary))" strokeWidth="2" />
        </svg>
        <div>
          <div className="font-display text-[16px] leading-none">CascadeGraph</div>
          <div className="font-editorial mt-1 text-[12px] text-sidebar-foreground/65">retry-policy workbench</div>
        </div>
      </Link>
      {nav}
      <div className="mt-auto space-y-1 border-t border-sidebar-border px-4 py-3 text-[11px]">
        <div className="num flex justify-between text-sidebar-foreground/65"><span>api</span><span data-testid="text-api-version">{status.data ? `v${status.data.version}` : status.isError ? "unreachable" : "…"}</span></div>
        <div className="num flex justify-between text-sidebar-foreground/65"><span>model</span><span>{status.data?.model_version ?? "…"}</span></div>
        <div className="num flex justify-between text-sidebar-foreground/65"><span>ai</span><span data-testid="text-ai-availability">{status.data ? (status.data.ai_available ? `available · ${status.data.ai_provider}` : "not configured") : "…"}</span></div>
      </div>
    </div>
  );
  return (
    <div className="min-h-[100dvh] bg-background md:grid md:grid-cols-[248px_1fr]">
      <a href="#workspace-content" inert={open} className="fixed left-4 top-4 z-50 -translate-y-24 rounded-md bg-primary px-4 py-2 text-primary-foreground shadow-lg focus:translate-y-0">Skip to content</a>
      <aside className="sticky top-0 hidden h-[100dvh] md:block">{side}</aside>
      <div ref={compactNavigation} className="md:hidden">
        <div className="flex items-center justify-between bg-sidebar px-4 py-3 text-sidebar-foreground">
          <span className="font-display">CascadeGraph</span>
          <button ref={navigationToggle} onClick={() => setOpen(!open)} aria-label="Toggle navigation" aria-expanded={open} aria-controls={navigationId} data-testid="button-mobile-nav">{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
        </div>
        <div id={navigationId} hidden={!open} className="fixed inset-x-0 top-12 bottom-0 z-40"
          onClick={event => { if ((event.target as HTMLElement).closest("a[href]")) setOpen(false); }}>
          {open && side}
        </div>
      </div>
      <main id="workspace-content" inert={open} tabIndex={-1} className="min-w-0 px-4 py-6 md:px-10 md:py-10"><div className="mx-auto max-w-[1320px] space-y-7">{children}</div></main>
    </div>
  );
}
