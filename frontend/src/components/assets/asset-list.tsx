"use client";

import { AssetStatusBadge } from "@/components/ui/status-badge";
import { formatBytes, formatDateTime } from "@/lib/format";
import type { Asset } from "@/lib/types";

/**
 * Renders the project's assets as a table-like list with name,
 * status badge, size, and upload time. Empty state matches the
 * project list.
 */
export function AssetList({ assets }: { assets: Asset[] }) {
  if (assets.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-neutral-800 px-4 py-6 text-center text-sm text-neutral-400">
        עדיין אין קבצים בפרויקט. העלו את הראשון למעלה.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
      {assets.map((asset) => (
        <li
          key={asset.id}
          className="flex items-center justify-between gap-3 px-4 py-3"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium" title={asset.filename}>
              {asset.filename}
            </p>
            <p className="text-xs text-neutral-500">
              {formatBytes(asset.size_bytes)} • הועלה ב‑
              {formatDateTime(asset.created_at)}
            </p>
          </div>
          <AssetStatusBadge status={asset.status} />
        </li>
      ))}
    </ul>
  );
}
