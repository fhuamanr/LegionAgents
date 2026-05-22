import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceChat } from "@/features/workspace/workspace-chat";
import { getDashboardSnapshot } from "@/lib/api";

export default async function WorkspacePage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <WorkspaceChat conversations={snapshot.workspace.conversations} />
    </AppShell>
  );
}
