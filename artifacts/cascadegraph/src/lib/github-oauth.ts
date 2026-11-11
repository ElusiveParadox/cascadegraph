export function githubOAuthParams(origin: string, basePath: string) {
  const base = basePath.replace(/\/$/, "");
  return {
    strategy: "oauth_github" as const,
    redirectCallbackUrl: `${origin}${base}/auth/callback`,
    redirectUrl: `${origin}${base}/workspace`,
  };
}

/** Classify by stable codes only; never display raw OAuth errors or their cause. */
export function githubOAuthError(error: unknown): string {
  function unavailable(value: unknown, depth = 0): boolean {
    if (!value || typeof value !== "object" || depth > 2) return false;
    const entry = value as Record<string, unknown>;
    const code = typeof entry.code === "string" ? entry.code : "";
    const meta = entry.meta && typeof entry.meta === "object"
      ? entry.meta as Record<string, unknown> : {};
    if (/strategy.*(invalid|unsupported|disabled|not_supported)|oauth.*(disabled|not_enabled|not_supported)/.test(code)
      || (code === "form_param_value_invalid" && (meta.paramName === "strategy" || meta.param_name === "strategy"))) return true;
    return (Array.isArray(entry.errors) && entry.errors.slice(0, 10).some(item => unavailable(item, depth + 1)))
      || unavailable(entry.cause, depth + 1);
  }
  return unavailable(error)
    ? "GitHub sign-in is not enabled by the sign-in service yet. You can still use Google or email."
    : "GitHub sign-in could not start. Try again, or continue with Google or email.";
}
