import { AppShell } from "@/components/layout/app-shell";
import { QaReportViewer } from "@/features/qa/qa-report-viewer";
import { ScreenshotGallery } from "@/features/qa/screenshot-gallery";
import { getDashboardSnapshot } from "@/lib/api";

export default async function QaPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1fr_28rem]">
        <QaReportViewer report={snapshot.qaReport} />
        <ScreenshotGallery screenshots={snapshot.qaReport.screenshots} />
      </div>
    </AppShell>
  );
}
