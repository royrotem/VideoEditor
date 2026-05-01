"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { RenderList } from "@/components/renders/render-list";
import { RenderPlayer } from "@/components/renders/render-player";
import { Alert } from "@/components/ui/alert";
import { ApiError, renderApi } from "@/lib/api";
import type { RenderJob } from "@/lib/types";

type Params = Promise<{ id: string }>;

const REFRESH_INTERVAL_MS = 4_000;

/**
 * Lists every render job for the project and lets the user click
 * one to play it.
 *
 * Polls every few seconds while at least one job is still running,
 * so the UI converges to "succeeded" without needing a WebSocket
 * (we will add one once render moves to a Celery worker).
 */
export default function ProjectRendersPage({ params }: { params: Params }) {
  const { id } = use(params);

  const [jobs, setJobs] = useState<RenderJob[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const fetched = await renderApi.list(id);
      setJobs(fetched);
      // Auto-select the most recent succeeded job for first-time visit.
      setSelectedId((current) => {
        if (current) return current;
        const succeeded = fetched.find((j) => j.status === "succeeded");
        return succeeded?.id ?? null;
      });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "שגיאה בטעינת הרנדרים",
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll while any job is in flight.
  useEffect(() => {
    const inFlight = jobs.some(
      (j) => j.status === "pending" || j.status === "running",
    );
    if (!inFlight) return;
    const handle = setInterval(() => {
      void refresh();
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(handle);
  }, [jobs, refresh]);

  const selectedJob = jobs.find((j) => j.id === selectedId) ?? null;

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <nav className="text-sm">
        <Link
          href={`/projects/${id}`}
          className="text-neutral-400 transition-colors hover:text-neutral-200"
        >
          ← חזרה לפרויקט
        </Link>
      </nav>

      <header>
        <h1 className="text-2xl font-bold tracking-tight">רנדרים</h1>
        <p className="text-sm text-neutral-400">
          כל רנדר שייצרתם נשמר כאן. בחרו אחד מהרשימה כדי לצפות.
        </p>
      </header>

      {error && <Alert>{error}</Alert>}
      {loading && <p className="text-neutral-400">טוען…</p>}

      {!loading && (
        <>
          <section className="space-y-2">
            <h2 className="text-lg font-semibold">היסטוריה</h2>
            <RenderList
              jobs={jobs}
              selectedId={selectedId}
              onSelect={(job) => setSelectedId(job.id)}
            />
          </section>

          {selectedJob && selectedJob.status === "succeeded" && (
            <section className="space-y-2">
              <h2 className="text-lg font-semibold">צפייה</h2>
              <RenderPlayer jobId={selectedJob.id} />
            </section>
          )}

          {selectedJob && selectedJob.status === "failed" && (
            <Alert>
              הרנדר נכשל: {selectedJob.error_message ?? "ללא פרטים"}
            </Alert>
          )}

          {selectedJob &&
            (selectedJob.status === "pending" ||
              selectedJob.status === "running") && (
              <Alert tone="info">
                הרנדר עוד פועל. הסטטוס יתעדכן אוטומטית.
              </Alert>
            )}
        </>
      )}
    </main>
  );
}
