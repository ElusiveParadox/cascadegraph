import { Link } from "wouter";
import type { Analysis } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/common";

export function SourceNeeds({ analysis }: { analysis: Analysis }) {
  const repository = analysis.repository;
  const needed = analysis.requested_files ?? [];
  const query = new URLSearchParams();
  if (repository) {
    query.set("repository", repository.repository_url);
    query.set("ref", repository.commit_sha);
    query.set("project", repository.project_path);
  }
  if (!repository && needed.length === 0) return null;
  return (
    <Panel title={needed.length ? "Additional source needed" : "Repository snapshot"} className={needed.length ? "border-chart-3/50" : undefined}>
      {repository && <div className="mb-3 space-y-1 text-xs">
        <a href={`${repository.repository_url}/commit/${repository.commit_sha}`} target="_blank" rel="noreferrer" className="break-all text-primary hover:underline" data-testid="link-repository-commit">{repository.repository_url}</a>
        <p className="num break-all" data-testid="text-repository-commit">Commit {repository.commit_sha} · project {repository.project_path}</p>
        {repository.supplemented_paths.length > 0 && <p className="break-all text-muted-foreground">User-supplied overrides: {repository.supplemented_paths.join(", ")}. Those files are not claimed to be from this commit.</p>}
      </div>}
      {needed.length > 0 && <div className="space-y-3">
        <p className="text-sm text-muted-foreground">Analysis has started, but the following evidence is missing or ambiguous. No service calls or retry values will be invented.</p>
        <ul className="list-inside list-disc space-y-1 text-xs" data-testid="list-requested-files">{needed.map(item => <li key={item}>{item}</li>)}</ul>
        <Button asChild size="sm" variant="outline"><Link href={`/?${query}`} data-testid="link-add-source-files">Add source files / choose project folder</Link></Button>
        <p className="text-[11px] text-muted-foreground">This starts a new analysis. Raw sources are not retained; a public repository is re-fetched at the same commit and your files are merged for that request only. For an archive/files-only analysis, select all necessary source files again.</p>
      </div>}
    </Panel>
  );
}
