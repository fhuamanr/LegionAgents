import type { ReactNode } from "react";
import { CheckCircle2, CirclePause, ShieldAlert, UserCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { ApprovalGate, ApprovalStatus } from "@/lib/types";

const statusVariant: Record<ApprovalStatus, "default" | "success" | "warning" | "destructive" | "muted"> = {
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  cancelled: "muted",
  expired: "muted",
};

export function ApprovalGatesPanel({ approvals }: Readonly<{ approvals: readonly ApprovalGate[] }>): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>Human Approval Gates</CardTitle>
            <CardDescription>Manual reviews, retry approvals, PR approvals, and QA overrides</CardDescription>
          </div>
          <Badge variant={approvals.some((approval) => approval.status === "pending") ? "warning" : "success"}>
            {approvals.filter((approval) => approval.status === "pending").length} pending
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {approvals.map((approval) => (
          <div key={approval.approvalId} className="rounded-md border bg-background p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  {approval.status === "pending" ? (
                    <CirclePause className="h-4 w-4 text-amber-300" aria-hidden="true" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-emerald-300" aria-hidden="true" />
                  )}
                  {approval.title}
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{approval.description}</p>
              </div>
              <div className="flex gap-2">
                <Badge variant={statusVariant[approval.status]}>{approval.status}</Badge>
                <Badge variant="muted">{approval.gateType}</Badge>
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-xs md:grid-cols-3">
              <Fact icon={<ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />} label="Pause reason" value={approval.pauseReason} />
              <Fact icon={<UserCheck className="h-3.5 w-3.5" aria-hidden="true" />} label="Requested by" value={approval.requestedBy} />
              <Fact label="Created" value={formatDateTime(approval.createdAt)} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {approval.requiredReviewers.map((reviewer) => (
                <Badge key={reviewer.reviewerId} variant="default">
                  {reviewer.displayName}
                  {reviewer.role ? ` / ${reviewer.role}` : ""}
                </Badge>
              ))}
            </div>
            {approval.decisionReason ? (
              <p className="mt-3 rounded-md bg-muted p-3 text-xs text-muted-foreground">{approval.decisionReason}</p>
            ) : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Fact({
  icon,
  label,
  value,
}: Readonly<{
  icon?: ReactNode;
  label: string;
  value: string;
}>): JSX.Element {
  return (
    <div className="rounded-md bg-muted px-3 py-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 truncate font-medium text-foreground">{value}</div>
    </div>
  );
}
