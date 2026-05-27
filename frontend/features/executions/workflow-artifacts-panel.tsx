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

export function WorkflowArtifactsPanel({ workflowId, artifacts }: Readonly<{ workflowId: string; artifacts: readonly Artifact[] }>): JSX.Element {
  const grouped = artifacts.reduce<Record<string, Artifact[]>>((acc, item) => {
    (acc[item.agentName] ||= []).push(item);
    return acc;
  }, {});
  const byZone = {
    frontend: artifacts.filter((item) => item.relativePath.includes("developer/code/src/components")),
    backend: artifacts.filter((item) => item.relativePath.includes("developer/code/src") && !item.relativePath.includes("components")),
    qa: artifacts.filter((item) => item.relativePath.startsWith("qa/")),
    docs: artifacts.filter((item) => item.relativePath.startsWith("docs/")),
    diagrams: artifacts.filter((item) => item.relativePath.includes("/diagrams/") || item.relativePath.endsWith(".mmd")),
  };
  const qualityReport = artifacts.find((item) => item.relativePath.endsWith("improvements/quality_report.md"));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Artifacts</CardTitle>
        <CardDescription>Artifacts saved at data/artifacts/{workflowId}/</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 rounded border p-3 text-xs sm:grid-cols-5">
          <div>Frontend files: {byZone.frontend.length}</div>
          <div>Backend files: {byZone.backend.length}</div>
          <div>QA files: {byZone.qa.length}</div>
          <div>Docs files: {byZone.docs.length}</div>
          <div>Diagrams: {byZone.diagrams.length}</div>
        </div>
        {qualityReport ? (
          <details className="rounded border bg-muted/30 p-2">
            <summary className="cursor-pointer text-xs font-semibold">Quality report available (improvements/quality_report.md)</summary>
            <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs">{qualityReport.preview}</pre>
          </details>
        ) : null}
        {Object.keys(grouped).length === 0 ? (
          <div className="text-sm text-muted-foreground">No artifacts available yet.</div>
        ) : (
          Object.entries(grouped).map(([agent, files]) => (
            <div key={agent} className="rounded border p-3">
              <div className="mb-2 text-sm font-semibold capitalize">{agent}</div>
              <div className="space-y-2">
                {files.map((file) => (
                  <details key={`${agent}-${file.relativePath}`} className="rounded border bg-muted/30 p-2">
                    <summary className="cursor-pointer text-xs font-medium">{file.relativePath}</summary>
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs">{file.preview || "(binary or empty)"}</pre>
                  </details>
                ))}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
