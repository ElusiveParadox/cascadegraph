import type { QueryClient } from "@tanstack/react-query";
import { getGetAnalysisQueryKey, getGetReportQueryKey, getListAnalysesQueryKey, type Analysis } from "@workspace/api-client-react";

export function refreshAnalysis(qc: QueryClient, analysisId: string, updated?: Analysis) {
  if (updated) qc.setQueryData(getGetAnalysisQueryKey(analysisId), updated);
  qc.invalidateQueries({ queryKey: getGetAnalysisQueryKey(analysisId) });
  qc.invalidateQueries({ queryKey: getListAnalysesQueryKey() });
  qc.invalidateQueries({ queryKey: getGetReportQueryKey(analysisId) });
}
