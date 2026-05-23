"use client";

import { useState, type FormEvent } from "react";
import { CheckCircle2, Cpu, KeyRound, RadioTower, Save, Server, TriangleAlert, type LucideIcon } from "lucide-react";
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
  const [message, setMessage] = useState<string | null>(null);
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
          <CardDescription>Configure the active runtime provider used by workflows and agent-specific model overrides.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-6" onSubmit={(event) => void saveProvider(event, setSaving, setMessage, setProviderItems, setHealthChecks)}>
            <Field name="name" label="Name" placeholder="OpenRouter" required />
            <SelectField name="kind" label="Kind" options={["openai", "cursor", "openrouter", "ollama", "lm_studio", "local", "custom"]} />
            <Field name="base_url" label="Base URL" placeholder="https://openrouter.ai/api/v1" />
            <Field name="default_model" label="Default model" placeholder="openai/gpt-4o-mini" required />
            <Field name="api_key" label="API key" placeholder="sk-..." type="password" />
            <div className="flex items-end">
              <Button type="submit" disabled={saving} className="w-full">
                <Save className="h-4 w-4" aria-hidden="true" />
                {saving ? "Saving" : "Save"}
              </Button>
            </div>
          </form>
          {message ? <p className="mt-3 text-xs text-muted-foreground">{message}</p> : null}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <Card>
          <CardHeader>
            <CardTitle>Provider Registry</CardTitle>
            <CardDescription>Runtime routing supports OpenAI-compatible cloud and local endpoints.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {providerItems.length === 0 ? (
              <div className="rounded-md border border-dashed p-5 text-sm text-muted-foreground">
                No provider is configured. Add one through the API or environment variables before running a real workflow.
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
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Health Checks</CardTitle>
            <CardDescription>Configuration validation before workflow execution.</CardDescription>
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
}

async function saveProvider(
  event: FormEvent<HTMLFormElement>,
  setSaving: (value: boolean) => void,
  setMessage: (value: string | null) => void,
  setProviderItems: (value: readonly LlmProviderSummary[]) => void,
  setHealthChecks: (value: readonly LlmProviderHealthCheck[]) => void,
): Promise<void> {
  event.preventDefault();
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!apiBaseUrl) {
    setMessage("NEXT_PUBLIC_API_BASE_URL is not configured.");
    return;
  }
  const form = new FormData(event.currentTarget);
  setSaving(true);
  setMessage(null);
  try {
    const response = await fetch(`${apiBaseUrl}/providers`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        name: form.get("name"),
        kind: form.get("kind"),
        base_url: emptyToNull(form.get("base_url")),
        api_key: emptyToNull(form.get("api_key")),
        default_model: form.get("default_model"),
        status: "active",
      }),
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const [providersResponse, healthResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/providers`, { headers: { Accept: "application/json" } }),
      fetch(`${apiBaseUrl}/providers/health`, { headers: { Accept: "application/json" } }),
    ]);
    const providersPayload = (await providersResponse.json()) as { providers: readonly Record<string, unknown>[] };
    const healthPayload = (await healthResponse.json()) as { checks: readonly Record<string, unknown>[] };
    setProviderItems(providersPayload.providers.map(normalizeProvider));
    setHealthChecks(healthPayload.checks.map(normalizeProviderHealth));
    event.currentTarget.reset();
    setMessage("Provider saved and ready for runtime routing.");
  } catch (error) {
    setMessage(`Provider save failed: ${error instanceof Error ? error.message : "unknown error"}`);
  } finally {
    setSaving(false);
  }
}

function emptyToNull(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text ? text : null;
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
    configured: Boolean(item.configured),
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
  name,
  label,
  placeholder,
  type = "text",
  required = false,
}: Readonly<{
  name: string;
  label: string;
  placeholder: string;
  type?: string;
  required?: boolean;
}>): JSX.Element {
  return (
    <label className="space-y-1 text-xs font-medium">
      <span>{label}</span>
      <input
        name={name}
        type={type}
        required={required}
        placeholder={placeholder}
        className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
    </label>
  );
}

function SelectField({ name, label, options }: Readonly<{ name: string; label: string; options: readonly string[] }>): JSX.Element {
  return (
    <label className="space-y-1 text-xs font-medium">
      <span>{label}</span>
      <select name={name} className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring">
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
