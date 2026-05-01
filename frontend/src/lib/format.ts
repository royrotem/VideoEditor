/**
 * Formatting helpers for Hebrew RTL UI.
 *
 * Intentionally tiny and pure - no React, no DOM. Components import
 * these so date / size strings are consistent across pages.
 */

const DATE_FORMATTER = new Intl.DateTimeFormat("he-IL", {
  dateStyle: "short",
  timeStyle: "short",
});

/** ISO-8601 timestamp → Hebrew-locale short date+time. */
export function formatDateTime(iso: string): string {
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return "";
  return DATE_FORMATTER.format(value);
}

/** Bytes → "12.3 MB" (Hebrew labels use the same SI prefixes). */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}
