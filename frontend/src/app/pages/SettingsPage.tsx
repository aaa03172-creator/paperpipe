import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowLeft, ClipboardPaste, KeyRound, RadioTower, RefreshCw, Save, ShieldCheck, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { getApiErrorMessage, getRuntimeLLMSettings, testRuntimeLLMConnection, updateRuntimeLLMSettings } from "../lib/api";
import {
  RuntimeLLMConnectionTestResponse,
  RuntimeLLMMode,
  RuntimeLLMProvider,
  RuntimeLLMSettingsResponse,
  RuntimeLLMSettingsUpdateRequest,
} from "../lib/types";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

const DEFAULT_MODELS: Record<RuntimeLLMProvider, string> = {
  openai: "gpt-4o-mini",
  anthropic: "claude-3-5-sonnet-latest",
  gemini: "gemini-2.5-flash",
};
const KNOWN_PROVIDER_DEFAULT_MODELS = new Set([...Object.values(DEFAULT_MODELS), "gpt-4o", "gpt-5.4-mini"]);

function sourceLabel(settings: RuntimeLLMSettingsResponse | null): string {
  if (!settings || !settings.api_key_configured) {
    return "Not configured";
  }
  if (settings.api_key_source === "env") {
    return `${settings.provider_env_var} (${settings.api_key_masked ?? "configured"})`;
  }
  return `Saved locally (${settings.api_key_masked ?? "configured"})`;
}

