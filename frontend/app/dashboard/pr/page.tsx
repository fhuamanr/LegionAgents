import { AppShell } from "@/components/layout/app-shell";
import { MermaidDiagram } from "@/features/diagrams/mermaid-diagram";
import { PrSummaryPanel } from "@/features/pr/pr-summary-panel";
import { getDashboardSnapshot } from "@/lib/api";

export default async function PullRequestPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[28rem_1fr]">
        <PrSummaryPanel pullRequest={snapshot.pullRequest} />
        <MermaidDiagram chart={snapshot.mermaid} />
      </div>
    </AppShell>
  );
}
