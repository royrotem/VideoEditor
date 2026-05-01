"use client";

import { JobStatusBadge } from "@/components/ui/status-badge";
import { formatDateTime } from "@/lib/format";
import type { RenderJob } from "@/lib/types";

/**
 * Pure presentational list of render jobs. Selecting a row tells the
 * parent which job to show in the player; the parent decides what
 * "selected" looks like.
 */
export function RenderList({
  jobs,
  selectedId,
  onSelect,
}: {
  jobs: RenderJob[];
  selectedId: string | null;
  onSelect: (job: RenderJob) => void;
}) {
  if (jobs.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-neutral-800 px-4 py-6 text-center text-sm text-neutral-400">
        עוד אין רנדרים בפרויקט. הריצו עריכה משיחה קיימת.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
      {jobs.map((job) => {
        const isSelected = job.id === selectedId;
        return (
          <li key={job.id}>
            <button
              type="button"
              onClick={() => onSelect(job)}
              className={
                "flex w-full items-center justify-between gap-3 px-4 py-3 text-right transition-colors " +
                (isSelected ? "bg-neutral-900" : "hover:bg-neutral-900/60")
              }
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  רנדר — {formatDateTime(job.created_at)}
                </p>
                <p className="text-xs text-neutral-500" dir="ltr">
                  {job.id.slice(0, 8)}
                </p>
                {job.error_message && (
                  <p className="mt-1 text-xs text-red-300 line-clamp-2">
                    {job.error_message}
                  </p>
                )}
              </div>
              <JobStatusBadge status={job.status} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
