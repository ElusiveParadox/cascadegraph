import { useSyncExternalStore } from "react";
import { getOwnAiState, subscribeOwnAi } from "@workspace/api-client-react";

export function useOwnAi() {
  return useSyncExternalStore(subscribeOwnAi, getOwnAiState, () => null);
}
