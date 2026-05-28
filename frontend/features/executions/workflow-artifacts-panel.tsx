"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Artifact = {
  name: string;
  agentName: string;
  relativePath: string;
  absolutePath: string;
  sizeBytes: number;
  createdAt: string;
  preview: string;
};

type ArtifactPrefs = {
  query: string;
  agentFilter: string;
  pageSize: number;
  expanded: Record<string, boolean>;
};

const PREF_KEY = "dashboard.artifacts.preferences.v2";

export function WorkflowArtifactsPanel({ workflowId, artifacts }: Readonly<{ workflowId: string; artifacts: readonly Artifact[] }>): JSX.Element {
  const [query, setQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState<"all" | string>("all");
  const [pageSize, setPageSize] = useState(120);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(PREF_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as Partial<ArtifactPrefs>;
      if (typeof parsed.query === "string") setQuery(parsed.query);
      if (typeof parsed.agentFilter === "string") setAgentFilter(parsed.agentFilter);
      if (typeof parsed.pageSize === "number") setPageSize(parsed.pageSize);
      if (parsed.expanded && typeof parsed.expanded === "object") setExpanded(parsed.expanded as Record<string, boolean>);
    } catch {
      // ignore cache parse errors
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const payload: ArtifactPrefs = { query, agentFilter, pageSize, expanded };
    window.localStorage.setItem(PREF_KEY, JSON.stringify(payload));
  }, [query, agentFilter, pageSize, expanded]);

  const agents = useMemo(() => ["all", ...new Set(artifacts.map((item) => item.agentName).filter(Boolean))], [artifacts]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return artifacts.filter((item) => {
      if (agentFilter !== "all" && item.agentName !== agentFilter) return false;
      if (!q) return true;
      return item.relativePath.toLowerCase().includes(q) || item.name.toLowerCase().includes(q) || item.preview.toLowerCase().includes(q);
    });
  }, [artifacts, query, agentFilter]);

  const grouped = useMemo(
    () =>
      filtered.reduce<Record<string, Artifact[]>>((acc, item) => {
        (acc[item.agentName || "unknown"] ||= []).push(item);
        return acc;
      }, {}),
    [filtered],
  );

  const depthArtifact = artifacts.find((item) => item.relativePath.endsWith("developer/generated_project/developer_quality_report.md"));
  const shallowWarnings = artifacts.filter((item) => item.relativePath.includes("developer_depth_analysis.md")).length;
  const governanceReports = artifacts.filter((item) => item.relativePath.endsWith("governance_report.json")).length;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Artifact Workspace</CardTitle>
        <CardDescription>Artifacts saved at data/artifacts/{workflowId}/</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 rounded-md border p-3 text-xs md:grid-cols-4">
          <div>Artifacts: {artifacts.length}</div>
          <div>Governance reports: {governanceReports}</div>
          <div>Depth analyses: {shallowWarnings}</div>
          <div>Agents with artifacts: {Object.keys(grouped).length}</div>
        </div>

        {depthArtifact ? (
          <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs">
            <div className="font-semibold">Developer depth score available</div>
            <div className="mt-1 whitespace-pre-wrap text-muted-foreground">{depthArtifact.preview}</div>
          </div>
        ) : null}

        <div className="grid gap-2 md:grid-cols-[1fr_12rem_9rem]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search artifacts..."
            className="rounded-md border bg-background px-3 py-2 text-sm"
          />
          <select
            value={agentFilter}
            onChange={(event) => setAgentFilter(event.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
          >
            {agents.map((agent) => (
              <option key={agent} value={agent}>
                {agent}
              </option>
            ))}
          </select>
          <select
            value={String(pageSize)}
            onChange={(event) => setPageSize(Number(event.target.value))}
            className="rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="80">80 rows</option>
            <option value="120">120 rows</option>
            <option value="200">200 rows</option>
          </select>
        </div>

        {filtered.length === 0 ? (
          <div className="rounded-md border p-3 text-sm text-muted-foreground">No artifacts match current filters.</div>
        ) : (
          Object.entries(grouped).map(([agent, files]) => {
            const isExpanded = expanded[agent] ?? true;
            const visible = isExpanded ? files.slice(0, pageSize) : [];
            return (
              <div key={agent} className="rounded-md border p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <button
                    type="button"
                    className="text-left text-sm font-semibold capitalize"
                    onClick={() => setExpanded((current) => ({ ...current, [agent]: !isExpanded }))}
                  >
                    {isExpanded ? "▾" : "▸"} {agent}
                  </button>
                  <Badge variant="muted">{files.length} files</Badge>
                </div>
                {isExpanded ? (
                  <div className="space-y-2">
                    {visible.map((file) => (
                      <details key={`${agent}-${file.relativePath}`} className="rounded-md border bg-muted/30 p-2">
                        <summary className="cursor-pointer text-xs font-medium">{file.relativePath}</summary>
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {new Date(file.createdAt).toLocaleString()} · {(file.sizeBytes / 1024).toFixed(1)} KB
                        </div>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs">{file.preview || "(binary or empty)"}</pre>
                      </details>
                    ))}
                    {files.length > pageSize ? (
                      <div className="text-xs text-muted-foreground">Showing {pageSize} of {files.length} files. Narrow search or increase page size.</div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
