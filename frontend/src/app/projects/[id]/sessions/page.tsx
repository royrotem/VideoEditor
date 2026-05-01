"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { SessionList } from "@/components/sessions/session-list";
import { StartSessionForm } from "@/components/sessions/start-session-form";
import { Alert } from "@/components/ui/alert";
import { ApiError, sessionsApi } from "@/lib/api";
import type { Session } from "@/lib/types";

type Params = Promise<{ id: string }>;

export default function ProjectSessionsPage({ params }: { params: Params }) {
  const { id } = use(params);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSessions(await sessionsApi.list(id));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "שגיאה בטעינת השיחות",
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 px-6 py-12">
      <nav className="text-sm">
        <Link
          href={`/projects/${id}`}
          className="text-neutral-400 transition-colors hover:text-neutral-200"
        >
          ← חזרה לפרויקט
        </Link>
      </nav>

      <header>
        <h1 className="text-2xl font-bold tracking-tight">שיחות עריכה</h1>
        <p className="text-neutral-300">
          כל שיחה מסתיימת בתכנית עריכה שאפשר להפיק ממנה רנדר.
        </p>
      </header>

      <StartSessionForm projectId={id} />

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold">היסטוריה</h2>
          {!loading && (
            <span className="text-xs text-neutral-500">
              {sessions.length} שיחות
            </span>
          )}
        </div>
        {loading && <p className="text-neutral-400">טוען…</p>}
        {error && <Alert>{error}</Alert>}
        {!loading && !error && (
          <SessionList projectId={id} sessions={sessions} />
        )}
      </section>
    </main>
  );
}
