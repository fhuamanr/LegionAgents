import { AppShell } from "@/components/layout/app-shell";
import { GovernanceEditor } from "@/features/governance/governance-editor";
import { getDashboardSnapshot } from "@/lib/api";

export default async function GovernancePage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <GovernanceEditor documents={snapshot.governance.documents} versions={snapshot.governance.versions} />
    </AppShell>
  );
}
