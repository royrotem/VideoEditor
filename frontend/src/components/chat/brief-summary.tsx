import type { BriefPlan } from "@/lib/types";

/**
 * Read-only render of a :class:`BriefPlan`. Shown after the user
 * triggers extract-brief, before the planner runs.
 */
export function BriefSummary({ brief }: { brief: BriefPlan }) {
  const PACING_LABEL: Record<BriefPlan["pacing"], string> = {
    slow: "איטי",
    medium: "בינוני",
    fast: "מהיר",
  };

  return (
    <div className="space-y-3 rounded-lg border border-emerald-900 bg-emerald-950/20 p-4">
      <div>
        <h3 className="text-base font-semibold">{brief.title}</h3>
        <p className="mt-1 text-sm text-neutral-200 whitespace-pre-wrap">
          {brief.intent}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="text-xs text-neutral-500">משך יעד</dt>
          <dd>{brief.target_duration_seconds.toFixed(0)}s</dd>
        </div>
        <div>
          <dt className="text-xs text-neutral-500">קצב</dt>
          <dd>{PACING_LABEL[brief.pacing]}</dd>
        </div>
        {brief.music_direction && (
          <div className="col-span-2">
            <dt className="text-xs text-neutral-500">כיוון מוזיקלי</dt>
            <dd>{brief.music_direction}</dd>
          </div>
        )}
        {brief.style_notes.length > 0 && (
          <div className="col-span-2">
            <dt className="text-xs text-neutral-500">הערות סגנון</dt>
            <dd className="flex flex-wrap gap-1">
              {brief.style_notes.map((note) => (
                <span
                  key={note}
                  className="inline-flex rounded-full border border-neutral-700 px-2 py-0.5 text-xs text-neutral-200"
                >
                  {note}
                </span>
              ))}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}
