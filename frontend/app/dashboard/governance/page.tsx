import { AppShell } from "@/components/layout/app-shell";
import { GovernanceEditor } from "@/features/governance/governance-editor";
import { getGovernanceManagementSnapshot } from "@/lib/api";

export default async function GovernancePage(): Promise<JSX.Element> {
  const snapshot = await getGovernanceManagementSnapshot();

  return (
    <AppShell>
      <GovernanceEditor documents={snapshot.documents} versions={snapshot.versions} />
    </AppShell>
  );
}
