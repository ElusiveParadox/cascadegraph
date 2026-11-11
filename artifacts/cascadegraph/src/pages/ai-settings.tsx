import { useState, type FormEvent } from "react";
import { Link } from "wouter";
import { ArrowLeft, KeyRound, Trash2 } from "lucide-react";
import { setOwnAiConnection, type OwnAiProvider } from "@workspace/api-client-react";
import { KV, PageHeader, Panel, Tag } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOwnAi } from "@/lib/use-own-ai";

const PROVIDERS: Record<OwnAiProvider, { label: string; model: string }> = {
  openai: { label: "OpenAI", model: "gpt-5.4-mini" },
  openrouter: { label: "OpenRouter", model: "openai/gpt-5.4-mini" },
};

type Feedback = { tone: "ok" | "bad"; text: string } | null;

export default function AiSettingsPage() {
  const active = useOwnAi();
  const [provider, setProvider] = useState<OwnAiProvider>(active?.provider ?? "openai");
  const [model, setModel] = useState(active?.model ?? PROVIDERS[active?.provider ?? "openai"].model);
  const [apiKey, setApiKey] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);

  const changeProvider = (next: OwnAiProvider) => {
    setProvider(next);
    setModel(PROVIDERS[next].model);
    setApiKey("");
    setFeedback(null);
  };

  const apply = (e: FormEvent) => {
    e.preventDefault();
    try {
      setOwnAiConnection({ provider, model: model.trim(), apiKey });
      setApiKey("");
      setFeedback({ tone: "ok", text: `Key held for this tab. ${PROVIDERS[provider].label} will be used when you opt in to AI on an analysis.` });
    } catch (err) {
      setFeedback({ tone: "bad", text: err instanceof Error ? err.message : "The key could not be applied." });
    }
  };

  const remove = () => {
    setOwnAiConnection(null);
    setApiKey("");
    setFeedback({ tone: "ok", text: "Key removed from this tab." });
  };

  return (
    <>
      <PageHeader
        kicker="AI provider"
        title="Use your own AI API key"
        actions={<Button asChild variant="outline" size="sm"><Link href="/" data-testid="link-back-workbench"><ArrowLeft className="mr-1.5 h-3.5 w-3.5" />Back to workbench</Link></Button>}
      >
        Optional. AI-assisted extraction stays off until you tick the opt-in on an analysis form. Choosing a key here sends nothing.
      </PageHeader>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_340px]">
        <Panel title="Key for this tab" meta="memory only">
          <form onSubmit={apply} className="space-y-4" autoComplete="off">
            <div className="grid gap-4 sm:grid-cols-[180px_1fr]">
              <div className="space-y-1.5">
                <Label htmlFor="own-ai-provider">Provider</Label>
                <select
                  id="own-ai-provider"
                  value={provider}
                  onChange={e => changeProvider(e.target.value as OwnAiProvider)}
                  data-testid="select-own-ai-provider"
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {(Object.keys(PROVIDERS) as OwnAiProvider[]).map(p => <option key={p} value={p}>{PROVIDERS[p].label}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="own-ai-model">Model ID</Label>
                <Input id="own-ai-model" value={model} onChange={e => setModel(e.target.value)} required maxLength={150} spellCheck={false} autoComplete="off" className="num" data-testid="input-own-ai-model" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="own-ai-key">API key</Label>
              <Input
                id="own-ai-key"
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                autoComplete="off"
                spellCheck={false}
                aria-describedby="own-ai-key-hint"
                data-testid="input-own-ai-key"
              />
              <p id="own-ai-key-hint" className="text-xs text-muted-foreground">
                Held in this tab's memory only. Not saved to storage, cookies, the URL or our database. Changing provider clears this field.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={!apiKey.trim() || !model.trim()} data-testid="button-use-own-ai"><KeyRound className="mr-1.5 h-3.5 w-3.5" />Use API key</Button>
              <Button type="button" variant="outline" onClick={remove} disabled={!active && !apiKey} data-testid="button-clear-own-ai"><Trash2 className="mr-1.5 h-3.5 w-3.5" />Remove key</Button>
            </div>
            <div aria-live="polite" role={feedback?.tone === "bad" ? "alert" : "status"} data-testid="status-own-ai-feedback">
              {feedback && (
                <p className={feedback.tone === "bad" ? "rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive" : "rounded-md border border-chart-2/40 bg-chart-2/10 px-3 py-2 text-sm text-chart-2"}>
                  {feedback.text}
                </p>
              )}
            </div>
          </form>
        </Panel>

        <div className="space-y-4">
          <Panel title="Current state">
            <div data-testid="status-own-ai" role="status" aria-live="polite">
              {active ? (
                <dl>
                  <KV k="Source"><Tag tone="hot">your key</Tag></KV>
                  <KV k="Provider">{PROVIDERS[active.provider].label}</KV>
                  <KV k="Model"><span className="num text-xs">{active.model}</span></KV>
                  <KV k="Checked">only when an AI analysis runs</KV>
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">No key set. AI-assisted analyses use the built-in provider.</p>
              )}
            </div>
          </Panel>
          <Panel title="What to expect">
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>Requests made with your key are billed by {active ? PROVIDERS[active.provider].label : "that provider"}; they do not use Replit AI.</li>
              <li>The key is not tested here. A bad key or model surfaces as a plain error on the analysis, never the provider's raw response.</li>
              <li>A key does not make extraction succeed. Unknown facts stay unknown.</li>
              <li>Only fixed OpenAI and OpenRouter endpoints are supported.</li>
              <li>Refreshing, signing out or closing this tab clears the key.</li>
            </ul>
            <p className="mt-4 text-sm"><span className="font-editorial">Next:</span> open the workbench and tick AI-assisted extraction on a new analysis.</p>
          </Panel>
        </div>
      </div>
    </>
  );
}
