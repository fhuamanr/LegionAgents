"use client";

import { useMemo, useState } from "react";
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
  const [selectedId, setSelectedId] = useState(prompts[0]?.id ?? "");
  const selected = prompts.find((prompt) => prompt.id === selectedId) ?? prompts[0];
  const [draft, setDraft] = useState(selected?.markdown ?? "");
  const [testInput, setTestInput] = useState("Generate a repository-aware implementation plan.");
  const selectedVersions = useMemo(
    () => versions.filter((version) => version.promptId === selected?.id),
    [selected?.id, versions],
  );
  const rendered = useMemo(() => renderPrompt(draft, selected?.variables ?? []), [draft, selected?.variables]);
  const estimatedTokens = Math.max(1, Math.round(rendered.length / 4));

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
          {prompts.map((prompt) => (
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
                <Button variant="outline" size="sm">
                  <FlaskConical className="h-4 w-4" aria-hidden="true" />
                  Test
                </Button>
                <Button size="sm">
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Save
                </Button>
              </div>
            </div>
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
                  <div className="text-xs text-muted-foreground">{testResult.evaluation.passed ? "Passing" : "Needs work"}</div>
                </div>
                <Badge variant={testResult.evaluation.passed ? "success" : "warning"}>{testResult.evaluation.score}/100</Badge>
              </div>
              <div className="mt-3 space-y-2">
                {(testResult.evaluation.findings.length ? testResult.evaluation.findings : ["No evaluation findings."]).map((finding) => (
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
                    <Button variant="outline" size="sm">
                      <GitCompareArrows className="h-4 w-4" aria-hidden="true" />
                      Compare
                    </Button>
                    <Button variant="outline" size="sm">
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
}

function renderPrompt(markdown: string, variables: readonly { name: string; default?: string }[]): string {
  return variables.reduce(
    (current, variable) => current.replaceAll(`{{${variable.name}}}`, variable.default ?? `<${variable.name}>`),
    markdown,
  );
}
