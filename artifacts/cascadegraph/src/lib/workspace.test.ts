// Lightweight self-checks; run with: npx tsx src/lib/workspace.test.ts
import { delta, fmtNum, layoutGraph } from "./workspace";
function eq(a: unknown, b: unknown, m: string) { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${m}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`); }
eq(fmtNum(null), "unknown", "null is unknown");
eq(delta(3, 3), "±0", "zero delta");
eq(delta(1, 4), "+3", "positive delta");
const g = layoutGraph(["a", "b", "c"], [{ source: "a", target: "b" }, { source: "b", target: "c" }]);
eq([g.pos.get("a")!.x < g.pos.get("b")!.x, g.pos.get("b")!.x < g.pos.get("c")!.x], [true, true], "layered");
console.log("workspace tests passed");
