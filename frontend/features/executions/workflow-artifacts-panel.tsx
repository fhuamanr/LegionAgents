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
  return (
    <Card>
      <CardHeader>
        <CardTitle>Artifacts</CardTitle>
        <CardDescription>Artifacts saved at data/artifacts/{workflowId}/</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
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
