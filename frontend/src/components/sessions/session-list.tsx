"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/ui/status-badge";
import { formatDateTime } from "@/lib/format";
import type { Session } from "@/lib/types";

const STATUS_LABEL = {
  active: { kind: "info" as const, label: "פעילה" },
  closed: { kind: "neutral" as const, label: "הסתיימה" },
};

/**
 * List of chat sessions for a project. Each row links to the chat
 * thread; closed sessions are still navigable so the user can read
 * the conversation that produced an existing render.
 */
export function SessionList({
  projectId,
  sessions,
}: {
  projectId: string;
  sessions: Session[];
}) {
  if (sessions.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-neutral-800 px-4 py-6 text-center text-sm text-neutral-400">
        עוד לא הייתה שיחה בפרויקט. פתחו את הראשונה למעלה.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
      {sessions.map((session) => {
        const cfg = STATUS_LABEL[session.status];
        return (
          <li key={session.id}>
            <Link
              href={`/projects/${projectId}/sessions/${session.id}`}
              className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-neutral-900"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  שיחה — {formatDateTime(session.created_at)}
                </p>
                <p className="text-xs text-neutral-500" dir="ltr">
                  {session.id.slice(0, 8)}
                </p>
              </div>
              <StatusBadge kind={cfg.kind} label={cfg.label} />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
