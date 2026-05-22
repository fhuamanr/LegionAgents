import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceManagement } from "@/features/workspace/workspace-management";
import { getDashboardSnapshot } from "@/lib/api";

export default async function WorkspacesPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <WorkspaceManagement
        workspaces={snapshot.workspace.workspaces}
        projects={snapshot.workspace.projects}
        isolation={snapshot.workspace.isolation}
      />
    </AppShell>
  );
}
