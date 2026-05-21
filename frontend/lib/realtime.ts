import type { ExecutionEvent } from "./types";

export interface ExecutionStream {
  close: () => void;
}

export function connectExecutionStream(
  workflowId: string,
  onEvent: (event: ExecutionEvent) => void,
  onError?: (error: Event) => void,
): ExecutionStream | null {
  const wsBaseUrl = process.env.NEXT_PUBLIC_WS_BASE_URL;

  if (!wsBaseUrl || typeof window === "undefined") {
    return null;
  }

  const socket = new WebSocket(`${wsBaseUrl}/workflows/${workflowId}/events`);

  socket.addEventListener("message", (message) => {
    onEvent(JSON.parse(message.data as string) as ExecutionEvent);
  });

  if (onError) {
    socket.addEventListener("error", onError);
  }

  return {
    close: () => socket.close(),
  };
}
