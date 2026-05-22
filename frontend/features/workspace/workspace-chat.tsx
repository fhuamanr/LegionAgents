"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { FileUp, GitBranch, Link2, Play, Send, UploadCloud } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { WorkspaceConversationSummary } from "@/lib/types";

export function WorkspaceChat({
  conversations,
}: Readonly<{
  conversations: readonly WorkspaceConversationSummary[];
}>): JSX.Element {
  const [selectedId, setSelectedId] = useState(conversations[0]?.id ?? "");
  const [draft, setDraft] = useState("");
  const conversation = conversations.find((item) => item.id === selectedId) ?? conversations[0];

  return (
    <div className="grid gap-6 xl:grid-cols-[20rem_1fr_22rem]">
      <Card>
        <CardHeader>
          <CardTitle>Conversations</CardTitle>
          <CardDescription>Persisted workspace threads</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {conversations.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedId(item.id)}
              className="w-full rounded-md border bg-background p-3 text-left hover:bg-muted"
            >
              <div className="text-sm font-medium">{item.title}</div>
              <div className="mt-2 text-xs text-muted-foreground">{formatDateTime(item.updatedAt)}</div>
              <div className="mt-2 flex gap-2">
                <Badge variant="muted">{item.messages.length} messages</Badge>
                <Badge variant="default">{item.attachments.length} inputs</Badge>
              </div>
            </button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>{conversation?.title ?? "AI Workspace Chat"}</CardTitle>
              <CardDescription>Trigger workflows from files, URLs, Git repositories, and local repository paths</CardDescription>
            </div>
            <Badge variant="success">stream-ready</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[34rem] space-y-3 overflow-auto rounded-md border bg-background p-4">
            {conversation?.messages.map((message) => (
              <div
                key={message.id}
                className={message.role === "user" ? "ml-auto max-w-[85%] rounded-md bg-primary/15 p-3" : "max-w-[85%] rounded-md bg-muted p-3"}
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <Badge variant={message.role === "workflow" ? "warning" : message.role === "assistant" ? "success" : "default"}>
                    {message.role}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{formatDateTime(message.createdAt)}</span>
                </div>
                <div className="whitespace-pre-wrap text-sm leading-6">{message.content}</div>
                {message.workflowId ? <div className="mt-2 text-xs text-primary">workflow {message.workflowId}</div> : null}
              </div>
            ))}
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask the workspace to ingest files, analyze a repo, or trigger a workflow..."
              className="min-h-20 resize-none rounded-md border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <Button variant="outline" className="h-20">
              <Play className="h-4 w-4" aria-hidden="true" />
              Workflow
            </Button>
            <Button className="h-20">
              <Send className="h-4 w-4" aria-hidden="true" />
              Send
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Workspace Inputs</CardTitle>
            <CardDescription>Multi-file uploads and external references</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <UploadAction icon={<FileUp className="h-4 w-4" />} label="PDF / DOCX" />
            <UploadAction icon={<UploadCloud className="h-4 w-4" />} label="Markdown / Text" />
            <UploadAction icon={<Link2 className="h-4 w-4" />} label="URL ingestion" />
            <UploadAction icon={<GitBranch className="h-4 w-4" />} label="Git / repo path" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Attached Context</CardTitle>
            <CardDescription>Inputs scoped to the active conversation</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {conversation?.attachments.map((attachment) => (
              <div key={attachment.id} className="rounded-md border bg-background p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate text-sm font-medium">{attachment.name}</div>
                  <Badge variant="muted">{attachment.kind}</Badge>
                </div>
                <div className="mt-2 truncate text-xs text-muted-foreground">{attachment.uri ?? attachment.path ?? `${attachment.sizeBytes} bytes`}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function UploadAction({
  icon,
  label,
}: Readonly<{
  icon: ReactNode;
  label: string;
}>): JSX.Element {
  return (
    <Button variant="outline" className="w-full justify-start">
      {icon}
      {label}
    </Button>
  );
}
