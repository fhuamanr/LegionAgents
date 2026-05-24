"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type ArtifactItem = {
  id: string;
  workflow_id: string;
  execution_id: string;
  agent_name: string;
  raw_output: string;
  structured_output: Record<string, unknown>;
  handoff: string;
  execution_log: string;
  token_report: Record<string, unknown>;
  created_at: string;
};

const AGENTS = ["ba", "architect", "developer", "qa", "docs", "pr"] as const;

export function AgentPlayground(): JSX.Element {
  const [agentName, setAgentName] = useState<string>("ba");
  const [inputSource, setInputSource] = useState<string>("manual_prompt");
  const [prompt, setPrompt] = useState<string>("Necesito un MVP de e-commerce con productos, usuarios y carrito.");
  const [workflowId, setWorkflowId] = useState<string>("");
  const [previousAgent, setPreviousAgent] = useState<string>("ba");
  const [artifacts, setArtifacts] = useState<readonly ArtifactItem[]>([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string>("");
  const [handoffEdit, setHandoffEdit] = useState<string>("");
  const [message, setMessage] = useState<string>("");
  const [running, setRunning] = useState<boolean>(false);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Agent Playground</CardTitle>
          <CardDescription>Run one agent at a time, inspect artifacts, edit handoff, then continue.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-4">
            <Select label="Agent" value={agentName} onChange={setAgentName} options={AGENTS as unknown as string[]} />
            <Select label="Input source" value={inputSource} onChange={setInputSource} options={["manual_prompt", "previous_agent_handoff", "previous_agent_raw_output"]} />
            <Select label="Previous agent" value={previousAgent} onChange={setPreviousAgent} options={AGENTS as unknown as string[]} />
            <Input label="Workflow id" value={workflowId} onChange={setWorkflowId} placeholder="auto-generated" />
          </div>
          <label className="space-y-1 text-xs font-medium">
            <span>Prompt/Input</span>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} className="min-h-28 w-full rounded-md border bg-background p-2 text-sm" />
          </label>
          <div className="flex gap-2">
            <Button disabled={running} onClick={() => void runStep()}>
              {running ? "Running..." : "Run agent"}
            </Button>
            <Button variant="outline" onClick={() => void loadArtifacts()}>
              Refresh artifacts
            </Button>
            <Button variant="outline" onClick={() => void sendToArchitect()}>
              Send to Architect
            </Button>
          </div>
          {message ? <p className="text-xs text-muted-foreground">{message}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Artifacts</CardTitle>
          <CardDescription>raw_output.md, structured_output.json, handoff.md, execution_log.txt, token_report.json</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="max-h-64 space-y-2 overflow-y-auto rounded-md border p-2">
            {artifacts.map((artifact) => (
              <button
                key={artifact.id}
                type="button"
                className="w-full rounded border p-2 text-left text-xs"
                onClick={() => {
                  setSelectedExecutionId(artifact.execution_id);
                  setHandoffEdit(artifact.handoff);
                }}
              >
                <div className="font-medium">{artifact.agent_name} - {artifact.execution_id}</div>
                <div className="text-muted-foreground">{new Date(artifact.created_at).toLocaleString()}</div>
              </button>
            ))}
          </div>
          <label className="space-y-1 text-xs font-medium">
            <span>Handoff editor</span>
            <textarea value={handoffEdit} onChange={(event) => setHandoffEdit(event.target.value)} className="min-h-40 w-full rounded-md border bg-background p-2 text-sm" />
          </label>
          <Button variant="outline" onClick={() => void saveHandoff()}>
            Save handoff
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  async function runStep(): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    setRunning(true);
    setMessage("");
    try {
      const response = await fetch(`${apiBaseUrl}/agent-playground/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          workflow_id: workflowId || null,
          agent_name: agentName,
          input_source: inputSource,
          prompt,
          previous_agent: previousAgent,
          local_lm_studio_safe_mode: true,
          compact_mode_enabled: true,
        }),
      });
      if (!response.ok) throw new Error(await extractError(response));
      const payload = (await response.json()) as { artifact: ArtifactItem; warnings: string[] };
      setWorkflowId(payload.artifact.workflow_id);
      setArtifacts((current) => [...current, payload.artifact]);
      setSelectedExecutionId(payload.artifact.execution_id);
      setHandoffEdit(payload.artifact.handoff);
      setMessage(`Agent completed. Input tokens: ${String(payload.artifact.token_report.input_tokens ?? 0)} | Output tokens: ${String(payload.artifact.token_report.output_tokens ?? 0)}`);
    } catch (error) {
      setMessage(`Run failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setRunning(false);
    }
  }

  async function loadArtifacts(): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl || !workflowId) return;
    const response = await fetch(`${apiBaseUrl}/agent-playground/${workflowId}/artifacts`, { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    const payload = (await response.json()) as { artifacts: ArtifactItem[] };
    setArtifacts(payload.artifacts);
  }

  async function saveHandoff(): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl || !workflowId || !selectedExecutionId) return;
    const response = await fetch(`${apiBaseUrl}/agent-playground/${workflowId}/artifacts/${selectedExecutionId}/handoff`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ handoff: handoffEdit }),
    });
    if (!response.ok) return;
    setMessage("Handoff updated.");
    await loadArtifacts();
  }

  async function sendToArchitect(): Promise<void> {
    setAgentName("architect");
    setInputSource("previous_agent_handoff");
    setPreviousAgent("ba");
    await runStep();
  }
}

function Input({ label, value, onChange, placeholder }: Readonly<{ label: string; value: string; onChange: (value: string) => void; placeholder: string }>): JSX.Element {
  return (
    <label className="space-y-1 text-xs font-medium">
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="h-9 w-full rounded-md border bg-background px-3 text-sm" />
    </label>
  );
}

function Select({ label, value, onChange, options }: Readonly<{ label: string; value: string; onChange: (value: string) => void; options: readonly string[] }>): JSX.Element {
  return (
    <label className="space-y-1 text-xs font-medium">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-9 w-full rounded-md border bg-background px-3 text-sm">
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

async function extractError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || `${response.status} ${response.statusText}`;
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}
