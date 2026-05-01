/**
 * Tailwind-aware class-name merging.
 *
 * `clsx` handles conditional classes (`{ active: true }`); the
 * `tailwind-merge` pass collapses duplicates so later utilities win
 * (e.g. `cn("p-2", isCompact && "p-1")` resolves to a single padding).
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...values: ClassValue[]): string {
  return twMerge(clsx(values));
}
