import { AppShell } from "@/components/layout/app-shell";
import { PromptStudio } from "@/features/prompts/prompt-studio";
import { getDashboardSnapshot } from "@/lib/api";

export default async function PromptStudioPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <PromptStudio
        prompts={snapshot.promptStudio.prompts}
        versions={snapshot.promptStudio.versions}
        testResult={snapshot.promptStudio.testResult}
      />
    </AppShell>
  );
}
