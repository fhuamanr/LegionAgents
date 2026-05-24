"use client";

import { useState, type FormEvent } from "react";
import { CheckCircle2, Cpu, KeyRound, PlugZap, RadioTower, Save, Server, TriangleAlert, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { LlmProviderHealthCheck, LlmProviderSummary } from "@/lib/types";

const agentLabels: Record<string, string> = {
  ba: "BA",
  architect: "Architect",
  developer: "Developer",
  qa: "QA",
  docs: "Docs",
  pr: "PR",
};

export function ProviderManagement({
  providers,
  checks,
}: Readonly<{
  providers: readonly LlmProviderSummary[];
  checks: readonly LlmProviderHealthCheck[];
}>): JSX.Element {
  const [providerItems, setProviderItems] = useState<readonly LlmProviderSummary[]>(providers);
  const [healthChecks, setHealthChecks] = useState<readonly LlmProviderHealthCheck[]>(checks);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [defaultModel, setDefaultModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [contextWindowTokens, setContextWindowTokens] = useState("4096");
  const [reservedOutputTokens, setReservedOutputTokens] = useState("1024");
  const [maxPromptTokens, setMaxPromptTokens] = useState("3000");
  const active = providerItems.filter((provider) => provider.status === "active");

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Metric icon={RadioTower} label="Active providers" value={active.length.toString()} />
        <Metric icon={Cpu} label="Configured models" value={providerItems.reduce((count, provider) => count + 1 + Object.keys(provider.agentModels).length, 0).toString()} />
        <Metric icon={KeyRound} label="Key status" value={providerItems.some((provider) => provider.configured) ? "Ready" : "Missing"} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add Provider</CardTitle>
          <CardDescription>Configure, validate connection, and save runtime providers.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-6" onSubmit={(event) => void saveProvider(event)}>
            <Field label="Name" placeholder="OpenAI Production" value={name} onChange={setName} required />
            <SelectField label="Kind" value={kind} onChange={setKind} options={["openai", "cursor", "openrouter", "ollama", "lm_studio", "local", "custom"]} />
            <Field label="Base URL" placeholder="https://api.openai.com/v1" value={baseUrl} onChange={setBaseUrl} />
            <Field label="Default model" placeholder="gpt-5-mini" value={defaultModel} onChange={setDefaultModel} required />
            <Field label="API key" placeholder="sk-..." value={apiKey} onChange={setApiKey} type="password" />
            <Field label="Context window" placeholder="4096" value={contextWindowTokens} onChange={setContextWindowTokens} />
            <Field label="Reserved output" placeholder="1024" value={reservedOutputTokens} onChange={setReservedOutputTokens} />
            <Field label="Max prompt tokens" placeholder="3000" value={maxPromptTokens} onChange={setMaxPromptTokens} />
            <label className="flex items-center gap-2 rounded-md border px-3 text-xs font-medium">
              <input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} />
              Set as default
            </label>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
              <Button type="button" variant="outline" disabled={testing || saving} onClick={() => void testConnection()}>
                <PlugZap className="h-4 w-4" aria-hidden="true" />
                {testing ? "Testing" : "Test"}
              </Button>
              <Button type="submit" disabled={saving || testing}>
                <Save className="h-4 w-4" aria-hidden="true" />
                {saving ? "Saving" : "Save"}
              </Button>
            </div>
          </form>
          {message ? <p className="mt-3 text-xs text-muted-foreground">{message}</p> : null}
          <p className="mt-2 text-xs text-muted-foreground">
            LM Studio in Docker: use <code>http://host.docker.internal:1234/v1</code> (not <code>http://127.0.0.1:1234/v1</code>). Small local models may require compact workflow mode.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <Card>
          <CardHeader>
            <CardTitle>Provider Registry</CardTitle>
          <CardDescription>Persisted providers used by workflow runtime routing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {providerItems.length === 0 ? (
              <div className="rounded-md border border-dashed p-5 text-sm text-muted-foreground">
                No provider is configured yet.
              </div>
            ) : (
              providerItems.map((provider) => (
                <div key={provider.id} className="rounded-md border p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Server className="h-4 w-4 text-primary" aria-hidden="true" />
                        <h3 className="text-sm font-semibold">{provider.name}</h3>
                        <Badge variant={provider.status === "active" ? "default" : "muted"}>{provider.status}</Badge>
                        {provider.isDefault ? <Badge variant="success">default</Badge> : null}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{provider.kind} / {provider.defaultModel}</p>
                    </div>
                    <Button variant="outline" size="sm" aria-label={`Use ${provider.name}`}>
                      {provider.configured ? "Ready" : "Needs key"}
                    </Button>
                  </div>
                  <dl className="mt-4 grid gap-3 text-xs md:grid-cols-3">
                    <Detail label="Endpoint" value={provider.baseUrl || "OpenAI default"} />
                    <Detail label="API key" value={provider.apiKey || "Not configured"} />
                    <Detail label="Updated" value={provider.updatedAt ? new Date(provider.updatedAt).toLocaleString() : "Unknown"} />
                    <Detail label="Context" value={provider.contextWindowTokens ? `${provider.contextWindowTokens} tokens` : "default"} />
                    <Detail label="Prompt budget" value={provider.maxPromptTokens ? `${provider.maxPromptTokens}` : "auto"} />
                  </dl>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {Object.entries(provider.agentModels).length === 0 ? (
                      <Badge variant="muted">Default model for all agents</Badge>
                    ) : (
                      Object.entries(provider.agentModels).map(([agent, model]) => (
                        <Badge key={agent} variant="muted">
                          {agentLabels[agent] ?? agent}: {model}
                        </Badge>
                      ))
                    )}
                  </div>
                  <div className="mt-4">
                    <Button variant="destructive" size="sm" onClick={() => void deleteProvider(provider.id)}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Health Checks</CardTitle>
            <CardDescription>Backend provider configuration validation.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {healthChecks.length === 0 ? (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">No health checks available.</div>
            ) : (
              healthChecks.map((check) => (
                <div key={check.providerId} className="flex gap-3 rounded-md border p-3">
                  {check.status === "ok" ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" aria-hidden="true" />
                  ) : (
                    <TriangleAlert className="mt-0.5 h-4 w-4 text-amber-600" aria-hidden="true" />
                  )}
                  <div>
                    <div className="text-sm font-medium capitalize">{check.status}</div>
                    <p className="text-xs text-muted-foreground">{check.message}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );

  async function refreshProviders(): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    const [providersResponse, healthResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/providers`, { headers: { Accept: "application/json" }, cache: "no-store" }),
      fetch(`${apiBaseUrl}/providers/health`, { headers: { Accept: "application/json" }, cache: "no-store" }),
    ]);
    const providersPayload = (await providersResponse.json()) as { providers: readonly Record<string, unknown>[] };
    const healthPayload = (await healthResponse.json()) as { checks: readonly Record<string, unknown>[] };
    setProviderItems(providersPayload.providers.map(normalizeProvider));
    setHealthChecks(healthPayload.checks.map(normalizeProviderHealth));
  }

  async function saveProvider(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      setMessage("NEXT_PUBLIC_API_BASE_URL is not configured.");
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const response = await fetch(`${apiBaseUrl}/providers`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({
            name,
            kind,
            base_url: baseUrl.trim() || null,
            api_key: apiKey.trim() || null,
            default_model: defaultModel,
            status: "active",
            is_default: isDefault,
            context_window_tokens: parseInt(contextWindowTokens || "0", 10) || null,
            reserved_output_tokens: parseInt(reservedOutputTokens || "0", 10) || null,
            max_prompt_tokens: parseInt(maxPromptTokens || "0", 10) || null,
          }),
      });
      if (!response.ok) throw new Error(await extractError(response));
      await refreshProviders();
      setMessage("Provider saved and persisted.");
      setApiKey("");
      setIsDefault(false);
    } catch (error) {
      setMessage(`Provider save failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setSaving(false);
    }
  }

  async function testConnection(): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    setTesting(true);
    setMessage(null);
    try {
      const response = await fetch(`${apiBaseUrl}/providers/test-connection`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          name,
          kind,
          base_url: baseUrl.trim() || null,
          api_key: apiKey.trim() || null,
          default_model: defaultModel,
          context_window_tokens: parseInt(contextWindowTokens || "0", 10) || null,
          reserved_output_tokens: parseInt(reservedOutputTokens || "0", 10) || null,
          max_prompt_tokens: parseInt(maxPromptTokens || "0", 10) || null,
        }),
      });
      if (!response.ok) throw new Error(await extractError(response));
      const payload = (await response.json()) as { result: { status: string; latency_ms?: number; message: string; capabilities?: Record<string, unknown> } };
      const latency = payload.result.latency_ms ? ` (${payload.result.latency_ms}ms)` : "";
      const capabilities = payload.result.capabilities
        ? ` | caps: ${Object.entries(payload.result.capabilities).filter(([, value]) => Boolean(value)).map(([key]) => key).join(", ")}`
        : "";
      setMessage(`Connection ${payload.result.status}${latency}: ${payload.result.message}${capabilities}`);
    } catch (error) {
      setMessage(`Connection test failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setTesting(false);
    }
  }

  async function deleteProvider(providerId: string): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    try {
      const response = await fetch(`${apiBaseUrl}/providers/${providerId}`, { method: "DELETE" });
      if (!response.ok) throw new Error(await extractError(response));
      await refreshProviders();
      setMessage("Provider deleted.");
    } catch (error) {
      setMessage(`Provider delete failed: ${error instanceof Error ? error.message : "unknown error"}`);
    }
  }
}

async function extractError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || `${response.status} ${response.statusText}`;
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

function normalizeProvider(item: Record<string, unknown>): LlmProviderSummary {
  return {
    id: String(item.id),
    name: String(item.name),
    kind: String(item.kind) as LlmProviderSummary["kind"],
    baseUrl: item.base_url ? String(item.base_url) : undefined,
    apiKey: item.api_key ? String(item.api_key) : undefined,
    defaultModel: String(item.default_model ?? ""),
    status: String(item.status) as LlmProviderSummary["status"],
    agentModels: (item.agent_models ?? {}) as Record<string, string>,
    contextWindowTokens: item.context_window_tokens ? Number(item.context_window_tokens) : undefined,
    maxOutputTokens: item.max_output_tokens ? Number(item.max_output_tokens) : undefined,
    reservedOutputTokens: item.reserved_output_tokens ? Number(item.reserved_output_tokens) : undefined,
    maxPromptTokens: item.max_prompt_tokens ? Number(item.max_prompt_tokens) : undefined,
    configured: Boolean(item.configured),
    isDefault: Boolean(item.is_default ?? false),
    updatedAt: String(item.updated_at ?? ""),
  };
}

function normalizeProviderHealth(item: Record<string, unknown>): LlmProviderHealthCheck {
  return {
    providerId: String(item.provider_id),
    status: String(item.status) as LlmProviderHealthCheck["status"],
    message: String(item.message),
    checkedAt: String(item.checked_at ?? ""),
  };
}

function Field({
  label,
  placeholder,
  value,
  onChange,
  type = "text",
  required = false,
}: Readonly<{
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}>): JSX.Element {
  return (
    <label className="space-y-1 text-xs font-medium">
      <span>{label}</span>
      <input
        type={type}
        required={required}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
    </label>
  );
}

function SelectField({ label, value, onChange, options }: Readonly<{ label: string; value: string; onChange: (value: string) => void; options: readonly string[] }>): JSX.Element {
  return (
    <label className="space-y-1 text-xs font-medium">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring">
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ icon: Icon, label, value }: Readonly<{ icon: LucideIcon; label: string; value: string }>): JSX.Element {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-secondary">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div>
          <div className="text-lg font-semibold">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function Detail({ label, value }: Readonly<{ label: string; value: string }>): JSX.Element {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-1 truncate font-medium" title={value}>{value}</dd>
    </div>
  );
}
