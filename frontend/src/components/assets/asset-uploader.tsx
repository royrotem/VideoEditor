"use client";

import { useRef, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, assetsApi } from "@/lib/api";

/**
 * File picker + upload trigger.
 *
 * The backend runs ``ffprobe`` (and the Vision Analyzer if wired)
 * inline, so a single upload may take a few seconds. The button is
 * locked into a "loading" state for the duration; an alert explains
 * any error returned by the backend.
 */
export function AssetUploader({
  projectId,
  onUploaded,
}: {
  projectId: string;
  onUploaded: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      await assetsApi.upload(projectId, file);
      onUploaded();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "שגיאה בהעלאת הקובץ",
      );
    } finally {
      setUploading(false);
      // Reset so picking the same file again triggers `change`.
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept="video/*,audio/*,image/*"
        onChange={handleChange}
        className="hidden"
        data-testid="asset-file-input"
      />
      <Button
        type="button"
        variant="secondary"
        loading={uploading}
        onClick={() => inputRef.current?.click()}
      >
        {uploading ? "מעלה ומנתח…" : "העלאת קובץ"}
      </Button>
      <p className="text-xs text-neutral-500">
        וידאו, אודיו או תמונה. הניתוח (משך, רזולוציה, סיכום ויזואלי) מתבצע
        אוטומטית מיד אחרי ההעלאה.
      </p>
      {error && <Alert>{error}</Alert>}
    </div>
  );
}
