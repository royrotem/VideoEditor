"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, projectsApi } from "@/lib/api";

/**
 * Inline form that creates a new project and notifies the parent on
 * success so it can refresh its list.
 *
 * Validation is intentionally minimal: the backend rejects empty
 * names with a 422; we just disable the submit button until at
 * least one non-whitespace character is typed.
 */
export function NewProjectForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmedName = name.trim();
  const trimmedDescription = description.trim();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmedName) return;
    setSubmitting(true);
    setError(null);
    try {
      await projectsApi.create({
        name: trimmedName,
        description: trimmedDescription || null,
      });
      setName("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "שגיאה לא צפויה ביצירת הפרויקט",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-900/40 p-4"
    >
      <h2 className="text-lg font-semibold">פרויקט חדש</h2>

      <label className="block space-y-1">
        <span className="text-sm text-neutral-300">שם</span>
        <input
          className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 outline-none focus:border-neutral-600"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="למשל: סרטון חתונה — קאט ראשון"
          required
          maxLength={255}
        />
      </label>

      <label className="block space-y-1">
        <span className="text-sm text-neutral-300">תיאור (אופציונלי)</span>
        <textarea
          className="min-h-[80px] w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 outline-none focus:border-neutral-600"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="כמה משפטים על הסרטון שאתם רוצים לבנות"
          maxLength={4096}
        />
      </label>

      {error && <Alert>{error}</Alert>}

      <Button type="submit" loading={submitting} disabled={!trimmedName}>
        {submitting ? "יוצר…" : "צור פרויקט"}
      </Button>
    </form>
  );
}
