import { AppShell } from "@/components/layout/app-shell";
import { ProviderManagement } from "@/features/providers/provider-management";
import { getProviderManagementSnapshot } from "@/lib/api";

export default async function ProvidersPage(): Promise<JSX.Element> {
  const snapshot = await getProviderManagementSnapshot();

  return (
    <AppShell>
      <ProviderManagement providers={snapshot.providers} checks={snapshot.checks} />
    </AppShell>
  );
}
