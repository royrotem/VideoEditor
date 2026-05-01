"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";

import { BriefSummary } from "@/components/chat/brief-summary";
import { MessageInput } from "@/components/chat/message-input";
import { MessageList } from "@/components/chat/message-list";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, planningApi, renderApi, sessionsApi } from "@/lib/api";
import type {
  AssistantReply,
  BriefPlan,
  EditDecisionList,
  Message,
} from "@/lib/types";

type Params = Promise<{ id: string; sid: string }>;

/**
 * Chat page.
 *
 * Drives the full chat → brief → plan → render flow on a single
 * screen. Each step exposes its result before the next button shows
 * up so the user always knows what they are about to commit to.
 */
export default function ChatPage({ params }: { params: Params }) {
  const { id: projectId, sid: sessionId } = use(params);
  const router = useRouter();

  const [messages, setMessages] = useState<Message[]>([]);
  const [converged, setConverged] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [brief, setBrief] = useState<BriefPlan | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);

  const [edl, setEdl] = useState<EditDecisionList | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);
  const [rendering, setRendering] = useState(false);

  const refreshMessages = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const fetched = await sessionsApi.messages(sessionId);
      setMessages(fetched);
      // Detect convergence retroactively in case the page is reloaded
      // after the Director already emitted a "סיכום:" turn.
      const last = [...fetched]
        .reverse()
        .find((m) => m.role === "agent");
      if (last && last.content.trimStart().startsWith("סיכום:")) {
        setConverged(true);
      }
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : "שגיאה בטעינת השיחה",
      );
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void refreshMessages();
  }, [refreshMessages]);

  function handleTurn(reply: AssistantReply) {
    setMessages((prev) => [...prev, reply.user_message, reply.assistant_message]);
    if (reply.converged) setConverged(true);
  }

  async function handleExtractBrief() {
    setExtracting(true);
    setBriefError(null);
    try {
      setBrief(await sessionsApi.extractBrief(sessionId));
    } catch (err) {
      setBriefError(
        err instanceof ApiError ? err.message : "שגיאה בגזירת ה-brief",
      );
    } finally {
      setExtracting(false);
    }
  }

  async function handlePlan() {
    if (!brief) return;
    setPlanning(true);
    setPlanError(null);
    try {
      setEdl(await planningApi.planEdit(projectId, brief));
    } catch (err) {
      setPlanError(
        err instanceof ApiError ? err.message : "שגיאה בתכנון העריכה",
      );
    } finally {
      setPlanning(false);
    }
  }

  async function handleSubmitRender() {
    if (!edl) return;
    setRendering(true);
    setPlanError(null);
    try {
      await renderApi.submit(projectId, edl, sessionId);
      router.push(`/projects/${projectId}/renders`);
    } catch (err) {
      setPlanError(
        err instanceof ApiError ? err.message : "שגיאה בשליחת הרנדר",
      );
      setRendering(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <nav className="text-sm">
        <Link
          href={`/projects/${projectId}/sessions`}
          className="text-neutral-400 transition-colors hover:text-neutral-200"
        >
          ← חזרה לרשימת השיחות
        </Link>
      </nav>

      <header>
        <h1 className="text-2xl font-bold tracking-tight">שיחה עם הבמאי</h1>
        <p className="text-sm text-neutral-400">
          הבמאי יציע 2-3 כיוונים בכל תור. כשמסכימים, הוא יסיים בהודעה
          שמתחילה ב-"סיכום:". אחר כך אפשר לגזור brief ולהפיק רנדר.
        </p>
      </header>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
        {loading ? (
          <p className="text-neutral-400">טוען את השיחה…</p>
        ) : loadError ? (
          <Alert>{loadError}</Alert>
        ) : (
          <MessageList messages={messages} />
        )}
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
        <MessageInput
          sessionId={sessionId}
          disabled={converged}
          onTurn={handleTurn}
        />
      </section>

      {converged && (
        <section className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
          <h2 className="text-lg font-semibold">השיחה הסתיימה — מה הלאה?</h2>
          {!brief && (
            <>
              <p className="text-sm text-neutral-300">
                הבמאי סיכם את הכיוון. הצעד הבא הוא לגזור את התוכנית
                לאובייקט מובנה (BriefPlan) שהמתכנן יוכל לעבוד מולו.
              </p>
              {briefError && <Alert>{briefError}</Alert>}
              <Button onClick={handleExtractBrief} loading={extracting}>
                {extracting ? "גוזר…" : "גזור brief"}
              </Button>
            </>
          )}

          {brief && (
            <>
              <BriefSummary brief={brief} />
              {!edl && (
                <>
                  {planError && <Alert>{planError}</Alert>}
                  <Button onClick={handlePlan} loading={planning}>
                    {planning ? "מתכנן עריכה…" : "תכנן עריכה (EDL)"}
                  </Button>
                </>
              )}
              {edl && (
                <>
                  <Alert tone="info">
                    תוכנית עריכה מוכנה. הקליקו על "הפק רנדר" כדי לבצע אותה.
                  </Alert>
                  {planError && <Alert>{planError}</Alert>}
                  <Button onClick={handleSubmitRender} loading={rendering}>
                    {rendering ? "מפיק…" : "הפק רנדר"}
                  </Button>
                </>
              )}
            </>
          )}
        </section>
      )}
    </main>
  );
}
