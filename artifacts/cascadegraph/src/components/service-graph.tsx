import { useMemo } from "react";
import type { DependencyEdge, ServiceNode } from "@workspace/api-client-react";
import { layoutGraph } from "@/lib/workspace";

export type GraphSelection = { kind: "node" | "edge"; id: string } | null;

export function ServiceGraph({ nodes, edges, selected, onSelect, hot }: {
  nodes: ServiceNode[]; edges: DependencyEdge[]; selected: GraphSelection; onSelect: (s: GraphSelection) => void; hot?: Set<string>;
}) {
  const { pos, width, height } = useMemo(() => layoutGraph(nodes.map((n) => n.id), edges), [nodes, edges]);
  if (!nodes.length) return null;
  return (
    <div className="grid-paper overflow-x-auto rounded-sm border border-border">
      <svg role="img" aria-label="Service dependency graph. Layout is structural, not quantitative." viewBox={`0 0 ${Math.max(width, 400)} ${Math.max(height, 140)}`} className="min-w-[480px] w-full" style={{ maxHeight: 460 }}>
        <defs>
          <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" fill="hsl(var(--foreground) / .55)" /></marker>
          <marker id="arr-hot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" fill="hsl(var(--primary))" /></marker>
        </defs>
        {edges.map((e) => {
          const a = pos.get(e.source); const b = pos.get(e.target);
          if (!a || !b) return null;
          const sel = selected?.kind === "edge" && selected.id === e.id;
          const retry = e.policy_ids.length > 0;
          const x1 = a.x + 62, x2 = b.x - 64, mx = (x1 + x2) / 2;
          const d = `M${x1} ${a.y} C${mx} ${a.y}, ${mx} ${b.y}, ${x2} ${b.y}`;
          const stroke = retry ? "hsl(var(--primary))" : "hsl(var(--foreground) / .45)";
          return (
            <g key={e.id} className="cursor-pointer" onClick={() => onSelect({ kind: "edge", id: e.id })} data-testid={`graph-edge-${e.id}`}
               tabIndex={0} role="button" aria-label={`Edge ${e.source} to ${e.target}, ${e.evidence_kind}${e.confirmed ? ", confirmed" : ""}`}
               onKeyDown={(k) => { if (k.key === "Enter" || k.key === " ") onSelect({ kind: "edge", id: e.id }); }}>
              <path d={d} stroke="transparent" strokeWidth={14} fill="none" />
              {sel && <path d={d} stroke="hsl(var(--ring) / .25)" strokeWidth={8} fill="none" />}
              <path d={d} stroke={stroke} strokeWidth={sel ? 2.2 : 1.5} fill="none" markerEnd={retry ? "url(#arr-hot)" : "url(#arr)"}
                className={retry ? "edge-flow" : undefined} strokeDasharray={!e.confirmed && !retry ? "2 4" : undefined} />
              {retry && <text x={mx} y={(a.y + b.y) / 2 - 6} textAnchor="middle" className="num" fontSize="9.5" fill="hsl(var(--primary))">retry ×{e.policy_ids.length}</text>}
            </g>
          );
        })}
        {nodes.map((n) => {
          const p = pos.get(n.id)!;
          const sel = selected?.kind === "node" && selected.id === n.id;
          return (
            <g key={n.id} transform={`translate(${p.x - 62} ${p.y - 18})`} className="cursor-pointer" tabIndex={0} role="button"
               aria-label={`Service ${n.name}`} data-testid={`graph-node-${n.id}`}
               onClick={() => onSelect({ kind: "node", id: n.id })}
               onKeyDown={(k) => { if (k.key === "Enter" || k.key === " ") onSelect({ kind: "node", id: n.id }); }}>
              <rect width="124" height="36" rx="4" fill="hsl(var(--card))" stroke={sel ? "hsl(var(--ring))" : "hsl(var(--foreground) / .5)"} strokeWidth={sel ? 2 : 1} />
              {hot?.has(n.id) && <rect width="4" height="36" rx="1" fill="hsl(var(--primary))" />}
              <text x="62" y="16" textAnchor="middle" fontSize="12" fontWeight={600} fill="hsl(var(--foreground))">{n.name.length > 16 ? n.name.slice(0, 15) + "…" : n.name}</text>
              <text x="62" y="29" textAnchor="middle" fontSize="9" className="num" fill="hsl(var(--muted-foreground))">{n.evidence.length} evidence</text>
            </g>
          );
        })}
      </svg>
      <div className="num flex flex-wrap gap-4 border-t border-border bg-card/80 px-3 py-1.5 text-[10.5px] text-muted-foreground">
        <span><span className="mr-1 inline-block h-[2px] w-5 bg-primary align-middle" />edge with retry policy</span>
        <span><span className="mr-1 inline-block h-[2px] w-5 bg-foreground/45 align-middle" />dependency</span>
        <span>dotted: declared or inferred, unconfirmed</span>
        <span>position encodes call depth only</span>
      </div>
    </div>
  );
}
