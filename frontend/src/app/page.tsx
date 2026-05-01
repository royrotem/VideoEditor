/**
 * Landing page (placeholder).
 *
 * Phase 1 only ships the shell of the app and a working RTL Hebrew
 * layout. The real upload / chat / editor screens land in later phases.
 */
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-4xl font-bold tracking-tight">עורך וידאו AI</h1>
      <p className="text-lg text-neutral-300">
        העלו את הקבצים, תארו את הסרטון שאתם רוצים, וצוות סוכני ה‑AI יבנה
        אותו עבורכם.
      </p>
      <p className="rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-2 text-sm text-neutral-400">
        בשלב הבנייה. בקרוב כאן יופיעו מסכי העלאה, שיחה ועריכה.
      </p>
    </main>
  );
}
