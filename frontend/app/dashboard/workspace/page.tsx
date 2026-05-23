import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceChat } from "@/features/workspace/workspace-chat";
import { getWorkspaceChatSnapshot } from "@/lib/api";

export default async function WorkspacePage(): Promise<JSX.Element> {
  const conversations = await getWorkspaceChatSnapshot();

  return (
    <AppShell>
      <WorkspaceChat conversations={conversations} />
    </AppShell>
  );
}
