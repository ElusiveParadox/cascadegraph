import { useState } from "react";
import { useSignIn } from "@clerk/react";
import { Github, LoaderCircle } from "lucide-react";
import { githubOAuthError, githubOAuthParams } from "@/lib/github-oauth";

const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

/** A real OAuth entry point, even when Clerk's prebuilt UI omits the provider. */
export function GitHubSignIn() {
  const { signIn, fetchStatus } = useSignIn();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = pending || fetchStatus === "fetching";

  async function startGitHub() {
    if (busy || !signIn) return;
    setPending(true);
    setError(null);
    try {
      const result = await signIn.sso(githubOAuthParams(window.location.origin, basePath));
      if (result.error) {
        setError(githubOAuthError(result.error));
      }
    } catch (cause) {
      // Never render/log raw provider errors, tokens, cookies or form values.
      setError(githubOAuthError(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="w-full" data-testid="github-provider-option">
      <button type="button" onClick={startGitHub} disabled={busy || !signIn}
        aria-busy={busy} data-testid="button-sign-in-github"
        className="flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-[#D6D6D9] bg-[#F5F5F2] px-4 py-2 text-sm font-medium text-[#131215] transition-colors hover:border-[#96959A] hover:bg-[#E4E4E6] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E6002B] disabled:cursor-wait disabled:opacity-60">
        {busy ? <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden /> : <Github className="h-4 w-4" aria-hidden />}
        {busy ? "Connecting to GitHub…" : "Continue with GitHub"}
      </button>
      {error && <p role="alert" data-testid="text-github-sign-in-error"
        className="mt-3 text-xs leading-relaxed text-destructive">{error}</p>}
    </div>
  );
}
