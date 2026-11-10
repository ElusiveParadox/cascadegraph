import { useGetValidation } from "@workspace/api-client-react";
import { ErrorPanel, LoadingBlock, PageHeader, Panel } from "@/components/common";
import { ValidationView } from "@/components/validation-view";

export default function ValidationPage() {
  const q = useGetValidation();
  return (
    <>
      <PageHeader kicker="06 / validation" title="Measured accuracy">
        The simulator is compared in CI against a real retry harness. This page reports exactly what CI recorded: if no run exists, it says so.
      </PageHeader>
      <Panel title="CI measurement">
        {q.isLoading ? <LoadingBlock rows={2} /> : q.isError ? <ErrorPanel error={q.error} onRetry={() => q.refetch()} /> : q.data ? <ValidationView v={q.data} /> : null}
      </Panel>
    </>
  );
}
