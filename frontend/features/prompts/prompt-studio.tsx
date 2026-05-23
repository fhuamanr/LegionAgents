"use client";

import { useEffect, useMemo, useState } from "react";
import { FlaskConical, GitCompareArrows, History, RotateCcw, Save } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { PromptDocument, PromptTestSummary, PromptVersion } from "@/lib/types";

export function PromptStudio({
  prompts,
  versions,
  testResult,
}: Readonly<{
  prompts: readonly PromptDocument[];
  versions: readonly PromptVersion[];
  testResult: PromptTestSummary;
}>): JSX.Element {
  const [items, setItems] = useState<readonly PromptDocument[]>(prompts);
  const [history, setHistory] = useState<readonly PromptVersion[]>(versions);
  const [result, setResult] = useState<PromptTestSummary>(testResult);
  const [selectedId, setSelectedId] = useState(prompts[0]?.id ?? "");
  const [notice, setNotice] = useState<string | null>(prompts.length ? null : "No prompts found yet. Use New Prompt to create an editable runtime prompt.");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [scopeFilter, setScopeFilter] = useState("all");
  const selected = items.find((prompt) => prompt.id === selectedId) ?? items[0];
  const [draft, setDraft] = useState(selected?.markdown ?? "");
  const [testInput, setTestInput] = useState("Generate a repository-aware implementation plan.");
  const selectedVersions = useMemo(
    () => history.filter((version) => version.promptId === selected?.id),
    [selected?.id, history],
  );
  const rendered = useMemo(() => renderPrompt(draft, selected?.variables ?? []), [draft, selected?.variables]);
  const estimatedTokens = Math.max(1, Math.round(rendered.length / 4));
  useEffect(() => {
    setDraft(selected?.markdown ?? "");
  }, [selectedId, selected?.markdown]);
  const filtered = useMemo(
    () => items.filter((prompt) => {
      const matchesQuery = `${prompt.name} ${prompt.agentName ?? ""}`.toLowerCase().includes(query.toLowerCase());
      const matchesScope = scopeFilter === "all" || prompt.scope === scopeFilter;
      return matchesQuery && matchesScope;
    }),
    [items, query, scopeFilter],
  );

  function selectPrompt(prompt: PromptDocument): void {
    setSelectedId(prompt.id);
    setDraft(prompt.markdown);
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[21rem_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Prompt Library</CardTitle>
          <CardDescription>Agent prompts with versioned markdown templates</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid gap-2">
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search prompts" className="h-9 rounded-md border bg-background px-3 text-sm" />
            <select value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value)} className="h-9 rounded-md border bg-background px-3 text-sm">
              <option value="all">all scopes</option>
              <option value="global">global</option>
              <option value="agent">agent</option>
              <option value="workflow">workflow</option>
            </select>
          </div>
          <Button variant="outline" className="w-full justify-start" disabled={busy} onClick={() => newPrompt()}>
            <Save className="h-4 w-4" aria-hidden="true" />
            New Prompt
          </Button>
          {filtered.map((prompt) => (
            <button
              key={prompt.id}
              type="button"
              onClick={() => selectPrompt(prompt)}
              className="w-full rounded-md border bg-background p-3 text-left transition-colors hover:bg-muted"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{prompt.name}</span>
                <Badge variant={prompt.status === "active" ? "success" : "muted"}>{prompt.status}</Badge>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant="default">{prompt.scope}</Badge>
                {prompt.agentName ? <Badge variant="muted">{prompt.agentName}</Badge> : null}
                <Badge variant="muted">v{prompt.version}</Badge>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">{formatDateTime(prompt.updatedAt)}</div>
            </button>
          ))}
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>{selected?.name ?? "Prompt Editor"}</CardTitle>
                <CardDescription>Markdown editing, variables, preview, token estimation, and live testing</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => void testPrompt()} disabled={busy || !draft.trim()}>
                  <FlaskConical className="h-4 w-4" aria-hidden="true" />
                  Test
                </Button>
                <Button size="sm" onClick={() => void savePrompt()} disabled={busy || !selected}>
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Save
                </Button>
              </div>
            </div>
            {notice ? <p className="mt-3 text-xs text-muted-foreground">{notice}</p> : null}
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="space-y-3">
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  className="min-h-[28rem] w-full resize-y rounded-md border bg-background p-4 font-mono text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring"
                  spellCheck={false}
                />
                <div className="flex flex-wrap gap-2">
                  <Badge variant="default">{estimatedTokens} tokens est.</Badge>
                  <Badge variant="muted">{draft.length} chars</Badge>
                  {(selected?.variables ?? []).map((variable) => (
                    <Badge key={variable.name} variant="muted">{`{{${variable.name}}}`}</Badge>
                  ))}
                </div>
              </div>
              <div className="space-y-4">
                <div className="rounded-md border bg-background p-4">
                  <div className="mb-3 text-xs font-medium text-muted-foreground">Execution Preview</div>
                  <div className="whitespace-pre-wrap rounded-md bg-muted p-4 font-mono text-sm">{rendered}</div>
                </div>
                <div className="rounded-md border bg-background p-4">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="prompt-test-input">Test Input</label>
                  <textarea
                    id="prompt-test-input"
                    value={testInput}
                    onChange={(event) => setTestInput(event.target.value)}
                    className="mt-2 min-h-24 w-full resize-y rounded-md border bg-background p-3 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring"
                  />
                  <div className="mt-3 rounded-md bg-muted p-3 text-xs text-muted-foreground">
                    {rendered}
                    {"\n\n# Test Input\n\n"}
                    {testInput}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Prompt Evaluation</CardTitle>
              <CardDescription>Live test readiness signals</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between rounded-md border bg-background p-4">
                <div>
                  <div className="text-sm font-medium">Evaluation Score</div>
                  <div className="text-xs text-muted-foreground">{result.evaluation.passed ? "Passing" : "Needs work"}</div>
                </div>
                <Badge variant={result.evaluation.passed ? "success" : "warning"}>{result.evaluation.score}/100</Badge>
              </div>
              <div className="mt-3 space-y-2">
                {(result.evaluation.findings.length ? result.evaluation.findings : ["No evaluation findings."]).map((finding) => (
                  <div key={finding} className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">{finding}</div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Version History</CardTitle>
              <CardDescription>Compare and rollback prompt revisions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {selectedVersions.map((version) => (
                <div key={version.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-4">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <History className="h-4 w-4 text-primary" aria-hidden="true" />
                      Version {version.version}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {version.changeSummary ?? "No summary"} / {version.changedBy} / {formatDateTime(version.createdAt)}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={selectedVersions.length < 2}>
                      <GitCompareArrows className="h-4 w-4" aria-hidden="true" />
                      Compare
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void rollback(version.version)} disabled={busy}>
                      <RotateCcw className="h-4 w-4" aria-hidden="true" />
                      Rollback
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );

  function newPrompt(): void {
    const prompt: PromptDocument = {
      id: `new-${Date.now()}`,
      name: "New Runtime Prompt",
      scope: "agent",
      agentName: "developer",
      markdown: "You are the {{agent}} agent.\n\nTask: {{task}}\n\nReturn valid JSON.",
      variables: [
        {name: "agent", required: true, default: "developer"},
        {name: "task", required: true, default: "Implement the requested change."},
      ],
      status: "draft",
      version: 1,
      updatedBy: "workspace-user",
      updatedAt: new Date().toISOString(),
    };
    setItems((current) => [prompt, ...current]);
    setSelectedId(prompt.id);
    setDraft(prompt.markdown);
    setNotice("Edit the new prompt and save it.");
  }

  async function savePrompt(): Promise<void> {
    if (!selected) return;
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      setNotice("NEXT_PUBLIC_API_BASE_URL is not configured.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/prompt-studio/prompts`, {
        method: "POST",
        headers: {"Content-Type": "application/json", Accept: "application/json"},
        body: JSON.stringify({
          name: selected.name,
          scope: selected.scope,
          agent_name: selected.agentName,
          markdown: draft,
          variables: selected.variables,
          status: selected.status,
          updated_by: "workspace-user",
          change_summary: "Saved from Prompt Studio UI",
        }),
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const payload = await response.json() as { prompt: Record<string, unknown>; latest_version?: Record<string, unknown> };
      const saved = normalizePromptDocument(payload.prompt);
      setItems((current) => [saved, ...current.filter((item) => item.id !== selected.id && item.id !== saved.id)]);
      setSelectedId(saved.id);
      if (payload.latest_version) {
        const version = normalizePromptVersion(payload.latest_version);
        setHistory((current) => [version, ...current.filter((item) => item.id !== version.id)]);
      }
      setNotice("Prompt saved and available for subsequent runtime injection.");
    } catch (error) {
      setNotice(`Save failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function testPrompt(): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/prompt-studio/prompts/test`, {
        method: "POST",
        headers: {"Content-Type": "application/json", Accept: "application/json"},
        body: JSON.stringify({
          prompt_id: selected?.id?.startsWith("new-") ? null : selected?.id,
          markdown: draft,
          variables: Object.fromEntries((selected?.variables ?? []).map((variable) => [variable.name, variable.default ?? ""])),
          test_input: testInput,
        }),
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const payload = await response.json() as { result: Record<string, unknown> };
      setResult(normalizePromptTestResult(payload.result));
      setNotice("Prompt test completed.");
    } catch (error) {
      setNotice(`Test failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function rollback(version: number): Promise<void> {
    if (!selected || selected.id.startsWith("new-")) return;
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/prompt-studio/prompts/${selected.id}/rollback`, {
        method: "POST",
        headers: {"Content-Type": "application/json", Accept: "application/json"},
        body: JSON.stringify({target_version: version, updated_by: "workspace-user"}),
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const payload = await response.json() as { prompt: Record<string, unknown>; latest_version?: Record<string, unknown> };
      const rolledBack = normalizePromptDocument(payload.prompt);
      setItems((current) => current.map((item) => item.id === rolledBack.id ? rolledBack : item));
      setDraft(rolledBack.markdown);
      if (payload.latest_version) {
        setHistory((current) => [normalizePromptVersion(payload.latest_version as Record<string, unknown>), ...current]);
      }
      setNotice(`Rolled back to version ${version}.`);
    } catch (error) {
      setNotice(`Rollback failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }
}

function renderPrompt(markdown: string, variables: readonly { name: string; default?: string }[]): string {
  return variables.reduce(
    (current, variable) => current.replaceAll(`{{${variable.name}}}`, variable.default ?? `<${variable.name}>`),
    markdown,
  );
}

function normalizePromptDocument(item: Record<string, unknown>): PromptDocument {
  const variables = Array.isArray(item.variables) ? item.variables as Record<string, unknown>[] : [];
  return {
    id: String(item.id),
    name: String(item.name),
    scope: String(item.scope) as PromptDocument["scope"],
    agentName: item.agent_name ? String(item.agent_name) : undefined,
    markdown: String(item.markdown ?? ""),
    variables: variables.map((variable) => ({
      name: String(variable.name),
      description: variable.description ? String(variable.description) : undefined,
      required: Boolean(variable.required),
      default: variable.default ? String(variable.default) : undefined,
    })),
    status: String(item.status) as PromptDocument["status"],
    version: Number(item.version ?? 1),
    updatedBy: String(item.updated_by ?? "system"),
    updatedAt: String(item.updated_at ?? ""),
  };
}

function normalizePromptVersion(item: Record<string, unknown>): PromptVersion {
  const variables = Array.isArray(item.variables) ? item.variables as Record<string, unknown>[] : [];
  return {
    id: String(item.id),
    promptId: String(item.prompt_id),
    version: Number(item.version ?? 1),
    markdown: String(item.markdown ?? ""),
    variables: variables.map((variable) => ({
      name: String(variable.name),
      description: variable.description ? String(variable.description) : undefined,
      required: Boolean(variable.required),
      default: variable.default ? String(variable.default) : undefined,
    })),
    changedBy: String(item.changed_by ?? "system"),
    changeSummary: item.change_summary ? String(item.change_summary) : undefined,
    createdAt: String(item.created_at ?? ""),
  };
}

function normalizePromptTestResult(item: Record<string, unknown>): PromptTestSummary {
  const preview = (item.preview ?? {}) as Record<string, unknown>;
  const evaluation = (item.evaluation ?? {}) as Record<string, unknown>;
  return {
    preview: {
      rendered: String(preview.rendered ?? ""),
      missingVariables: Array.isArray(preview.missing_variables) ? preview.missing_variables.map(String) : [],
      estimatedTokens: Number(preview.estimated_tokens ?? 0),
      characterCount: Number(preview.character_count ?? 0),
    },
    executionPreview: String(item.execution_preview ?? ""),
    evaluation: {
      score: Number(evaluation.score ?? 0),
      passed: Boolean(evaluation.passed),
      findings: Array.isArray(evaluation.findings) ? evaluation.findings.map(String) : [],
    },
  };
}
