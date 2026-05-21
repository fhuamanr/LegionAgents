import type { ReactNode } from "react";
import { GitBranch, GitPullRequest } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { PullRequestSummary } from "@/lib/types";

export function PrSummaryPanel({ pullRequest }: Readonly<{ pullRequest: PullRequestSummary }>): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>PR Visualization</CardTitle>
            <CardDescription>GitLab-ready merge request draft context</CardDescription>
          </div>
          <Badge variant={pullRequest.status === "merged" ? "success" : "default"}>{pullRequest.status}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border bg-background p-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <GitPullRequest className="h-4 w-4 text-primary" aria-hidden="true" />
            {pullRequest.title}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{pullRequest.summary}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Fact icon={<GitBranch className="h-4 w-4" aria-hidden="true" />} label="Branch" value={pullRequest.branch} />
            <Fact label="Target" value={pullRequest.target} />
            <Fact label="Changed files" value={String(pullRequest.changedFiles)} />
          </div>
        </div>
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
    <div className="rounded-md bg-muted p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 truncate text-sm font-medium">{value}</div>
    </div>
  );
}
