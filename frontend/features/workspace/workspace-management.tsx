"use client";

import { useMemo, useState } from "react";
import { Boxes, Database, FolderKanban, GitBranch, HardDrive, ShieldCheck, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { WorkspaceIsolationSummary, WorkspaceProjectSummary, WorkspaceSummary } from "@/lib/types";

export function WorkspaceManagement({
  workspaces,
  projects,
  isolation,
}: Readonly<{
  workspaces: readonly WorkspaceSummary[];
  projects: readonly WorkspaceProjectSummary[];
  isolation: readonly WorkspaceIsolationSummary[];
}>): JSX.Element {
  const [selectedId, setSelectedId] = useState(workspaces[0]?.id ?? "");
  const workspace = workspaces.find((item) => item.id === selectedId) ?? workspaces[0];
  const workspaceProjects = useMemo(
    () => projects.filter((project) => project.workspaceId === workspace?.id),
    [projects, workspace?.id],
  );
  const currentIsolation = isolation.find((item) => item.workspaceId === workspace?.id);

  return (
    <div className="grid gap-6 xl:grid-cols-[22rem_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Workspaces</CardTitle>
          <CardDescription>Tenant-aware project boundaries</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {workspaces.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedId(item.id)}
              className="w-full rounded-md border bg-background p-3 text-left transition-colors hover:bg-muted"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{item.name}</span>
                <Badge variant="default">{item.tenantId}</Badge>
              </div>
              <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant="muted">{item.projectIds.length} projects</Badge>
                <Badge variant="success">{item.agents.filter((agent) => agent.enabled).length} agents</Badge>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">{formatDateTime(item.updatedAt)}</div>
            </button>
          ))}
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>{workspace?.name ?? "Workspace"}</CardTitle>
                <CardDescription>{workspace?.description ?? "Workspace configuration and isolation"}</CardDescription>
              </div>
              <Badge variant="success">isolated</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Metric icon={<FolderKanban className="h-4 w-4" />} label="Projects" value={String(currentIsolation?.projectCount ?? 0)} />
              <Metric icon={<GitBranch className="h-4 w-4" />} label="Repositories" value={String(currentIsolation?.repositoryCount ?? 0)} />
              <Metric icon={<Users className="h-4 w-4" />} label="Members" value={String(workspace?.members.length ?? 0)} />
              <Metric icon={<Boxes className="h-4 w-4" />} label="Agents" value={String(currentIsolation?.enabledAgents.length ?? 0)} />
            </div>
            <div className="mt-4 grid gap-3 xl:grid-cols-3">
              <IsolationLine icon={<HardDrive className="h-4 w-4" />} label="Storage" value={workspace?.configuration.storageRoot ?? ""} />
              <IsolationLine icon={<Database className="h-4 w-4" />} label="Memory" value={workspace?.configuration.memoryNamespace ?? ""} />
              <IsolationLine icon={<ShieldCheck className="h-4 w-4" />} label="Governance" value={workspace?.configuration.governanceNamespace ?? ""} />
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Projects and Repositories</CardTitle>
              <CardDescription>Multiple repositories scoped to this workspace</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {workspaceProjects.map((project) => (
                <div key={project.id} className="rounded-md border bg-background p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium">{project.name}</div>
                      <p className="mt-1 text-xs text-muted-foreground">{project.description}</p>
                    </div>
                    <Badge variant="muted">{project.repositories.length} repos</Badge>
                  </div>
                  <div className="mt-3 space-y-2">
                    {project.repositories.map((repository) => (
                      <div key={repository.id} className="rounded-md bg-muted p-3 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{repository.name}</span>
                          <Badge variant="default">{repository.provider}</Badge>
                        </div>
                        <div className="mt-1 truncate text-muted-foreground">{repository.uri ?? repository.path}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Workspace Agents</CardTitle>
              <CardDescription>Agent availability, prompt profiles, and retry policy</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {workspace?.agents.map((agent) => (
                <div key={agent.agentName} className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-4">
                  <div>
                    <div className="text-sm font-medium uppercase">{agent.agentName}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      retries {agent.maxRetries}
                      {agent.promptProfile ? ` / prompt ${agent.promptProfile}` : ""}
                      {agent.governanceProfile ? ` / governance ${agent.governanceProfile}` : ""}
                    </div>
                  </div>
                  <Badge variant={agent.enabled ? "success" : "muted"}>{agent.enabled ? "enabled" : "disabled"}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Permissions</CardTitle>
            <CardDescription>Workspace roles and explicit capabilities</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 xl:grid-cols-2">
            {workspace?.members.map((member) => (
              <div key={member.userId} className="rounded-md border bg-background p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium">{member.displayName}</div>
                  <Badge variant={member.role === "owner" ? "success" : "default"}>{member.role}</Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {member.permissions.map((permission) => (
                    <Badge key={permission} variant="muted">{permission}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Metric({ icon, label, value }: Readonly<{ icon: JSX.Element; label: string; value: string }>): JSX.Element {
  return (
    <div className="rounded-md border bg-background p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">{icon}{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function IsolationLine({ icon, label, value }: Readonly<{ icon: JSX.Element; label: string; value: string }>): JSX.Element {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">{icon}{label}</div>
      <div className="mt-2 break-words font-mono text-xs">{value}</div>
    </div>
  );
}
