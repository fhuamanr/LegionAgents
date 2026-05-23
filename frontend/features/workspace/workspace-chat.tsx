"use client";

import { useMemo, useRef, useState } from "react";
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
  const [items, setItems] = useState<readonly WorkspaceConversationSummary[]>(conversations);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(conversations.length ? null : "Create a conversation to start using the workspace.");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const conversation = useMemo(() => items.find((item) => item.id === selectedId) ?? items[0], [items, selectedId]);
  const attachmentIds = conversation?.attachments.map((attachment) => attachment.id) ?? [];

  return (
    <div className="grid gap-6 xl:grid-cols-[20rem_1fr_22rem]">
      <Card>
        <CardHeader>
          <CardTitle>Conversations</CardTitle>
          <CardDescription>Persisted workspace threads</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button variant="outline" className="w-full justify-start" disabled={busy} onClick={() => void createConversation()}>
            <Send className="h-4 w-4" aria-hidden="true" />
            New conversation
          </Button>
          {items.map((item) => (
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
            {!conversation ? <div className="text-sm text-muted-foreground">No conversation yet. Create one, upload context, then send a request.</div> : null}
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
          {notice ? <p className="mt-3 text-xs text-muted-foreground">{notice}</p> : null}
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask the workspace to ingest files, analyze a repo, or trigger a workflow..."
              className="min-h-20 resize-none rounded-md border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <Button variant="outline" className="h-20" onClick={() => void sendMessage(true)} disabled={busy || !draft.trim()}>
              <Play className="h-4 w-4" aria-hidden="true" />
              Workflow
            </Button>
            <Button className="h-20" onClick={() => void sendMessage(false)} disabled={busy || !draft.trim()}>
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
            <input ref={fileInputRef} type="file" className="hidden" multiple accept=".md,.txt,.pdf,.docx,text/markdown,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => void uploadFiles(event.currentTarget.files)} />
            <UploadAction icon={<FileUp className="h-4 w-4" />} label="PDF / DOCX" onClick={() => fileInputRef.current?.click()} disabled={busy || !conversation} />
            <UploadAction icon={<UploadCloud className="h-4 w-4" />} label="Markdown / Text" onClick={() => fileInputRef.current?.click()} disabled={busy || !conversation} />
            <UploadAction icon={<Link2 className="h-4 w-4" />} label="URL ingestion" onClick={() => void addReference("url")} disabled={busy || !conversation} />
            <UploadAction icon={<GitBranch className="h-4 w-4" />} label="Git / repo path" onClick={() => void addReference("git_repository")} disabled={busy || !conversation} />
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

  async function createConversation(): Promise<WorkspaceConversationSummary | null> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      setNotice("NEXT_PUBLIC_API_BASE_URL is not configured.");
      return null;
    }
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/workspace/chat/conversations`, {
        method: "POST",
        headers: {"Content-Type": "application/json", Accept: "application/json"},
        body: JSON.stringify({title: "MVP delivery workspace", created_by: "workspace-user"}),
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      const payload = await response.json() as { conversation: Record<string, unknown> };
      const created = normalizeConversation(payload.conversation);
      setItems((current) => [created, ...current]);
      setSelectedId(created.id);
      setNotice("Conversation created.");
      return created;
    } catch (error) {
      setNotice(`Could not create conversation: ${error instanceof Error ? error.message : "unknown error"}`);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(triggerWorkflow: boolean): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    const active = conversation ?? await ensureConversation();
    if (!apiBaseUrl || !active) {
      setNotice("Create a conversation and configure NEXT_PUBLIC_API_BASE_URL first.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`${apiBaseUrl}/workspace/chat/conversations/${active.id}/messages`, {
        method: "POST",
        headers: {"Content-Type": "application/json", Accept: "application/json"},
        body: JSON.stringify({
          content: draft,
          attachment_ids: attachmentIds,
          trigger_workflow: triggerWorkflow,
        }),
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      setDraft("");
      await refreshConversation(active.id);
      setNotice(triggerWorkflow ? "Workflow request sent. Check executions and live logs for progress." : "Message sent.");
    } catch (error) {
      setNotice(`Send failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function uploadFiles(files: FileList | null): Promise<void> {
    if (!files?.length || !conversation) {
      return;
    }
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      setNotice("NEXT_PUBLIC_API_BASE_URL is not configured.");
      return;
    }
    setBusy(true);
    try {
      for (const file of Array.from(files)) {
        const content = await readFileForAttachment(file);
        const response = await fetch(`${apiBaseUrl}/workspace/chat/conversations/${conversation.id}/attachments`, {
          method: "POST",
          headers: {"Content-Type": "application/json", Accept: "application/json"},
          body: JSON.stringify({
            kind: attachmentKind(file.name),
            name: file.name,
            content,
            content_type: file.type || "application/octet-stream",
          }),
        });
        if (!response.ok) {
          throw new Error(`${response.status} ${response.statusText}`);
        }
      }
      await refreshConversation(conversation.id);
      setNotice(`${files.length} file(s) attached.`);
    } catch (error) {
      setNotice(`Upload failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function addReference(kind: "url" | "git_repository"): Promise<void> {
    if (!conversation) {
      return;
    }
    const value = window.prompt(kind === "url" ? "Paste URL" : "Paste Git repository URL or local repository path");
    if (!value) {
      return;
    }
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      setNotice("NEXT_PUBLIC_API_BASE_URL is not configured.");
      return;
    }
    setBusy(true);
    try {
      const isPath = kind === "git_repository" && !value.startsWith("http") && !value.endsWith(".git");
      const response = await fetch(`${apiBaseUrl}/workspace/chat/conversations/${conversation.id}/attachments`, {
        method: "POST",
        headers: {"Content-Type": "application/json", Accept: "application/json"},
        body: JSON.stringify({
          kind: isPath ? "repository_path" : kind,
          name: value.split(/[\\/]/).pop() || value,
          uri: isPath ? undefined : value,
          path: isPath ? value : undefined,
        }),
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      await refreshConversation(conversation.id);
      setNotice("Reference attached.");
    } catch (error) {
      setNotice(`Reference failed: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function ensureConversation(): Promise<WorkspaceConversationSummary | null> {
    if (conversation) {
      return conversation;
    }
    return await createConversation();
  }

  async function refreshConversation(conversationId: string): Promise<void> {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      return;
    }
    const response = await fetch(`${apiBaseUrl}/workspace/chat/conversations/${conversationId}`, {headers: {Accept: "application/json"}});
    if (!response.ok) {
      return;
    }
    const payload = await response.json() as { conversation: Record<string, unknown> };
    const updated = normalizeConversation(payload.conversation);
    setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
  }
}

function UploadAction({
  icon,
  label,
  onClick,
  disabled,
}: Readonly<{
  icon: ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}>): JSX.Element {
  return (
    <Button variant="outline" className="w-full justify-start" onClick={onClick} disabled={disabled}>
      {icon}
      {label}
    </Button>
  );
}

function attachmentKind(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".pdf")) return "pdf";
  if (lower.endsWith(".docx")) return "docx";
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "markdown";
  return "text";
}

async function readFileForAttachment(file: File): Promise<string> {
  if (file.type.startsWith("text/") || /\.(md|markdown|txt)$/i.test(file.name)) {
    return await file.text();
  }
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read file."));
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.readAsDataURL(file);
  });
}

