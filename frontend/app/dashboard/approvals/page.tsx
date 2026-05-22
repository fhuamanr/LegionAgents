import { AppShell } from "@/components/layout/app-shell";
import { ApprovalGatesPanel } from "@/features/approvals/approval-gates-panel";
import { ExecutionTimeline } from "@/features/executions/execution-timeline";
import { getDashboardSnapshot } from "@/lib/api";

export default async function ApprovalsPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1fr_28rem]">
        <ApprovalGatesPanel approvals={snapshot.approvals} />
        <ExecutionTimeline items={snapshot.timeline} />
      </div>
    </AppShell>
  );
}
