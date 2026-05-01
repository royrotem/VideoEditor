/**
 * Small coloured pill that renders a status enum (asset / job /
 * session) plus its Hebrew label. Centralised here so a colour
 * scheme tweak touches one file.
 */

import { cn } from "@/lib/cn";

type StatusKind = "neutral" | "info" | "success" | "warning" | "danger";

type StatusBadgeProps = {
  kind: StatusKind;
  label: string;
  className?: string;
};

const KIND_STYLES: Record<StatusKind, string> = {
  neutral: "bg-neutral-800 text-neutral-300 ring-neutral-700",
  info: "bg-blue-950/60 text-blue-300 ring-blue-900",
  success: "bg-emerald-950/60 text-emerald-300 ring-emerald-900",
  warning: "bg-amber-950/60 text-amber-300 ring-amber-900",
  danger: "bg-red-950/60 text-red-300 ring-red-900",
};

export function StatusBadge({ kind, label, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        KIND_STYLES[kind],
        className,
      )}
    >
      {label}
    </span>
  );
}

const ASSET_STATUS_LABELS = {
  uploaded: { kind: "info" as const, label: "הועלה" },
  analyzing: { kind: "info" as const, label: "בניתוח…" },
  ready: { kind: "success" as const, label: "מוכן" },
  failed: { kind: "danger" as const, label: "נכשל" },
};

const JOB_STATUS_LABELS = {
  pending: { kind: "neutral" as const, label: "ממתין" },
  running: { kind: "info" as const, label: "בעיבוד…" },
  succeeded: { kind: "success" as const, label: "הושלם" },
  failed: { kind: "danger" as const, label: "נכשל" },
  cancelled: { kind: "warning" as const, label: "בוטל" },
};

export function AssetStatusBadge({
  status,
}: {
  status: keyof typeof ASSET_STATUS_LABELS;
}) {
  const cfg = ASSET_STATUS_LABELS[status];
  return <StatusBadge kind={cfg.kind} label={cfg.label} />;
}

export function JobStatusBadge({
  status,
}: {
  status: keyof typeof JOB_STATUS_LABELS;
}) {
  const cfg = JOB_STATUS_LABELS[status];
  return <StatusBadge kind={cfg.kind} label={cfg.label} />;
}
