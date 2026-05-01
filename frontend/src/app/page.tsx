"use client";

import { useCallback, useEffect, useState } from "react";

import { NewProjectForm } from "@/components/projects/new-project-form";
import { ProjectList } from "@/components/projects/project-list";
import { Alert } from "@/components/ui/alert";
import { ApiError, projectsApi } from "@/lib/api";
import type { Project } from "@/lib/types";

/**
 * Home page.
 *
 * Lists the user's projects and exposes a "new project" form. After a
 * successful create the form clears and the list refreshes.
 *
 * Implemented as a client component because the data is per-user and
 * we want immediate post-mutation feedback. A future authenticated
 * server-component variant could pre-render the list on the server.
 */
export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProjects(await projectsApi.list());
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "שגיאה לא צפויה בטעינת הפרויקטים",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 px-6 py-12">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">עורך וידאו AI</h1>
        <p className="text-neutral-300">
          העלו את הקבצים, שוחחו עם הסוכן בעברית, וקבלו סרטון ערוך לפי
          התיאור שלכם.
        </p>
      </header>

      <NewProjectForm onCreated={refresh} />

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold">הפרויקטים שלי</h2>
          {!loading && (
            <span className="text-xs text-neutral-500">
              {projects.length} פרויקטים
            </span>
          )}
        </div>

        {loading && <p className="text-neutral-400">טוען…</p>}
        {error && <Alert>{error}</Alert>}
        {!loading && !error && <ProjectList projects={projects} />}
      </section>
    </main>
  );
}
