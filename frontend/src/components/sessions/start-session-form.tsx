"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, sessionsApi } from "@/lib/api";

/**
 * Inline form that opens a new chat session for a project. On
 * success the user is taken straight to the chat page so the
 * Director's first reply is the first thing they see.
 */
export function StartSessionForm({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [brief, setBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = brief.trim();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmed) return;
    setSubmitting(true);
    setError(null);
    try {
      const { session } = await sessionsApi.start(projectId, trimmed);
      router.push(`/projects/${projectId}/sessions/${session.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "שגיאה בפתיחת השיחה",
      );
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-900/40 p-4"
    >
      <h2 className="text-lg font-semibold">פתיחת שיחה חדשה</h2>
      <label className="block space-y-1">
        <span className="text-sm text-neutral-300">תארו את הסרטון שאתם רוצים</span>
        <textarea
          className="min-h-[100px] w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 outline-none focus:border-neutral-600"
          value={brief}
          onChange={(event) => setBrief(event.target.value)}
          placeholder="למשל: סרטון קצר ואנרגטי מהחתונה של אחותי, 30 שניות, עם פופ עברי"
          required
          maxLength={8192}
        />
      </label>
      {error && <Alert>{error}</Alert>}
      <Button type="submit" loading={submitting} disabled={!trimmed}>
        {submitting ? "פותח שיחה…" : "פתח שיחה"}
      </Button>
      <p className="text-xs text-neutral-500">
        הבמאי יענה בעברית, יציע מספר כיוונים, ויסיים את השיחה כשנגיע
        להחלטה משותפת.
      </p>
    </form>
  );
}