function normalizeConversation(item: Record<string, unknown>): WorkspaceConversationSummary {
  const messages = Array.isArray(item.messages) ? item.messages as Record<string, unknown>[] : [];
  const attachments = Array.isArray(item.attachments) ? item.attachments as Record<string, unknown>[] : [];
  return {
    id: String(item.id),
    title: String(item.title),
    updatedAt: String(item.updated_at ?? item.updatedAt ?? ""),
    messages: messages.map((message) => ({
      id: String(message.id),
      role: String(message.role) as WorkspaceConversationSummary["messages"][number]["role"],
      content: String(message.content ?? ""),
      attachmentIds: Array.isArray(message.attachment_ids) ? message.attachment_ids.map(String) : [],
      workflowId: message.workflow_id ? String(message.workflow_id) : undefined,
      createdAt: String(message.created_at ?? ""),
    })),
    attachments: attachments.map((attachment) => ({
      id: String(attachment.id),
      kind: String(attachment.kind) as WorkspaceConversationSummary["attachments"][number]["kind"],
      name: String(attachment.name),
      uri: attachment.uri ? String(attachment.uri) : undefined,
      path: attachment.path ? String(attachment.path) : undefined,
      sizeBytes: Number(attachment.size_bytes ?? 0),
    })),
  };
}
