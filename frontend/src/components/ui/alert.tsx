/**
 * Inline alert used for error / info banners.
 *
 * Visually consistent with the page background so it doesn't shout
 * for attention - errors are common in async flows.
 */

import { cn } from "@/lib/cn";

type AlertProps = {
  tone?: "error" | "info" | "warning";
  children: React.ReactNode;
  className?: string;
};

const TONE: Record<NonNullable<AlertProps["tone"]>, string> = {
  error: "border-red-900 bg-red-950/40 text-red-200",
  info: "border-blue-900 bg-blue-950/40 text-blue-200",
  warning: "border-amber-900 bg-amber-950/40 text-amber-200",
};

export function Alert({ tone = "error", children, className }: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-md border px-3 py-2 text-sm",
        TONE[tone],
        className,
      )}
    >
      {children}
    </div>
  );
}
