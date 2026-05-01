"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, sessionsApi } from "@/lib/api";
import type { AssistantReply } from "@/lib/types";

/**
 * Textarea + send button for one chat turn. Sends to the backend,
 * surfaces errors as an inline alert, and notifies the parent of
 * the resulting message pair so it can refresh the thread.
 *
 * Disabled when the session has converged (the parent passes the
 * flag through) so the user is nudged toward the "extract brief"
 * step instead of accidentally re-opening the conversation.
 */
export function MessageInput({
  sessionId,
  disabled = false,
  onTurn,
}: {
  sessionId: string;
  disabled?: boolean;
  onTurn: (reply: AssistantReply) => void;
}) {
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = content.trim();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmed) return;
    setSending(true);
    setError(null);
    try {
      const reply = await sessionsApi.send(sessionId, trimmed);
      onTurn(reply);
      setContent("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "שגיאה בשליחת ההודעה",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <form className="space-y-2" onSubmit={handleSubmit}>
      <textarea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder={
          disabled
            ? "השיחה הסתיימה. עברו ל'גזור brief' כדי להמשיך."
            : "כתבו תשובה לבמאי..."
        }
        disabled={disabled || sending}
        className="min-h-[80px] w-full resize-y rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm outline-none focus:border-neutral-600 disabled:cursor-not-allowed disabled:opacity-60"
        maxLength={8192}
        onKeyDown={(event) => {
          // Cmd/Ctrl-Enter sends without leaving the textarea.
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            (event.currentTarget.form as HTMLFormElement).requestSubmit();
          }
        }}
      />
      {error && <Alert>{error}</Alert>}
      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-500">
          Cmd/Ctrl + Enter לשליחה מהירה
        </span>
        <Button type="submit" loading={sending} disabled={disabled || !trimmed}>
          {sending ? "שולח…" : "שלח"}
        </Button>
      </div>
    </form>
  );
}
