import { AppShell } from "@/components/layout/app-shell";
import { AgentPlayground } from "@/features/playground/agent-playground";

export default function PlaygroundPage(): JSX.Element {
  return (
    <AppShell>
      <AgentPlayground />
    </AppShell>
  );
}
