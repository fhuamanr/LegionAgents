"use client";

import { useMemo, useState } from "react";
import { History, RotateCcw, Save, Settings2 } from "lucide-react";
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
  const [selectedId, setSelectedId] = useState(documents[0]?.id ?? "");
  const selected = documents.find((document) => document.id === selectedId) ?? documents[0];
  const [draft, setDraft] = useState(selected?.markdown ?? "");
  const selectedVersions = useMemo(
    () => versions.filter((version) => version.documentId === selected?.id),
    [selected?.id, versions],
  );

  function selectDocument(document: GovernanceConfigDocument): void {
    setSelectedId(document.id);
    setDraft(document.markdown);
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[20rem_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Governance Documents</CardTitle>
          <CardDescription>Global defaults and agent-specific configurations</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {documents.map((document) => (
            <button
              key={document.id}
              type="button"
              onClick={() => selectDocument(document)}
              className="w-full rounded-md border bg-background p-3 text-left transition-colors hover:bg-muted"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{document.name}</span>
                <Badge variant={document.scope === "global" ? "success" : "default"}>{document.scope}</Badge>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant="muted">{document.kind}</Badge>
                {document.agentName ? <Badge variant="default">{document.agentName}</Badge> : null}
              </div>
              <div className="mt-2 text-xs text-muted-foreground">v{document.version} / {formatDateTime(document.updatedAt)}</div>
            </button>
          ))}
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>{selected?.name ?? "Governance Editor"}</CardTitle>
                <CardDescription>Markdown editor with live persistence and reload-ready metadata</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Settings2 className="h-4 w-4" aria-hidden="true" />
                  Reload
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
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                className="min-h-[30rem] w-full resize-y rounded-md border bg-background p-4 font-mono text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring"
                spellCheck={false}
              />
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
            <CardDescription>Rollback-ready history for the selected governance document</CardDescription>
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
                <Button variant="outline" size="sm">
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
}
