"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { AssetList } from "@/components/assets/asset-list";
import { AssetUploader } from "@/components/assets/asset-uploader";
import { Alert } from "@/components/ui/alert";
import { ApiError, assetsApi, projectsApi } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Asset, Project } from "@/lib/types";

type Params = Promise<{ id: string }>;

/**
 * Project detail page.
 *
 * Shows the project's metadata and its assets, with an inline
 * uploader. The assets list refreshes automatically after a
 * successful upload so the new row (already analysed) appears with
 * the correct status badge.
 *
 * Next.js 15 made dynamic-route ``params`` async; we unwrap it with
 * `use()` to keep the component a client component.
 */
export default function ProjectPage({ params }: { params: Params }) {
  // React 19's ``use()`` is the canonical way to read an async ``params``
  // promise inside a client component.
  const { id } = use(params);

  const [project, setProject] = useState<Project | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [fetchedProject, fetchedAssets] = await Promise.all([
        projectsApi.get(id),
        assetsApi.list(id),
      ]);
      setProject(fetchedProject);
      setAssets(fetchedAssets);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "שגיאה לא צפויה בטעינת הפרויקט",
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
          href="/"
          className="text-neutral-400 transition-colors hover:text-neutral-200"
        >
          ← חזרה לרשימת הפרויקטים
        </Link>
      </nav>

      {loading && <p className="text-neutral-400">טוען…</p>}
      {error && <Alert>{error}</Alert>}

      {project && (
        <header className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
          {project.description && (
            <p className="text-neutral-300">{project.description}</p>
          )}
          <p className="text-xs text-neutral-500">
            נוצר ב‑{formatDateTime(project.created_at)}
          </p>
        </header>
      )}

      {project && (
        <>
          <section className="space-y-4 rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
            <h2 className="text-lg font-semibold">קבצים</h2>
            <AssetUploader projectId={project.id} onUploaded={refresh} />
          </section>

          <section className="space-y-3">
            <div className="flex items-baseline justify-between">
              <h2 className="text-xl font-semibold">קבצים בפרויקט</h2>
              <span className="text-xs text-neutral-500">
                {assets.length} קבצים
              </span>
            </div>
            <AssetList assets={assets} />
          </section>
        </>
      )}
    </main>
  );
}
