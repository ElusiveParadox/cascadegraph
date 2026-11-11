import { Link, useLocation } from "wouter";
import { ArrowLeft, KeyRound, UserRound } from "lucide-react";
import { KV, LoadingBlock, PageHeader, Panel, Tag } from "@/components/common";
import { Button } from "@/components/ui/button";
import { useAuthState } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import AiSettingsPage from "@/pages/ai-settings";

function AccountSettings() {
  const auth = useAuthState();
  if (!auth.ready) return <LoadingBlock rows={2} />;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Account">
        <dl data-testid="text-settings-account">
          <KV k="Session"><Tag>{auth.signedIn ? "Signed in" : "Guest"}</Tag></KV>
          {auth.signedIn && auth.displayName && <KV k="Name">{auth.displayName}</KV>}
          {auth.signedIn && auth.email && <KV k="Email"><span className="break-all">{auth.email}</span></KV>}
        </dl>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          {auth.signedIn
            ? "Your analyses belong to this account. To end this session, use Sign out at the bottom of the sidebar."
            : "You are using a guest session. Guest analyses are separate from account analyses and are not transferred automatically when you sign in."}
        </p>
        {!auth.signedIn && auth.available && (
          <Button asChild className="mt-4" size="sm"><Link href="/sign-in" data-testid="link-settings-sign-in">Sign in</Link></Button>
        )}
        {!auth.available && <p className="mt-3 text-sm text-muted-foreground">Sign-in is unavailable in this environment.</p>}
      </Panel>
      <Panel title="Privacy & API keys">
        <p className="text-sm leading-relaxed text-muted-foreground">Your own AI API key stays in this tab's memory. It is not saved in the database, cookies or browser storage. Refreshing or signing out clears it.</p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">AI-assisted extraction is optional for each analysis. Requests using your key are billed by your selected provider.</p>
        <Link href="/settings/ai" data-testid="link-settings-manage-ai" className="mt-4 inline-flex text-sm font-medium text-primary underline underline-offset-4">Manage AI settings</Link>
      </Panel>
    </div>
  );
}

export default function SettingsPage() {
  const [location] = useLocation();
  const auth = useAuthState();
  const account = location === "/settings/account";
  const tabs = [
    { href: "/settings/ai", label: "AI settings", icon: KeyRound, active: !account, id: "ai" },
    { href: "/settings/account", label: "Account & privacy", icon: UserRound, active: account, id: "account" },
  ];
  return (
    <>
      <PageHeader kicker="Preferences" title="Settings"
        actions={<Button asChild variant="outline" size="sm"><Link href={auth.signedIn ? "/workspace" : "/"} data-testid="link-back-workbench"><ArrowLeft className="mr-1.5 h-3.5 w-3.5" />Back to workbench</Link></Button>}>
        Manage your AI provider and view your account and privacy information.
      </PageHeader>
      <nav aria-label="Settings sections" className="flex flex-wrap gap-1 border-b border-border">
        {tabs.map(({ href, label, icon: Icon, active, id }) => (
          <Link key={id} href={href} aria-current={active ? "page" : undefined} data-testid={`link-settings-${id}`}
            className={cn("-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
              active ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:border-primary/40")}>
            <Icon className="h-4 w-4" />{label}
          </Link>
        ))}
      </nav>
      {account ? <AccountSettings /> : <AiSettingsPage />}
    </>
  );
}
