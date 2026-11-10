import { type ReactNode, useEffect } from "react";
import { Link } from "wouter";
import { getGetAnalysisQueryKey, useGetAnalysis, type Analysis } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorPanel, LoadingBlock } from "@/components/common";
import { writeSelection } from "@/lib/workspace";

export function WithAnalysis({ id, children }: { id: string; children: (a: Analysis) => ReactNode }) {
  const q = useGetAnalysis(id, { query: { enabled: !!id, queryKey: getGetAnalysisQueryKey(id) } });
  useEffect(() => { if (q.data) writeSelection({ analysisId: q.data.id }); }, [q.data]);
  if (q.isLoading) return <LoadingBlock rows={5} />;
  if (q.isError) {
    const status = (q.error as { status?: number } | null)?.status;
    if (status === 404) {
      return <EmptyState title="Analysis not found" action={<Button asChild variant="outline"><Link href="/" data-testid="link-back-overview">Back to overview</Link></Button>}>
        It may have expired, been deleted, or belong to a different browser session.
      </EmptyState>;
    }
    return <ErrorPanel error={q.error} onRetry={() => q.refetch()} title="Could not load analysis" />;
  }
  if (!q.data) return null;
  return <>{children(q.data)}</>;
}