export function SettingsPage() {
  const [settings, setSettings] = useState<RuntimeLLMSettingsResponse | null>(null);
  const [mode, setMode] = useState<RuntimeLLMMode>("local");
  const [provider, setProvider] = useState<RuntimeLLMProvider>("openai");
  const [model, setModel] = useState(DEFAULT_MODELS.openai);
  const [embeddingModel, setEmbeddingModel] = useState("text-embedding-3-small");
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<RuntimeLLMConnectionTestResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const apiKeyInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    document.title = "Settings | Lattice";
  }, []);

  function applySettings(next: RuntimeLLMSettingsResponse) {
    setSettings(next);
    setMode(next.mode);
    setProvider(next.provider);
    setModel(next.model || DEFAULT_MODELS[next.provider]);
    setEmbeddingModel(next.embedding_model ?? "");
    setApiKey("");
  }

  async function loadSettings() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await getRuntimeLLMSettings();
      applySettings(result.data);
    } catch (loadError) {
      setError(getApiErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSettings();
  }, []);

  function handleProviderChange(nextProvider: RuntimeLLMProvider) {
    const previousProvider = provider;
    setProvider(nextProvider);
    setTestResult(null);
    setModel((current) => {
      const currentModel = current.trim();
      if (
        !currentModel ||
        currentModel === DEFAULT_MODELS[previousProvider] ||
        KNOWN_PROVIDER_DEFAULT_MODELS.has(currentModel)
      ) {
        return DEFAULT_MODELS[nextProvider];
      }
      return current;
    });
  }

  async function submitSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    const payload: RuntimeLLMSettingsUpdateRequest = {
      mode,
      provider,
      model: model.trim() || DEFAULT_MODELS[provider],
      embedding_model: embeddingModel.trim() || null,
    };
    if (apiKey.trim()) {
      payload.api_key = apiKey;
    }
    try {
      const result = await updateRuntimeLLMSettings(payload);
      applySettings(result.data);
      setTestResult(null);
      setMessage("LLM settings saved.");
    } catch (saveError) {
      setError(getApiErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function clearSavedKey() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateRuntimeLLMSettings({ clear_api_key: true });
      applySettings(result.data);
      setTestResult(null);
      setMessage("Saved API key removed.");
    } catch (clearError) {
      setError(getApiErrorMessage(clearError));
    } finally {
      setSaving(false);
    }
  }

  async function pasteApiKeyFromClipboard() {
    setError(null);
    setMessage(null);
    if (typeof navigator === "undefined" || !navigator.clipboard?.readText) {
      setError("Clipboard paste is not available in this app window. Use Command+V inside the API key field.");
      apiKeyInputRef.current?.focus();
      return;
    }
    try {
      const clipboardText = await navigator.clipboard.readText();
      if (!clipboardText.trim()) {
        setError("Clipboard is empty.");
        apiKeyInputRef.current?.focus();
        return;
      }
      setApiKey(clipboardText.trim());
      apiKeyInputRef.current?.focus();
      setMessage("API key pasted. Save settings when ready.");
    } catch (pasteError) {
      setError(getApiErrorMessage(pasteError));
      apiKeyInputRef.current?.focus();
    }
  }

  async function runConnectionTest() {
    setTesting(true);
    setError(null);
    setMessage(null);
    setTestResult(null);
    try {
      const result = await testRuntimeLLMConnection();
      setTestResult(result.data);
      setMessage(result.data.status === "ok" ? "Live provider test completed." : "Live provider test failed.");
    } catch (testError) {
      setError(getApiErrorMessage(testError));
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
              <KeyRound className="h-3.5 w-3.5" />
              Settings
            </p>
            <h1 className="mt-1 text-lg font-semibold text-[var(--pp-text-primary)]">LLM provider</h1>
            <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">
              Connect the model account this machine should use for cloud or hybrid inference.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => void loadSettings()} disabled={loading || saving}>
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Reload
            </Button>
            <Link
              to="/"
              className="inline-flex items-center rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-secondary)]"
            >
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              Back
            </Link>
          </div>
        </div>
      </header>

      <main className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <form onSubmit={submitSettings} className="surface-card p-4">
          <div className="grid gap-4">
            <label className="grid gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Runtime mode</span>
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value as RuntimeLLMMode)}
                className="h-10 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-sm text-[var(--pp-text-primary)] outline-none focus:border-[var(--pp-accent-border)]"
              >
                <option value="local">Local</option>
                <option value="hybrid">Hybrid</option>
                <option value="cloud">Cloud</option>
              </select>
            </label>

            <label className="grid gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Provider</span>
              <select
                value={provider}
                onChange={(event) => handleProviderChange(event.target.value as RuntimeLLMProvider)}
                className="h-10 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 text-sm text-[var(--pp-text-primary)] outline-none focus:border-[var(--pp-accent-border)]"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Google Gemini</option>
              </select>
            </label>

            <label className="grid gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Model</span>
              <Input value={model} onChange={(event) => setModel(event.target.value)} placeholder={DEFAULT_MODELS[provider]} />
            </label>

            <label className="grid gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Embedding model</span>
              <Input
                value={embeddingModel}
                onChange={(event) => setEmbeddingModel(event.target.value)}
                placeholder="text-embedding-3-small"
              />
            </label>

            <label className="grid gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">API key</span>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  ref={apiKeyInputRef}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={settings?.api_key_configured ? "Leave blank to keep current key" : "Paste provider API key"}
                  type="password"
                  autoComplete="off"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void pasteApiKeyFromClipboard()}
                  disabled={saving || loading}
                  className="shrink-0"
                >
                  <ClipboardPaste className="mr-1.5 h-3.5 w-3.5" />
                  Paste key
                </Button>
              </div>
            </label>

            {message ? (
              <p className="rounded-md border border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] px-3 py-2 text-sm text-[var(--pp-status-completed-text)]">
                {message}
              </p>
            ) : null}
            {error ? (
              <p className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] px-3 py-2 text-sm text-[var(--pp-status-failed-text)]">
                {error}
              </p>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={saving || loading}>
                <Save className="mr-1.5 h-3.5 w-3.5" />
                Save settings
              </Button>
              <Button type="button" variant="secondary" onClick={() => void clearSavedKey()} disabled={saving || loading}>
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                Remove saved key
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => void runConnectionTest()}
                disabled={saving || loading || testing || !settings?.api_key_configured}
              >
                <RadioTower className={`mr-1.5 h-3.5 w-3.5 ${testing ? "animate-pulse" : ""}`} />
                {testing ? "Testing..." : "Test live call"}
              </Button>
            </div>
          </div>
        </form>

        <aside className="surface-card p-4">
          <div className="flex items-start gap-2">
            <ShieldCheck className="mt-0.5 h-4 w-4 text-[var(--pp-accent-text)]" />
            <div>
              <h2 className="text-sm font-semibold text-[var(--pp-text-primary)]">Credential status</h2>
              <p className="mt-2 text-sm text-[var(--pp-text-secondary)]">{sourceLabel(settings)}</p>
            </div>
          </div>

          <dl className="mt-4 space-y-3 border-t border-[var(--pp-border)] pt-4 text-sm">
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">Config path</dt>
              <dd className="mt-1 break-all font-mono text-xs text-[var(--pp-text-secondary)]">
                {settings?.config_path ?? "Loading..."}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">Environment override</dt>
              <dd className="mt-1 text-[var(--pp-text-secondary)]">
                {settings?.env_override_active ? `${settings.provider_env_var} is active` : "None"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--pp-text-dim)]">Live test</dt>
              <dd className="mt-1 text-[var(--pp-text-secondary)]">
                {testResult
                  ? `${testResult.status.toUpperCase()} · ${testResult.model}${
                      testResult.latency_ms !== null && testResult.latency_ms !== undefined
                        ? ` · ${testResult.latency_ms} ms`
                        : ""
                    }`
                  : "Not run"}
              </dd>
              {testResult ? <dd className="mt-1 text-xs text-[var(--pp-text-dim)]">{testResult.detail}</dd> : null}
            </div>
          </dl>
        </aside>
      </main>
    </div>
  );
}
