import { AppShell } from "@/components/layout/app-shell";
import { PromptStudio } from "@/features/prompts/prompt-studio";
import { getPromptStudioSnapshot } from "@/lib/api";

export default async function PromptStudioPage(): Promise<JSX.Element> {
  const snapshot = await getPromptStudioSnapshot();

  return (
    <AppShell>
      <PromptStudio
        prompts={snapshot.prompts}
        versions={snapshot.versions}
        testResult={snapshot.testResult}
      />
    </AppShell>
  );
}
