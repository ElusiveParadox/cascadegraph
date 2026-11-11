export type OwnAiProvider = "openai" | "openrouter";
export type OwnAiConnection = { provider: OwnAiProvider; model: string; apiKey: string };
export type OwnAiState = Readonly<{ provider: OwnAiProvider; model: string }> | null;

let connection: OwnAiConnection | null = null;
let snapshot: OwnAiState = null;
const listeners = new Set<() => void>();

/** Deliberately memory-only. Public snapshots never contain the credential. */
export const getOwnAiState = (): OwnAiState => snapshot;
export function subscribeOwnAi(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function setOwnAiConnection(value: OwnAiConnection | null) {
  if (value) {
    if (!["openai", "openrouter"].includes(value.provider)) throw new Error("Choose a supported provider.");
    if (!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,149}$/.test(value.model)) throw new Error("Enter a valid model ID, up to 150 characters.");
    if (!/^[!-~]{10,1024}$/.test(value.apiKey)) throw new Error("Enter a valid API key without spaces, up to 1024 characters.");
  }
  connection = value ? { ...value } : null;
  snapshot = value ? Object.freeze({ provider: value.provider, model: value.model }) : null;
  listeners.forEach(listener => listener());
}

/** Never forward credentials to external URLs, reads, other routes or non-AI requests. */
export function ownAiHeaders(input: string, method: string, body: BodyInit | null | undefined): Headers {
  const result = new Headers();
  if (!connection || method !== "POST" || !input.startsWith("/") || input.startsWith("//")
    || input.includes("\\") || !/\/api\/v1\/analyses(?:\/(?:archive|sources|repository))?$/.test(input)) return result;
  let optedIn = false;
  if (typeof FormData !== "undefined" && body instanceof FormData) optedIn = body.get("use_ai") === "true";
  else if (typeof body === "string") {
    try { optedIn = JSON.parse(body)?.use_ai === true; } catch { /* Not an AI analysis payload. */ }
  }
  if (optedIn) {
    result.set("X-CascadeGraph-AI-Provider", connection.provider);
    result.set("X-CascadeGraph-AI-Model", connection.model);
    result.set("X-CascadeGraph-AI-Key", connection.apiKey);
  }
  return result;
}
