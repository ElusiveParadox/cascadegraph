import { useEffect, useState } from "react";
import { FilePlus2, Github, Loader2, X } from "lucide-react";
import { useAnalyzeRepository, useAnalyzeSources, type Analysis, type SystemStatus } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorPanel, Panel } from "@/components/common";
import { FileDropZone } from "@/components/file-drop-zone";
import { SOURCE_ACCEPT, sourceSelectionError } from "@/lib/file-intake";

type SourceFile = { file: File; path: string };
type Props = {
  limits?: SystemStatus;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
  onAnalyzed: (analysis: Analysis) => void;
  initialRepository?: string;
  initialRef?: string;
  initialProject?: string;
};

export function SourceIntake({ limits, disabled, onBusyChange, onAnalyzed, initialRepository = "", initialRef = "", initialProject = "." }: Props) {
  const [url, setUrl] = useState(initialRepository);
  const [ref, setRef] = useState(initialRef);
  const [project, setProject] = useState(initialProject);
  const [files, setFiles] = useState<SourceFile[]>([]);
  const [ai, setAi] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const repository = useAnalyzeRepository({ mutation: { onSuccess: onAnalyzed } });
  const sources = useAnalyzeSources({ mutation: { onSuccess: onAnalyzed } });
  const busy = repository.isPending || sources.isPending;
  useEffect(() => onBusyChange(busy), [busy, onBusyChange]);
  const errors: string[] = [];
  if (!url.trim() && !files.length) errors.push("Paste a public GitHub repository URL or choose source files.");
  if (url.trim() && !/^https:\/\/github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+\/?$/.test(url.trim())) {
    errors.push("Use https://github.com/owner/repository, without credentials or query parameters.");
  }
  const fileError = limits ? sourceSelectionError(files.map(f => f.file), limits) : null;
  if (fileError) errors.push(fileError);
  if (new Set(files.map(f => f.path)).size !== files.length) errors.push("Each uploaded file needs a distinct repository-relative path.");
  if (files.some(f => !f.path.trim() || f.path.startsWith("/") || f.path.includes("..") || f.path.includes("\\"))) {
    errors.push("File paths must be relative, without traversal or backslashes.");
  }
  const intakeDisabled = disabled || busy || !limits;
  const addFiles = (incoming: File[]) => {
    if (intakeDisabled || !limits || !incoming.length) return;
    const error = sourceSelectionError([...files.map(f => f.file), ...incoming], limits);
    setSelectionError(error);
    if (error) return;
    const prefix = project.trim() && project.trim() !== "." ? project.trim().replace(/\/+$/, "") + "/" : "";
    setFiles(current => [...current, ...incoming.map(file => ({ file, path: file.webkitRelativePath || prefix + file.name }))]);
  };
  return (
    <Panel title={<span className="flex items-center gap-2"><Github className="h-4 w-4" />Repository URL / source files</span>} meta="public GitHub · read-only">
      <form className="space-y-4" data-testid="form-source-intake" onSubmit={e => {
        e.preventDefault(); setSubmitted(true);
        if (errors.length || busy || disabled || !limits) return;
        repository.reset(); sources.reset();
        if (files.length) {
          sources.mutate({ data: { files: files.map(f => f.file), paths: files.map(f => f.path.trim()),
            repository_url: url.trim(), ref: ref.trim(), project_path: project.trim() || ".", use_ai: ai && !!limits.ai_available } });
        } else {
          repository.mutate({ data: { repository_url: url.trim(), ref: ref.trim(),
            project_path: project.trim() || ".", use_ai: ai && !!limits.ai_available } });
        }
      }}>
        <p className="text-sm text-muted-foreground">Paste a public repository link to start. CascadeGraph downloads a bounded, commit-pinned snapshot and inspects supported source without running it. If files are missing, the analysis asks for them.</p>
        <label className="block text-xs font-medium">Public GitHub repository URL
          <Input type="url" maxLength={300} value={url} onChange={e => setUrl(e.target.value)} placeholder="https://github.com/owner/repository" className="mt-1" data-testid="input-repository-url" />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-xs font-medium">Branch, tag or commit <span className="font-normal text-muted-foreground">optional</span>
            <Input value={ref} maxLength={200} onChange={e => setRef(e.target.value)} placeholder="Default branch" className="num mt-1" data-testid="input-repository-ref" />
          </label>
          <label className="block text-xs font-medium">Project folder inside repository <span className="font-normal text-muted-foreground">optional</span>
            <Input value={project} maxLength={200} onChange={e => setProject(e.target.value)} placeholder="e.g. sample-app" className="num mt-1" data-testid="input-project-path" />
          </label>
        </div>
        <FileDropZone disabled={intakeDisabled} onFiles={addFiles} testId="drop-source-files">
          <label className="block text-xs font-medium"><FilePlus2 className="mr-1 inline h-3.5 w-3.5" />Add source/configuration files
            <Input type="file" multiple accept={SOURCE_ACCEPT} disabled={intakeDisabled} className="mt-2 max-w-full" data-testid="input-source-files"
              onChange={e => {
                addFiles(Array.from(e.target.files ?? [])); e.target.value = "";
              }} />
          </label>
          {selectionError && <p role="alert" className="mt-2 text-xs text-destructive">{selectionError} No files were added; your previous selection is unchanged.</p>}
          <p role="status" className="num mt-2 text-xs text-muted-foreground">{files.length} source files selected · {(files.reduce((sum, f) => sum + f.file.size, 0) / 1024).toFixed(1)} KiB total</p>
          {limits && <p className="mt-1 text-xs text-muted-foreground">Up to {limits.max_source_files} files · {limits.max_file_kb} KiB each · {limits.max_source_mb} MiB total</p>}
          <p className="mt-2 text-xs text-muted-foreground">Use Python retry/client files, Compose or Istio YAML. Edit each relative path if it belongs in a subfolder. Files supplement or override the public snapshot. For private repositories, leave the URL blank and upload files or a ZIP—never a token.</p>
          {files.length > 0 && <div className="mt-3 space-y-2">
            {files.map((source, index) => (
              <div key={`${source.file.name}-${index}`} className="flex min-w-0 items-center gap-2">
                <div className="min-w-0 flex-1"><span className="block truncate text-[11px] text-muted-foreground">{source.file.name} · {(source.file.size / 1024).toFixed(1)} KiB</span>
                  <Input aria-label={`Relative path for ${source.file.name}`} value={source.path} maxLength={300} className="num mt-1"
                    data-testid={`input-source-path-${index}`} onChange={e => setFiles(current => current.map((f, i) => i === index ? { ...f, path: e.target.value } : f))} /></div>
                <Button type="button" variant="ghost" size="icon" aria-label={`Remove ${source.file.name}`}
                  onClick={() => { setFiles(current => current.filter((_, i) => i !== index)); setSelectionError(null); }}><X className="h-4 w-4" /></Button>
              </div>
            ))}
            {url && <Button type="button" size="sm" variant="outline" onClick={() => { setUrl(""); setRef(""); }}>Use uploaded files only</Button>}
          </div>}
        </FileDropZone>
        <label className="flex items-start gap-2 text-xs">
          <input type="checkbox" checked={ai} disabled={!limits?.ai_available} onChange={e => setAi(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[hsl(var(--primary))]" data-testid="checkbox-repository-ai" />
          <span>Use AI-assisted extraction <span className="num text-[10px] text-primary">OPT-IN, BILLED</span><span className="mt-1 block text-muted-foreground">Optional redacted source excerpts are sent to an external model and billed to credits. Leave unchecked to keep parsing local.</span></span>
        </label>
        {limits && <p className="num text-[10.5px] text-muted-foreground">ZIP/download ≤ {limits.max_archive_mb} MiB · expanded ≤ {limits.max_expanded_mb} MiB · supported source ≤ {limits.max_source_mb} MiB · each source ≤ {limits.max_file_kb} KiB</p>}
        {(submitted || files.length > 0) && errors.length > 0 && <ul role="alert" className="space-y-1 text-xs text-destructive">{errors.map(error => <li key={error}>{error}</li>)}</ul>}
        {repository.isError && <ErrorPanel error={repository.error} title="Repository could not be analyzed" />}
        {sources.isError && <ErrorPanel error={sources.error} title="Source files could not be analyzed" />}
        <Button type="submit" disabled={disabled || busy || !limits} data-testid="button-analyze-repository">
          {busy ? <><Loader2 className="mr-1 h-4 w-4 animate-spin" />Fetching / analyzing source…</> : files.length ? "Analyze source files" : "Analyze repository"}
        </Button>
        <p className="text-[11px] text-muted-foreground">Supported extraction remains Compose, Python Tenacity/urllib3 and Istio. Unsupported languages or ambiguous topology are reported as incomplete—not invented.</p>
      </form>
    </Panel>
  );
}
