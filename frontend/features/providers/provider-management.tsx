"use client";

import { useState, type FormEvent } from "react";
import { CheckCircle2, Cpu, KeyRound, PlugZap, RadioTower, Save, Search, Server, TriangleAlert, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { LlmModelCapabilityProfile, LlmProviderHealthCheck, LlmProviderSummary } from "@/lib/types";

const AGENTS = ["chat", "ba", "architect", "developer", "qa", "docs", "pr"] as const;
type AgentName = typeof AGENTS[number];

const agentLabels: Record<string, string> = {
  chat: "Chat",
  ba: "BA",
  architect: "Architect",
  developer: "Developer",
  qa: "QA",
  docs: "Docs",
  pr: "PR",
};

type AgentOverride = {
  use_default: boolean;
  provider_id?: string;
  model?: string;
  context_window_tokens?: number;
  max_output_tokens?: number;
  compact_mode_enabled?: boolean;
  streaming_enabled?: boolean;
  parser_strategy?: string;
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
  const [selectedModelsByProvider, setSelectedModelsByProvider] = useState<Record<string, string>>({});
  const [searchByProvider, setSearchByProvider] = useState<Record<string, string>>({});
  const [loadedFilterByProvider, setLoadedFilterByProvider] = useState<Record<string, "all" | "loaded" | "unloaded">>({});
  const [runtimeContextByProvider, setRuntimeContextByProvider] = useState<Record<string, string>>({});
  const [runtimeParallelByProvider, setRuntimeParallelByProvider] = useState<Record<string, string>>({});
  const [flashAttentionByProvider, setFlashAttentionByProvider] = useState<Record<string, boolean>>({});
  const [runtimeBusyByProvider, setRuntimeBusyByProvider] = useState<Record<string, boolean>>({});
  const [tokenByProvider, setTokenByProvider] = useState<Record<string, string>>({});
  const [authModeByProvider, setAuthModeByProvider] = useState<Record<string, "raw" | "bearer">>({});
  const [agentOverridesByProvider, setAgentOverridesByProvider] = useState<Record<string, Record<string, AgentOverride>>>({});
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
            <SelectField label="Kind" value={kind} onChange={setKind} options={["openai", "cursor", "openrouter", "ollama", "lm_studio", "local_lm_studio", "local", "custom"]} />
            <Field label="Base URL" placeholder="https://api.openai.com/v1" value={baseUrl} onChange={setBaseUrl} />
            <Field label="Default model" placeholder="gpt-5-mini" value={defaultModel} onChange={setDefaultModel} required />
            <Field label="API key / local token" placeholder="sk-..." value={apiKey} onChange={setApiKey} type="password" />
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
            Cloud Provider Mode: API consumption, model selection, no runtime lifecycle control.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Local/Controlled Runtime Mode: model lifecycle management, runtime context tuning, and compact workflow safety controls.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            LM Studio/Ollama local providers may require API token authentication. Save the local token in the provider to enable model list/load/unload.
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
                    <Button variant="outline" size="sm">
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

                  {renderDefaultAssignment(provider)}
                  {renderTokenEditor(provider)}
                  {renderAdvancedOverrides(provider)}

                  <div className="mt-4 flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => void refreshModels(provider.id)}>
                      List models
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void saveAgentAssignments(provider)}>
                      Save assignments
                    </Button>
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

  function renderDefaultAssignment(provider: LlmProviderSummary): JSX.Element {
    const selectedModel = selectedModelsByProvider[provider.id] ?? provider.defaultModel;
    const profiles = Object.values(provider.modelProfiles ?? {});
    const search = (searchByProvider[provider.id] ?? "").toLowerCase();
    const loadedFilter = loadedFilterByProvider[provider.id] ?? "all";
    const filteredProfiles = profiles.filter((profile) => {
      const matchSearch = !search || profile.modelId.toLowerCase().includes(search) || (profile.displayName ?? "").toLowerCase().includes(search);
      const status = (profile.runtimeStatus ?? "").toLowerCase();
      const matchLoaded = loadedFilter === "all" || (loadedFilter === "loaded" ? status === "loaded" : status !== "loaded");
      return matchSearch && matchLoaded;
    });
    return (
      <div className="mt-4 rounded-md border bg-muted/30 p-3">
        <div className="mb-2 text-xs font-semibold">Global Default Assignment</div>
        <div className="grid gap-2 md:grid-cols-4">
          <Field label="Model id" placeholder="model-id" value={selectedModel} onChange={(value) => setSelectedModelsByProvider((current) => ({ ...current, [provider.id]: value }))} />
          <Field label="Context" placeholder="8192" value={runtimeContextByProvider[provider.id] ?? String(provider.contextWindowTokens ?? 8192)} onChange={(value) => setRuntimeContextByProvider((current) => ({ ...current, [provider.id]: value }))} />
          <Field label="Parallel slots" placeholder="1" value={runtimeParallelByProvider[provider.id] ?? "1"} onChange={(value) => setRuntimeParallelByProvider((current) => ({ ...current, [provider.id]: value }))} />
          <div className="flex items-end gap-2">
            {isLocalProvider(provider.kind) ? (
              <>
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={flashAttentionByProvider[provider.id] ?? true}
                    onChange={(event) => setFlashAttentionByProvider((current) => ({ ...current, [provider.id]: event.target.checked }))}
                  />
                  Flash attention
                </label>
                <Button variant="outline" size="sm" disabled={Boolean(runtimeBusyByProvider[provider.id])} onClick={() => void loadRuntimeModel(provider.id)}>
                  {runtimeBusyByProvider[provider.id] ? "Loading..." : "Load model"}
                </Button>
                <Button variant="outline" size="sm" disabled={Boolean(runtimeBusyByProvider[provider.id])} onClick={() => void unloadRuntimeModel(provider.id)}>
                  {runtimeBusyByProvider[provider.id] ? "Working..." : "Unload"}
                </Button>
              </>
            ) : (
              <div className="text-xs text-muted-foreground">Cloud/API mode</div>
            )}
          </div>
        </div>
        <div className="mt-3 rounded border bg-background">
          <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b bg-background p-2">
            <label className="relative flex-1 text-xs">
              <Search className="pointer-events-none absolute left-2 top-2.5 h-3 w-3 text-muted-foreground" />
              <input
                value={searchByProvider[provider.id] ?? ""}
                onChange={(event) => setSearchByProvider((current) => ({ ...current, [provider.id]: event.target.value }))}
                placeholder="Search models..."
                className="h-8 w-full rounded-md border bg-background pl-7 pr-2 text-xs"
              />
            </label>
            <select
              value={loadedFilter}
              onChange={(event) => setLoadedFilterByProvider((current) => ({ ...current, [provider.id]: event.target.value as "all" | "loaded" | "unloaded" }))}
              className="h-8 rounded-md border bg-background px-2 text-xs"
            >
              <option value="all">All</option>
              <option value="loaded">Loaded</option>
              <option value="unloaded">Unloaded</option>
            </select>
          </div>
          <div className="max-h-[22rem] overflow-y-auto p-2">
            {filteredProfiles.length === 0 ? (
              <div className="p-3 text-xs text-muted-foreground">No models match current filters.</div>
            ) : (
              <div className="grid gap-2">
                {filteredProfiles.map((profile) => {
                  const selected = selectedModel === profile.modelId;
                  const loaded = profile.runtimeStatus === "loaded";
                  return (
                    <button
                      key={`${provider.id}-${profile.modelId}`}
                      type="button"
                      onClick={() => selectModel(provider, profile)}
                      className={`rounded border p-2 text-left text-xs transition ${selected ? "border-primary bg-primary/5" : "hover:bg-muted/60"}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium">{profile.displayName ?? profile.modelId}</div>
                        <Badge variant={loaded ? "success" : "muted"}>{loaded ? "loaded" : "unloaded"}</Badge>
                      </div>
                      <div className="mt-1 text-muted-foreground">
                        ctx {profile.contextWindowTokens} | out {profile.maxOutputTokens} | {profile.providerType}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        <Badge variant="muted">{profile.compactModeRequired ? "compact" : profile.contextWindowTokens >= 32000 ? "heavy workflow" : "balanced"}</Badge>
                        {profile.recommendedForCode ? <Badge variant="muted">coding</Badge> : null}
                        {profile.recommendedForChat ? <Badge variant="muted">chat</Badge> : null}
                        {profile.supportsEmbeddings ? <Badge variant="muted">embedding</Badge> : null}
                        {profile.notes?.toLowerCase().includes("q4") ? <Badge variant="muted">quantized</Badge> : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  function renderAdvancedOverrides(provider: LlmProviderSummary): JSX.Element {
    const overrides = resolveOverrides(provider);
    return (
      <details className="mt-3 rounded-md border bg-background p-3">
        <summary className="cursor-pointer text-xs font-semibold">Advanced Per-Agent Overrides</summary>
        <div className="mt-3 space-y-2">
          {AGENTS.map((agent) => {
            const override = overrides[agent] ?? { use_default: true };
            return (
              <div key={`${provider.id}-${agent}`} className="grid gap-2 rounded border p-2 md:grid-cols-8">
                <div className="text-xs font-medium">{agentLabels[agent]}</div>
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={override.use_default}
                    onChange={(event) =>
                      setAgentOverridesByProvider((current) => ({
                        ...current,
                        [provider.id]: {
                          ...overrides,
                          [agent]: { ...override, use_default: event.target.checked },
                        },
                      }))
                    }
                  />
                  Use default
                </label>
                <input
                  disabled={override.use_default}
                  value={override.model ?? ""}
                  onChange={(event) =>
                    setAgentOverridesByProvider((current) => ({
                      ...current,
                      [provider.id]: {
                        ...overrides,
                        [agent]: { ...override, model: event.target.value },
                      },
                    }))
                  }
                  placeholder="model"
                  className="h-8 rounded border px-2 text-xs disabled:opacity-50"
                />
                <input
                  disabled={override.use_default}
                  value={String(override.context_window_tokens ?? "")}
                  onChange={(event) =>
                    setAgentOverridesByProvider((current) => ({
                      ...current,
                      [provider.id]: {
                        ...overrides,
                        [agent]: { ...override, context_window_tokens: parseInt(event.target.value || "0", 10) || undefined },
                      },
                    }))
                  }
                  placeholder="ctx"
                  className="h-8 rounded border px-2 text-xs disabled:opacity-50"
                />
                <input
                  disabled={override.use_default}
                  value={String(override.max_output_tokens ?? "")}
                  onChange={(event) =>
                    setAgentOverridesByProvider((current) => ({
                      ...current,
                      [provider.id]: {
                        ...overrides,
                        [agent]: { ...override, max_output_tokens: parseInt(event.target.value || "0", 10) || undefined },
                      },
                    }))
                  }
                  placeholder="max out"
                  className="h-8 rounded border px-2 text-xs disabled:opacity-50"
                />
                <select
                  disabled={override.use_default}
                  value={override.parser_strategy ?? "json"}
                  onChange={(event) =>
                    setAgentOverridesByProvider((current) => ({
                      ...current,
                      [provider.id]: {
                        ...overrides,
                        [agent]: { ...override, parser_strategy: event.target.value },
                      },
                    }))
                  }
                  className="h-8 rounded border px-2 text-xs disabled:opacity-50"
                >
                  <option value="json">json</option>
                  <option value="markdown_sections">markdown_sections</option>
                  <option value="yaml">yaml</option>
                  <option value="relaxed_json">relaxed_json</option>
                </select>
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    disabled={override.use_default}
                    checked={Boolean(override.compact_mode_enabled)}
                    onChange={(event) =>
                      setAgentOverridesByProvider((current) => ({
                        ...current,
                        [provider.id]: {
                          ...overrides,
                          [agent]: { ...override, compact_mode_enabled: event.target.checked },
                        },
                      }))
                    }
                  />
                  Compact
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    disabled={override.use_default}
                    checked={Boolean(override.streaming_enabled)}
                    onChange={(event) =>
                      setAgentOverridesByProvider((current) => ({
                        ...current,
                        [provider.id]: {
                          ...overrides,
                          [agent]: { ...override, streaming_enabled: event.target.checked },
                        },
                      }))
                    }
                  />
                  Stream
                </label>
              </div>
            );
          })}
        </div>
      </details>
    );
  }

  function renderTokenEditor(provider: LlmProviderSummary): JSX.Element | null {
    if (!isLocalProvider(provider.kind)) return null;
    const value = tokenByProvider[provider.id] ?? "";
    const authMode = authModeByProvider[provider.id] ?? String(provider.metadata?.lm_studio_auth_mode ?? "raw");
    return (
      <div className="mt-3 rounded-md border bg-muted/30 p-3">
        <div className="mb-2 text-xs font-semibold">Local Runtime Token</div>
        <div className="grid gap-2 md:grid-cols-[1fr_11rem_auto]">
          <input
            type="password"
            value={value}
            onChange={(event) => setTokenByProvider((current) => ({ ...current, [provider.id]: event.target.value }))}
            placeholder="Paste LM Studio/Ollama API token"
            className="h-9 rounded-md border bg-background px-3 text-sm"
          />
          <select
            value={authMode}
            onChange={(event) => setAuthModeByProvider((current) => ({ ...current, [provider.id]: event.target.value as "raw" | "bearer" }))}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            <option value="raw">Auth mode: raw</option>
            <option value="bearer">Auth mode: bearer</option>
          </select>
          <Button variant="outline" size="sm" onClick={() => void saveProviderToken(provider.id)}>
            Save token
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Authorization header mode controls whether token is sent as raw value or Bearer token.
        </p>
      </div>
    );
  }

  function resolveOverrides(provider: LlmProviderSummary): Record<string, AgentOverride> {
    const local = agentOverridesByProvider[provider.id];
    if (local) return local;
    const fromMetadata = provider.metadata?.agent_runtime_overrides;
    if (fromMetadata && typeof fromMetadata === "object") return fromMetadata as Record<string, AgentOverride>;
    return {};
  }

  function selectModel(provider: LlmProviderSummary, profile: LlmModelCapabilityProfile): void {
    setSelectedModelsByProvider((current) => ({ ...current, [provider.id]: profile.modelId }));
    setRuntimeContextByProvider((current) => ({ ...current, [provider.id]: String(profile.contextWindowTokens) }));
    setRuntimeParallelByProvider((current) => ({ ...current, [provider.id]: profile.compactModeRequired ? "1" : current[provider.id] ?? "2" }));
  }

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
    if (!apiBaseUrl) return;
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
          default_model: defaultModel || (isLocalProvider(kind) ? "local-model" : "default"),
          status: "active",
          is_default: isDefault,
          context_window_tokens: parseInt(contextWindowTokens || "0", 10) || null,
          reserved_output_tokens: parseInt(reservedOutputTokens || "0", 10) || null,
          max_prompt_tokens: parseInt(maxPromptTokens || "0", 10) || null,
        }),
      });
      if (!response.ok) throw new Error(await extractError(response));
      await refreshProviders();
      setMessage("Provider saved.");
    } catch (error) {
      setMessage(`Provider save failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setSaving(false);
    }
  }

  async function saveAgentAssignments(provider: LlmProviderSummary): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    try {
      const selectedModel = selectedModelsByProvider[provider.id] ?? provider.defaultModel;
      const contextWindow = parseInt(runtimeContextByProvider[provider.id] ?? String(provider.contextWindowTokens ?? 8192), 10) || 8192;
      const parallelSlots = parseInt(runtimeParallelByProvider[provider.id] ?? "1", 10) || 1;
      const overrides = resolveOverrides(provider);
      const response = await fetch(`${apiBaseUrl}/providers/${provider.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          name: provider.name,
          kind: provider.kind,
          base_url: provider.baseUrl ?? null,
          api_key: null,
          default_model: selectedModel,
          status: provider.status,
          context_window_tokens: contextWindow,
          max_output_tokens: provider.maxOutputTokens ?? 1024,
          reserved_output_tokens: provider.reservedOutputTokens ?? 1024,
          max_prompt_tokens: provider.maxPromptTokens ?? null,
          agent_models: {
            ...provider.agentModels,
            ...Object.fromEntries(
              Object.entries(overrides)
                .filter(([, value]) => value && value.use_default === false && value.model)
                .map(([agent, value]) => [agent, value.model as string]),
            ),
          },
          metadata: {
            ...(provider.metadata ?? {}),
            selected_model_id: selectedModel,
            selected_context: contextWindow,
            parallel_slots: parallelSlots,
            compact_mode_enabled: contextWindow <= 8192,
            lm_studio_auth_mode: authModeByProvider[provider.id] ?? String(provider.metadata?.lm_studio_auth_mode ?? "raw"),
            agent_runtime_overrides: overrides,
          },
          is_default: provider.isDefault ?? false,
        }),
      });
      if (!response.ok) throw new Error(await extractError(response));
      await refreshProviders();
      setMessage("Assignments saved and persisted.");
    } catch (error) {
      setMessage(`Assignment save failed: ${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  async function saveProviderToken(providerId: string): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    const provider = providerItems.find((item) => item.id === providerId);
    const token = tokenByProvider[providerId]?.trim();
    if (!provider || !token) {
      setMessage("Token is required.");
      return;
    }
    try {
      const response = await fetch(`${apiBaseUrl}/providers/${providerId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          name: provider.name,
          kind: provider.kind,
          base_url: provider.baseUrl ?? null,
          api_key: token,
          default_model: provider.defaultModel,
          status: provider.status,
          agent_models: provider.agentModels,
          context_window_tokens: provider.contextWindowTokens ?? 8192,
          max_output_tokens: provider.maxOutputTokens ?? 1024,
          reserved_output_tokens: provider.reservedOutputTokens ?? 1024,
          max_prompt_tokens: provider.maxPromptTokens ?? null,
          metadata: {
            ...(provider.metadata ?? {}),
            lm_studio_auth_mode: authModeByProvider[provider.id] ?? String(provider.metadata?.lm_studio_auth_mode ?? "raw"),
          },
          is_default: provider.isDefault ?? false,
        }),
      });
      if (!response.ok) throw new Error(await extractError(response));
      setTokenByProvider((current) => ({ ...current, [providerId]: "" }));
      await refreshProviders();
      setMessage("Local runtime token saved.");
    } catch (error) {
      setMessage(`Token save failed: ${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  async function loadRuntimeModel(providerId: string): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    const modelId = selectedModelsByProvider[providerId];
    if (!modelId) return;
    const contextLength = parseInt(runtimeContextByProvider[providerId] ?? "0", 10) || null;
    const parallel = parseInt(runtimeParallelByProvider[providerId] ?? "1", 10) || 1;
    setRuntimeBusyByProvider((current) => ({ ...current, [providerId]: true }));
    try {
      const response = await fetch(`${apiBaseUrl}/providers/${providerId}/runtime-models/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          model_id: modelId,
          context_length: contextLength,
          parallel_slots: parallel,
          flash_attention: flashAttentionByProvider[providerId] ?? true,
          echo_load_config: true,
        }),
      });
      if (!response.ok) {
        const error = await extractError(response);
        setMessage(error.includes("lm_studio_token_missing") ? "LM Studio API token is required for model listing/loading/unloading." : error.includes("lm_studio_token_rejected") || error.includes("401") ? "Unauthorized. Check LM Studio token and Authorization mode." : `Load failed: ${error}`);
        return;
      }
      await refreshProviders();
      setMessage(`Loaded ${modelId}.`);
    } finally {
      setRuntimeBusyByProvider((current) => ({ ...current, [providerId]: false }));
    }
  }

  async function unloadRuntimeModel(providerId: string): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    const modelId = selectedModelsByProvider[providerId];
    if (!modelId) return;
    setRuntimeBusyByProvider((current) => ({ ...current, [providerId]: true }));
    try {
      const response = await fetch(`${apiBaseUrl}/providers/${providerId}/runtime-models/unload`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
      if (!response.ok) {
        const error = await extractError(response);
        setMessage(error.includes("lm_studio_token_missing") ? "LM Studio API token is required for model listing/loading/unloading." : error.includes("lm_studio_token_rejected") || error.includes("401") ? "Unauthorized. Check LM Studio token and Authorization mode." : `Unload failed: ${error}`);
        return;
      }
      await refreshProviders();
      setMessage(`Unloaded ${modelId}.`);
    } finally {
      setRuntimeBusyByProvider((current) => ({ ...current, [providerId]: false }));
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
          default_model: defaultModel || (isLocalProvider(kind) ? "local-model" : "default"),
          context_window_tokens: parseInt(contextWindowTokens || "0", 10) || null,
          reserved_output_tokens: parseInt(reservedOutputTokens || "0", 10) || null,
          max_prompt_tokens: parseInt(maxPromptTokens || "0", 10) || null,
          management_base_url: isLocalProvider(kind) ? stripLmStudioSuffix(baseUrl.trim() || "") : null,
          inference_base_url: isLocalProvider(kind) ? `${stripLmStudioSuffix(baseUrl.trim() || "")}/v1` : null,
          lm_studio_auth_mode: isLocalProvider(kind) ? "raw" : null,
        }),
      });
      if (!response.ok) throw new Error(await extractError(response));
      const payload = (await response.json()) as { result: { status: string; message: string } };
      setMessage(`Connection ${payload.result.status}: ${payload.result.message}`);
    } catch (error) {
      setMessage(`Connection test failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setTesting(false);
    }
  }

  async function deleteProvider(providerId: string): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    const response = await fetch(`${apiBaseUrl}/providers/${providerId}`, { method: "DELETE" });
    if (!response.ok) return;
    await refreshProviders();
  }

  async function refreshModels(providerId: string): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    const response = await fetch(`${apiBaseUrl}/providers/${providerId}/models/refresh`, { method: "POST", headers: { Accept: "application/json" } });
    if (!response.ok) {
      setMessage(`Model refresh failed: ${await extractError(response)}`);
      return;
    }
    await refreshProviders();
    setMessage("Model list updated.");
  }
}

function isLocalProvider(kind: string): boolean {
  return ["lm_studio", "local_lm_studio", "ollama", "local"].includes(kind);
}

async function extractError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown; message?: unknown; error?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => {
          if (!item || typeof item !== "object") return String(item);
          const row = item as Record<string, unknown>;
          const loc = Array.isArray(row.loc) ? row.loc.join(".") : "field";
          const msg = typeof row.msg === "string" ? row.msg : JSON.stringify(row);
          return `${loc}: ${msg}`;
        })
        .join("; ");
    }
    if (payload.detail && typeof payload.detail === "object") return JSON.stringify(payload.detail);
    if (typeof payload.message === "string") return payload.message;
    if (payload.message && typeof payload.message === "object") return JSON.stringify(payload.message);
    if (typeof payload.error === "string") return payload.error;
    if (payload.error && typeof payload.error === "object") return JSON.stringify(payload.error);
    return `${response.status} ${response.statusText}`;
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

function stripLmStudioSuffix(value: string): string {
  const raw = value.trim().replace(/\/+$/, "");
  if (!raw) return raw;
  if (raw.endsWith("/api/v1")) return raw.slice(0, -"/api/v1".length);
  if (raw.endsWith("/v1")) return raw.slice(0, -"/v1".length);
  return raw;
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
    metadata: (item.metadata ?? {}) as Record<string, unknown>,
    modelProfiles: normalizeModelProfiles(item.model_profiles),
  };
}

function normalizeModelProfiles(value: unknown): Record<string, import("@/lib/types").LlmModelCapabilityProfile> | undefined {
  if (!value || typeof value !== "object") return undefined;
  const records = value as Record<string, Record<string, unknown>>;
  return Object.fromEntries(
    Object.entries(records).map(([key, item]) => [
      key,
      {
        providerId: item.provider_id ? String(item.provider_id) : undefined,
        providerType: String(item.provider_type ?? ""),
        modelId: String(item.model_id ?? key),
        displayName: item.display_name ? String(item.display_name) : undefined,
        contextWindowTokens: Number(item.context_window_tokens ?? 4096),
        maxInputTokens: Number(item.max_input_tokens ?? 2500),
        maxOutputTokens: Number(item.max_output_tokens ?? 1024),
        supportsStreaming: Boolean(item.supports_streaming ?? true),
        supportsJsonMode: Boolean(item.supports_json_mode ?? false),
        supportsTools: Boolean(item.supports_tools ?? false),
        supportsEmbeddings: Boolean(item.supports_embeddings ?? false),
        recommendedForChat: Boolean(item.recommended_for_chat ?? true),
        recommendedForAgents: Boolean(item.recommended_for_agents ?? true),
        recommendedForCode: Boolean(item.recommended_for_code ?? false),
        compactModeRequired: Boolean(item.compact_mode_required ?? true),
        notes: item.notes ? String(item.notes) : undefined,
        detectionSource: String(item.detection_source ?? "estimated"),
        loadedModelId: item.loaded_model_id ? String(item.loaded_model_id) : undefined,
        localRuntimeManagedByPlatform: Boolean(item.local_runtime_managed_by_platform ?? false),
        runtimeStatus: item.runtime_status ? String(item.runtime_status) : undefined,
        lastLoadedAt: item.last_loaded_at ? String(item.last_loaded_at) : undefined,
        lastHealthCheckAt: item.last_health_check_at ? String(item.last_health_check_at) : undefined,
        lastRefreshedAt: String(item.last_refreshed_at ?? ""),
      },
    ]),
  );
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
