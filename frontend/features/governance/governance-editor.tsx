"use client";

import { useEffect, useMemo, useState } from "react";
import { History, RotateCcw, Save, Search, Settings2, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { GovernanceConfigDocument, GovernanceConfigVersion } from "@/lib/types";

export function GovernanceEditor({
  documents,
  versions,
}: Readonly<{
  documents: readonly GovernanceConfigDocument[];
  versions: readonly GovernanceConfigVersion[];
}>): JSX.Element {
  const [items, setItems] = useState<readonly GovernanceConfigDocument[]>(documents);
  const [history, setHistory] = useState<readonly GovernanceConfigVersion[]>(versions);
  const [selectedId, setSelectedId] = useState(documents[0]?.id ?? "");
  const [notice, setNotice] = useState<string | null>(documents.length ? null : "No governance documents found yet.");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");
  const [kindFilter, setKindFilter] = useState("all");
  const [activeFilter, setActiveFilter] = useState("all");
  const selected = items.find((document) => document.id === selectedId) ?? items[0];
  const [draft, setDraft] = useState(selected?.markdown ?? "");

  useEffect(() => {
    setDraft(selected?.markdown ?? "");
  }, [selectedId, selected?.markdown]);

  const selectedVersions = useMemo(
    () => history.filter((version) => version.documentId === selected?.id),
    [selected?.id, history],
  );

  const filtered = useMemo(() => {
    return items.filter((document) => {
      const searchable = `${document.name} ${document.kind} ${document.agentName ?? ""}`.toLowerCase();
      const matchesQuery = searchable.includes(query.toLowerCase());
      const matchesAgent = agentFilter === "all" || (document.agentName ?? "global") === agentFilter;
      const matchesKind = kindFilter === "all" || document.kind === kindFilter;
      const isActive = document.isActive ?? true;
      const matchesActive = activeFilter === "all" || (activeFilter === "active" ? isActive : !isActive);
      return matchesQuery && matchesAgent && matchesKind && matchesActive;
    });
  }, [items, query, agentFilter, kindFilter, activeFilter]);

  const availableAgents = useMemo(() => {
    const values = new Set<string>();
    items.forEach((item) => values.add(item.agentName ?? "global"));
    return ["all", ...Array.from(values).sort()];
  }, [items]);

  const availableKinds = useMemo(() => ["all", ...Array.from(new Set(items.map((item) => item.kind))).sort()], [items]);

  return (
    <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
      <Card className="min-h-[75vh]">
        <CardHeader>
          <CardTitle>Governance Documents</CardTitle>
          <CardDescription>Filter by agent/type and edit runtime policies.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search documents" className="h-9 w-full rounded-md border bg-background pl-8 pr-3 text-sm" />
          </label>
          <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-1">
            <select value={agentFilter} onChange={(event) => setAgentFilter(event.target.value)} className="h-9 rounded-md border bg-background px-2 text-xs">
              {availableAgents.map((agent) => <option key={agent} value={agent}>{agent}</option>)}
            </select>
            <select value={kindFilter} onChange={(event) => setKindFilter(event.target.value)} className="h-9 rounded-md border bg-background px-2 text-xs">
              {availableKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
            </select>
            <select value={activeFilter} onChange={(event) => setActiveFilter(event.target.value)} className="h-9 rounded-md border bg-background px-2 text-xs">
              <option value="all">all status</option>
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
          </div>
          <Button variant="outline" className="w-full justify-start" disabled={busy} onClick={() => newDocument()}>
            <Save className="h-4 w-4" aria-hidden="true" />
            New governance document
          </Button>
          <div className="max-h-[58vh] space-y-2 overflow-auto pr-1">
            {filtered.map((document) => (
              <button key={document.id} type="button" onClick={() => setSelectedId(document.id)} className="w-full rounded-md border bg-background p-3 text-left transition-colors hover:bg-muted">
                <div className="flex items-center justify-between gap-2">
                  <span className="line-clamp-2 text-sm font-medium">{document.name}</span>
                  <Badge variant={document.scope === "global" ? "success" : "default"}>{document.scope}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant="muted">{document.kind}</Badge>
                  {document.agentName ? <Badge variant="default">{document.agentName}</Badge> : null}
                  <Badge variant={document.isActive ? "success" : "warning"}>{document.isActive ? "active" : "inactive"}</Badge>
                </div>
                <div className="mt-2 text-xs text-muted-foreground">v{document.version} / {formatDateTime(document.updatedAt)}</div>
                <div className="mt-1 text-xs text-muted-foreground">{document.sourceType ?? "runtime_created"}{document.sourcePath ? ` / ${document.sourcePath}` : ""}</div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>{selected?.name ?? "Governance Editor"}</CardTitle>
                <CardDescription>Edit markdown and persist a new version.</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => void refreshDocuments()} disabled={busy}>
                  <Settings2 className="h-4 w-4" aria-hidden="true" />
                  Reload
                </Button>
                <Button size="sm" onClick={() => void saveDocument()} disabled={busy || !selected}>
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Save
                </Button>
                <Button variant="destructive" size="sm" onClick={() => void deleteDocument()} disabled={busy || !selected || selected.protected}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  Delete
                </Button>
              </div>
            </div>
            {notice ? <p className="mt-3 text-xs text-muted-foreground">{notice}</p> : null}
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 xl:grid-cols-2">
              <textarea value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-[30rem] w-full resize-y rounded-md border bg-background p-4 font-mono text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring" spellCheck={false} />
              <div className="min-h-[30rem] rounded-md border bg-background p-4">
                <div className="mb-3 text-xs font-medium text-muted-foreground">Preview</div>
                <div className="whitespace-pre-wrap rounded-md bg-muted p-4 font-mono text-sm">{draft}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Version History</CardTitle>
            <CardDescription>Rollback-ready history for the selected document.</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[24rem] space-y-3 overflow-auto">
            {selectedVersions.map((version) => (
              <div key={version.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-4">
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <History className="h-4 w-4 text-primary" aria-hidden="true" />
                    Version {version.version}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{version.changeSummary ?? "No summary"} / {version.changedBy} / {formatDateTime(version.createdAt)}</p>
                </div>
                <Button variant="outline" size="sm" onClick={() => void rollback(version.version)} disabled={busy}>
                  <RotateCcw className="h-4 w-4" aria-hidden="true" />
                  Rollback
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );

  function newDocument(): void {
    const document: GovernanceConfigDocument = {
      id: `new-${Date.now()}`,
      scope: "global",
      kind: "gravity",
      name: "New Governance Rule",
      markdown: "- Describe the rule here.",
      version: 1,
      updatedBy: "workspace-user",
      updatedAt: new Date().toISOString(),
      isActive: true,
      protected: false,
    };
    setItems((current) => [document, ...current]);
    setSelectedId(document.id);
    setNotice("Edit the new document and save it.");
  }

  async function deleteDocument(): Promise<void> {
    if (!selected) return;
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/governance/configs/${selected.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const remaining = items.filter((item) => item.id !== selected.id);
      setItems(remaining);
      setSelectedId(remaining[0]?.id ?? "");
      setNotice("Document deleted.");
    } catch (error) {
      setNotice(`Delete failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function saveDocument(): Promise<void> {
    if (!selected) return;
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      setNotice("NEXT_PUBLIC_API_BASE_URL is not configured.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/governance/configs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          scope: selected.scope,
          kind: selected.kind,
          name: selected.name,
          markdown: draft,
          agent_name: selected.agentName,
          updated_by: "workspace-user",
          change_summary: "Saved from Governance UI",
        }),
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const payload = (await response.json()) as { document: Record<string, unknown>; latest_version?: Record<string, unknown> };
      const saved = normalizeGovernanceDocument(payload.document);
      setItems((current) => [saved, ...current.filter((item) => item.id !== selected.id && item.id !== saved.id)]);
      setSelectedId(saved.id);
      if (payload.latest_version) {
        const version = normalizeGovernanceVersion(payload.latest_version);
        setHistory((current) => [version, ...current.filter((item) => item.id !== version.id)]);
      }
      setNotice("Governance document saved.");
    } catch (error) {
      setNotice(`Save failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function rollback(version: number): Promise<void> {
    if (!selected) return;
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/governance/configs/${selected.id}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ target_version: version, updated_by: "workspace-user" }),
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const payload = (await response.json()) as { document: Record<string, unknown>; latest_version?: Record<string, unknown> };
      const rolledBack = normalizeGovernanceDocument(payload.document);
      setItems((current) => current.map((item) => item.id === rolledBack.id ? rolledBack : item));
      if (payload.latest_version) setHistory((current) => [normalizeGovernanceVersion(payload.latest_version as Record<string, unknown>), ...current]);
      setNotice(`Rolled back to version ${version}.`);
    } catch (error) {
      setNotice(`Rollback failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function refreshDocuments(): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/governance/configs`, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const payload = (await response.json()) as { documents: readonly Record<string, unknown>[] };
      const refreshed = payload.documents.map(normalizeGovernanceDocument);
      setItems(refreshed);
      if (!refreshed.find((item) => item.id === selectedId)) {
        setSelectedId(refreshed[0]?.id ?? "");
      }
      setNotice("Governance documents reloaded.");
    } catch (error) {
      setNotice(`Reload failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }
}

function normalizeGovernanceDocument(item: Record<string, unknown>): GovernanceConfigDocument {
  return {
    id: String(item.id),
    scope: String(item.scope) as GovernanceConfigDocument["scope"],
    kind: String(item.kind) as GovernanceConfigDocument["kind"],
    name: String(item.name),
    markdown: String(item.markdown ?? ""),
    agentName: item.agent_name ? String(item.agent_name) : undefined,
    version: Number(item.version ?? 1),
    updatedBy: String(item.updated_by ?? "system"),
    updatedAt: String(item.updated_at ?? ""),
    sourceType: item.source_type ? String(item.source_type) : undefined,
    sourcePath: item.source_path ? String(item.source_path) : undefined,
    isActive: Boolean(item.is_active ?? true),
    protected: Boolean(item.protected ?? false),
  };
}

function normalizeGovernanceVersion(item: Record<string, unknown>): GovernanceConfigVersion {
  return {
    id: String(item.id),
    documentId: String(item.document_id),
    version: Number(item.version ?? 1),
    markdown: String(item.markdown ?? ""),
    changedBy: String(item.changed_by ?? "system"),
    changeSummary: item.change_summary ? String(item.change_summary) : undefined,
    createdAt: String(item.created_at ?? ""),
  };
}
