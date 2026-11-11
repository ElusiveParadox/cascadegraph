import { useRef, useState } from "react";
import { Link, useLocation, useSearch } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowRight, Box, Trash2, Upload } from "lucide-react";
import {
  getListAnalysesQueryKey, useCreateAnalysis, useDeleteAnalysis, useGetSystemStatus, useListAnalyses, useUploadArchive, type Analysis,
} from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { SourceIntake } from "@/components/source-intake";
import { FileDropZone } from "@/components/file-drop-zone";
import { archiveSelectionError } from "@/lib/file-intake";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { EmptyState, ErrorPanel, LoadingBlock, PageHeader, Panel, Tag, severityTone } from "@/components/common";
import { useToast } from "@/hooks/use-toast";
import { fmtDate, readSelection, writeSelection } from "@/lib/workspace";
import { useAuthState } from "@/lib/auth-context";
import { useOwnAi } from "@/lib/use-own-ai";

function AiOptIn({ id, checked, onChange, available }: { id: string; checked: boolean; onChange: (v: boolean) => void; available: boolean | undefined }) {
  const ownAi = useOwnAi();
  return (
    <div className="rounded-md border border-dashed border-input/70 bg-muted/50 p-3.5">
      <label htmlFor={id} className="flex items-start gap-2.5 text-sm">
        <Checkbox id={id} checked={checked} disabled={!available} onCheckedChange={(v) => onChange(v === true)} data-testid={`checkbox-${id}`} className="mt-0.5" />
        <span>
          <span className="font-medium">Use AI-assisted extraction</span> <Tag tone={available ? "warn" : "info"}>{available ? "opt-in, billed" : "unavailable"}</Tag>
          <span className="mt-1 block text-xs text-muted-foreground">
            {available
              ? `Relevant source excerpts are sent to ${ownAi ? `${ownAi.provider} using your key, billed by that provider` : "the managed model provider, billed to your Replit credits"}. Deterministic parsing runs either way. Leave unchecked to avoid AI requests.`
              : "No managed AI provider is available. Add your own API key in AI settings, or use deterministic parsing."}
          </span>
        </span>
      </label>
      <Link href="/settings/ai" className="mt-2 inline-flex text-xs text-primary underline underline-offset-2">AI settings · use your own API key</Link>
    </div>
  );
}

