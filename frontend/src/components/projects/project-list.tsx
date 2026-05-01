"use client";

import Link from "next/link";

import type { Project } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

/**
 * Renders an array of projects as a vertical list. Each item is a
 * link into the project detail page; an empty array shows a hint.
 *
 * Pure presentation: the parent owns fetching and refresh.
 */
export function ProjectList({ projects }: { projects: Project[] }) {
  if (projects.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-neutral-800 px-4 py-6 text-center text-sm text-neutral-400">
        עדיין אין פרויקטים. צרו את הראשון למעלה.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
      {projects.map((project) => (
        <li key={project.id}>
          <Link
            href={`/projects/${project.id}`}
            className="flex flex-col gap-1 px-4 py-3 transition-colors hover:bg-neutral-900"
          >
            <span className="font-medium">{project.name}</span>
            {project.description && (
              <span className="text-sm text-neutral-400 line-clamp-2">
                {project.description}
              </span>
            )}
            <span className="text-xs text-neutral-500">
              נוצר ב‑{formatDateTime(project.created_at)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
