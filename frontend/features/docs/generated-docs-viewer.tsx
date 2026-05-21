import { FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { DocumentationArtifact } from "@/lib/types";

export function GeneratedDocsViewer({ docs }: Readonly<{ docs: readonly DocumentationArtifact[] }>): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Generated Documentation</CardTitle>
        <CardDescription>Artifacts emitted by the docs agent after QA approval</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {docs.map((doc) => (
          <div key={doc.id} className="rounded-md border bg-background p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
                {doc.title}
              </div>
              <Badge variant={doc.status === "published" ? "success" : doc.status === "generated" ? "default" : "muted"}>{doc.status}</Badge>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{doc.summary}</p>
            <div className="mt-3 text-xs text-muted-foreground">Updated {formatDateTime(doc.updatedAt)}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
