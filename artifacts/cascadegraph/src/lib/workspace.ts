const KEY = "cascadegraph.selection.v1";
export type Selection = { analysisId?: string; simulationId?: string };

export function readSelection(): Selection {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Selection;
  } catch {
    return {};
  }
}

export function writeSelection(patch: Selection) {
  const next = { ...readSelection(), ...patch };
  for (const k of Object.keys(patch) as (keyof Selection)[]) if (patch[k] === undefined) delete next[k];
  localStorage.setItem(KEY, JSON.stringify(next));
  window.dispatchEvent(new Event("cg-selection"));
}

export function errorMessage(e: unknown): string {
  if (!e) return "Unknown error";
  if (e instanceof Error) return e.message;
  return String(e);
}

export function fmtNum(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "unknown";
  return n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function fmtMs(n: number | null | undefined): string {
  return n === null || n === undefined ? "unknown" : `${fmtNum(n)} ms`;
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "unknown";
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function delta(base: number, cand: number): string {
  const d = cand - base;
  if (d === 0) return "±0";
  return `${d > 0 ? "+" : ""}${fmtNum(d, Math.abs(d) < 10 && !Number.isInteger(d) ? 2 : 0)}`;
}

/** Layered layout for a dependency graph: roots (no incoming) on the left. */
export function layoutGraph(nodeIds: string[], edges: { source: string; target: string }[]) {
  const depth = new Map<string, number>();
  const incoming = new Map<string, number>();
  nodeIds.forEach((n) => incoming.set(n, 0));
  edges.forEach((e) => incoming.set(e.target, (incoming.get(e.target) ?? 0) + 1));
  const queue = nodeIds.filter((n) => (incoming.get(n) ?? 0) === 0);
  if (queue.length === 0 && nodeIds.length) queue.push(nodeIds[0]);
  queue.forEach((n) => depth.set(n, 0));
  let guard = 0;
  while (queue.length && guard++ < 10000) {
    const n = queue.shift()!;
    const d = depth.get(n)!;
    for (const e of edges) {
      if (e.source !== n) continue;
      if (!depth.has(e.target) || (depth.get(e.target)! < d + 1 && d + 1 < nodeIds.length)) {
        depth.set(e.target, d + 1);
        queue.push(e.target);
      }
    }
  }
  nodeIds.forEach((n) => { if (!depth.has(n)) depth.set(n, 0); });
  const cols = new Map<number, string[]>();
  nodeIds.forEach((n) => { const d = depth.get(n)!; cols.set(d, [...(cols.get(d) ?? []), n]); });
  const pos = new Map<string, { x: number; y: number }>();
  const colCount = Math.max(...Array.from(cols.keys()), 0) + 1;
  const maxRows = Math.max(...Array.from(cols.values()).map((c) => c.length), 1);
  cols.forEach((ids, d) => ids.forEach((id, i) => pos.set(id, { x: 90 + d * 210, y: 50 + (i + (maxRows - ids.length) / 2) * 90 })));
  return { pos, width: 180 + (colCount - 1) * 210, height: 100 + (maxRows - 1) * 90 };
}
