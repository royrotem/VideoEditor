"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { ApiError, renderApi } from "@/lib/api";

/**
 * HTML5 video player for a finished render.
 *
 * Asks the backend for a fresh presigned URL when the job changes,
 * and shows a loading / error state in between. Re-mounting on
 * jobId change is intentional - the new URL has its own playback
 * position and we do not want the old <video> element's state
 * leaking across.
 */
export function RenderPlayer({ jobId }: { jobId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setUrl(null);

    renderApi
      .outputUrl(jobId, 3600, controller.signal)
      .then((response) => setUrl(response.url))
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "שגיאה בקבלת קישור לצפייה",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [jobId]);

  if (loading) {
    return <p className="text-neutral-400">מחפש קישור צפייה…</p>;
  }
  if (error) return <Alert>{error}</Alert>;
  if (!url) return null;

  return (
    <video
      key={url}
      controls
      preload="metadata"
      className="aspect-video w-full rounded-lg border border-neutral-800 bg-black"
      src={url}
    />
  );
}