export default function Overview() {
  const ownAi = useOwnAi();
  const { signedIn } = useAuthState();
  const qc = useQueryClient();
  const [, nav] = useLocation();
  const parameters = new URLSearchParams(useSearch());
  const { toast } = useToast();
  const status = useGetSystemStatus();
  const list = useListAnalyses();
  const [sampleAi, setSampleAi] = useState(false);
  const [zipAi, setZipAi] = useState(false);
  const [zipProject, setZipProject] = useState(".");
  const [importBusy, setImportBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; name: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onCreated = (a: Analysis) => {
    qc.invalidateQueries({ queryKey: getListAnalysesQueryKey() });
    writeSelection({ analysisId: a.id, simulationId: undefined });
    nav(`/analyses/${a.id}`);
  };
  const create = useCreateAnalysis({ mutation: { onSuccess: onCreated } });
  const upload = useUploadArchive({ mutation: { onSuccess: onCreated } });
  const del = useDeleteAnalysis({
    mutation: {
      onSuccess: (_d, vars) => {
        qc.invalidateQueries({ queryKey: getListAnalysesQueryKey() });
        if (readSelection().analysisId === vars.analysisId) writeSelection({ analysisId: undefined, simulationId: undefined });
        toast({ title: "Analysis deleted", description: "Source-derived data and simulations were removed." });
      },
      onError: (e) => toast({ title: "Delete failed", description: e instanceof Error ? e.message : String(e), variant: "destructive" }),
    },
  });
  // Settle both initial cookie-setting reads before creating session-owned data.
  const ready = list.isSuccess && status.isSuccess;
  const busy = create.isPending || upload.isPending || importBusy || !ready;
  const maxMb = status.data?.max_archive_mb;
  const tooBig = !!(file && maxMb && file.size > maxMb * 1024 * 1024);
  const selectArchive = (incoming: File[]) => {
    if (busy || !status.data || !incoming.length) return;
    const error = archiveSelectionError(incoming, status.data);
    setArchiveError(error);
    if (!error) setFile(incoming[0]);
  };

  return (
    <>
      <PageHeader kicker="overview" title="Where do your retries multiply?">
        Point CascadeGraph at service source. It extracts retry policies with file and line evidence, builds the call graph, and replays seeded failure scenarios so you can compare a baseline against a candidate policy.
      </PageHeader>

      {(create.isPending || upload.isPending || importBusy) && (
        <div className="rise relative overflow-hidden rounded-md border border-primary/40 bg-primary/5 p-4" role="status" data-testid="status-processing">
          <div className="text-sm font-semibold">Analyzing {create.isPending ? "bundled sample" : importBusy ? "repository / source files" : file?.name}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">Parsing runs synchronously within a bounded file and size budget. The result appears when the request returns; there is no partial progress to report.</div>
          <div className="mt-3 h-[3px] overflow-hidden rounded bg-primary/15"><div className="scanbar h-full w-1/3 bg-primary" /></div>
        </div>
      )}
      {create.isError && <ErrorPanel error={create.error} title="Sample analysis failed" />}
      {upload.isError && <ErrorPanel error={upload.error} title="Archive analysis failed" />}
      {!ready && (status.isError || list.isError
        ? <ErrorPanel error={status.error ?? list.error} title="Workspace could not be initialized" onRetry={() => { status.refetch(); list.refetch(); }} />
        : <p role="status" className="text-xs text-muted-foreground">Preparing browser session and server limits…</p>)}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,1fr)]">
        <SourceIntake limits={status.data} disabled={create.isPending || upload.isPending || !ready} onBusyChange={setImportBusy} onAnalyzed={onCreated}
          initialRepository={parameters.get("repository") ?? ""} initialRef={parameters.get("ref") ?? ""} initialProject={parameters.get("project") ?? "."} />

      <div className="grid min-w-0 gap-5 lg:grid-cols-2 xl:grid-cols-1">
        <Panel title={<span className="flex items-center gap-2"><Box className="h-3.5 w-3.5" />Bundled sample</span>} meta="no upload">
          <p className="text-sm text-muted-foreground">A small multi-service repository with known retry layering. Useful to learn the workflow before uploading your own code.</p>
          <div className="mt-3"><AiOptIn id="sample-ai" checked={sampleAi} onChange={setSampleAi} available={!!ownAi || status.data?.ai_available} /></div>
          <Button className="mt-3" disabled={busy} data-testid="button-analyze-sample"
            onClick={() => create.mutate({ data: { source_type: "sample", use_ai: sampleAi && (!!ownAi || !!status.data?.ai_available) } })}>
            Analyze sample <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
        </Panel>
        <Panel title={<span className="flex items-center gap-2"><Archive className="h-3.5 w-3.5" />ZIP archive</span>} meta={status.data ? `≤ ${status.data.max_archive_mb} MiB · ≤ ${status.data.max_files} files` : "limits loading"}>
          <FileDropZone disabled={busy} onFiles={selectArchive} testId="drop-archive">
          <button type="button" disabled={busy} onClick={() => fileRef.current?.click()} data-testid="button-choose-archive"
            className="grid-paper flex w-full flex-col items-center gap-1 rounded-md border border-dashed border-input px-4 py-6 text-sm transition-colors hover:border-primary hover:bg-primary/[0.03]">
            <Upload className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Choose a .zip of your repository</span>
          </button>
          <input ref={fileRef} type="file" accept=".zip,application/zip" disabled={busy} className="hidden" data-testid="input-archive"
            onChange={(e) => { selectArchive(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
          <p role="status" className="num mt-2 break-all text-xs text-muted-foreground">{file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KiB selected` : "No ZIP selected."}</p>
          {file && <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => { setFile(null); setArchiveError(null); }}>Remove ZIP</Button>}
          {archiveError && <p role="alert" className="mt-2 text-xs text-destructive">{archiveError} Your previous selection is unchanged.</p>}
          {tooBig && <p role="alert" className="mt-2 text-xs text-destructive">File exceeds the {maxMb} MiB server limit.</p>}
          </FileDropZone>
          <label className="mt-3 block text-xs font-medium">Project folder inside ZIP <span className="font-normal text-muted-foreground">optional</span>
            <Input value={zipProject} maxLength={200} onChange={e => setZipProject(e.target.value)} placeholder="e.g. sample-app" className="num mt-1" data-testid="input-zip-project" />
          </label>
          <div className="mt-3"><AiOptIn id="zip-ai" checked={zipAi} onChange={setZipAi} available={!!ownAi || status.data?.ai_available} /></div>
          <Button className="mt-3" variant="secondary" disabled={!file || busy || tooBig} data-testid="button-upload-archive"
            onClick={() => file && upload.mutate({ data: { file, use_ai: zipAi && (!!ownAi || !!status.data?.ai_available), project_path: zipProject.trim() || "." } })}>
            Upload and analyze
          </Button>
          <p className="mt-2 text-[11px] text-muted-foreground">ZIPs may contain irrelevant binary assets; they are skipped without execution. Supported source, expansion and entry-count limits still apply.</p>
        </Panel>
      </div>
      </div>

      <Panel title={signedIn ? "Account history" : "Session history"} meta={list.data ? `${list.data.length} analyses` : undefined}>
        <p className="mb-3 text-xs text-muted-foreground">
          {signedIn ? "Analyses belong to your signed-in account and can be reopened on another device." : "Guest analyses belong to this browser session and are not automatically transferred when you sign in."}
          {" "}All analyses expire after 24 hours{status.data ? ` (storage: ${status.data.storage})` : ""}.
        </p>
        {list.isLoading ? <LoadingBlock rows={3} /> : list.isError ? <ErrorPanel error={list.error} onRetry={() => list.refetch()} /> :
          !list.data?.length ? <EmptyState title={signedIn ? "No analyses in this account" : "No analyses in this session"}>Start with the bundled sample above to see the full workflow.</EmptyState> : (
          <div className="overflow-x-auto scroll-p-1" onFocusCapture={(event) => {
            // Browsers can consider a partially clipped table control visible.
            // Reveal the entire focused control, including the final column.
            if (event.target instanceof HTMLElement) {
              event.target.scrollIntoView({ block: "nearest", inline: "nearest" });
            }
          }}>
            <table className="w-full text-sm">
              <thead><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Name</th><th className="py-2 pr-3 font-medium">Status</th><th className="py-2 pr-3 text-right font-medium">Files</th>
                <th className="py-2 pr-3 text-right font-medium">Services</th><th className="py-2 pr-3 text-right font-medium">Policies</th><th className="py-2 pr-3 font-medium">Created</th><th className="py-2 pr-3 font-medium">Expires</th><th />
              </tr></thead>
              <tbody>
                {list.data.map((a) => (
                  <tr key={a.id} className="group border-b border-dashed border-border last:border-0 hover:bg-muted/40" data-testid={`row-analysis-${a.id}`}>
                    <td className="py-2 pr-3"><Link href={`/analyses/${a.id}`} onClick={() => writeSelection({ analysisId: a.id })} className="font-medium hover:text-primary" data-testid={`link-analysis-${a.id}`}>{a.name}</Link>
                      <div className="num text-[10.5px] text-muted-foreground">{a.source_type} · {a.id.slice(0, 8)}</div></td>
                    <td className="py-2 pr-3"><Tag tone={severityTone(a.status)}>{a.status}</Tag></td>
                    <td className="num py-2 pr-3 text-right">{a.file_count}</td>
                    <td className="num py-2 pr-3 text-right">{a.service_count}</td>
                    <td className="num py-2 pr-3 text-right">{a.policy_count}</td>
                    <td className="py-2 pr-3 text-xs">{fmtDate(a.created_at)}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{fmtDate(a.expires_at)}</td>
                    <td className="py-2 text-right">
                      <Button size="icon" variant="ghost" aria-label={`Delete ${a.name}`} data-testid={`button-delete-${a.id}`} disabled={del.isPending}
                        onClick={() => setPendingDelete({ id: a.id, name: a.name })}><Trash2 className="h-4 w-4" /></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{pendingDelete?.name}”?</AlertDialogTitle>
            <AlertDialogDescription>This removes the analysis, its confirmations and all simulations. It cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="button-cancel-delete">Cancel</AlertDialogCancel>
            <AlertDialogAction data-testid="button-confirm-delete" className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => pendingDelete && del.mutate({ analysisId: pendingDelete.id })}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
