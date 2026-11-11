import type { ReactNode } from "react";
import { Link } from "wouter";
import { ArrowLeft } from "lucide-react";
import { SignIn, SignUp } from "@clerk/react";
import { useAuthState } from "@/lib/auth-context";

const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

function AuthFrame({ eyebrow, children }: { eyebrow: string; children: ReactNode }) {
  return (
    <div className="grid-paper flex min-h-[100dvh] flex-col bg-background px-4 py-6">
      <div className="mx-auto flex w-full max-w-[1100px] items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-primary" data-testid="link-auth-home">
          <ArrowLeft className="h-4 w-4" /> Back to workbench
        </Link>
        <span className="font-display text-[15px]">CascadeGraph</span>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center gap-5 py-10">
        <p className="font-editorial text-[15px] text-muted-foreground">{eyebrow}</p>
        <div className="rise w-full">{children}</div>
        <p className="max-w-[440px] text-center text-xs leading-relaxed text-muted-foreground">
          Guest analyses are separate from your account and are not transferred
          automatically. Export any guest reports you want to keep. All analyses
          retain their 24-hour expiry.
        </p>
      </div>
    </div>
  );
}

function Unavailable() {
  return (
    <div className="mx-auto w-[440px] max-w-full rounded-xl border border-card-border bg-card p-7" data-testid="status-auth-unavailable">
      <h1 className="font-display text-xl">Sign-in is not configured here</h1>
      <p className="mt-2 text-muted-foreground">
        This environment has no authentication key, so accounts are unavailable. The workbench still runs as an anonymous browser session; your analyses stay tied to this browser.
      </p>
      <Link href="/" className="mt-5 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground" data-testid="link-auth-unavailable-home">
        Continue without an account
      </Link>
    </div>
  );
}

export function SignInPage() {
  const { available } = useAuthState();
  return (
    <AuthFrame eyebrow="evidence first, conclusions second">
      {available ? <SignIn routing="path" path={`${basePath}/sign-in`} signUpUrl={`${basePath}/sign-up`} /> : <Unavailable />}
    </AuthFrame>
  );
}

export function SignUpPage() {
  const { available } = useAuthState();
  return (
    <AuthFrame eyebrow="keep your analyses with your account">
      {available ? <SignUp routing="path" path={`${basePath}/sign-up`} signInUrl={`${basePath}/sign-in`} /> : <Unavailable />}
    </AuthFrame>
  );
}
