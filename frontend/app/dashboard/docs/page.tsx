import { AppShell } from "@/components/layout/app-shell";
import { MermaidDiagram } from "@/features/diagrams/mermaid-diagram";
import { GeneratedDocsViewer } from "@/features/docs/generated-docs-viewer";
import { getDashboardSnapshot } from "@/lib/api";

export default async function DocsPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1fr_30rem]">
        <GeneratedDocsViewer docs={snapshot.docs} />
        <MermaidDiagram chart={snapshot.mermaid} />
      </div>
    </AppShell>
  );
}
