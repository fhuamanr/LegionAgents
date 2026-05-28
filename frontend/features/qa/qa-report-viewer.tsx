import { Bug, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { QaReport, Severity } from "@/lib/types";

const severityVariant: Record<Severity, "default" | "success" | "warning" | "destructive" | "muted"> = {
  critical: "destructive",
  high: "destructive",
  medium: "warning",
  low: "default",
  info: "muted",
};

export function QaReportViewer({ report }: Readonly<{ report: QaReport }>): JSX.Element {
  const noDataYet =
    report.unitTests === 0 &&
    report.integrationTests === 0 &&
    report.browserTests === 0 &&
    report.bugs.length === 0 &&
    report.coveragePercent === 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>QA Report</CardTitle>
            <CardDescription>Coverage, browser automation, evidence, and bug summary</CardDescription>
          </div>
          <Badge variant={report.status === "failed" ? "destructive" : report.status === "passed" ? "success" : "default"}>
            {report.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {noDataYet && report.status === "running" ? (
          <div className="rounded-md border bg-background p-4 text-sm text-muted-foreground">QA has not executed yet.</div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-4">
            <Metric label="Coverage" value={report.coveragePercent > 0 ? `${report.coveragePercent}%` : "not available"} />
            <Metric label="Unit" value={report.unitTests > 0 ? String(report.unitTests) : "not available"} />
            <Metric label="Integration" value={report.integrationTests > 0 ? String(report.integrationTests) : "not available"} />
            <Metric label="Browser" value={report.browserTests > 0 ? String(report.browserTests) : "not available"} />
          </div>
        )}
        <div className="mt-5 space-y-3">
          {report.bugs.map((bug) => (
            <div key={bug.id} className="rounded-md border bg-background p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Bug className="h-4 w-4 text-primary" aria-hidden="true" />
                  {bug.title}
                </div>
                <div className="flex gap-2">
                  <Badge variant={severityVariant[bug.severity]}>{bug.severity}</Badge>
                  <Badge variant="muted">{bug.status}</Badge>
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{bug.evidence}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: Readonly<{ label: string; value: string }>): JSX.Element {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
        {label}
      </div>
      <div className="mt-2 text-lg font-semibold">{value}</div>
    </div>
  );
}
