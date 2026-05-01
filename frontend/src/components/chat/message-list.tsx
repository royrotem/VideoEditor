"use client";

import { useEffect, useRef } from "react";

import { MessageBubble } from "@/components/chat/message-bubble";
import type { Message } from "@/lib/types";

/**
 * Scrollable list of message bubbles. Auto-scrolls to the bottom
 * whenever the list grows so a new turn is always visible.
 *
 * The very first user message in a session is the synthetic
 * BRIEF + ASSET_FACTS payload the backend hands the Creative
 * Director. It is shown to the LLM, not to the user, so we filter
 * it out here.
 */
export function MessageList({ messages }: { messages: Message[] }) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const visible = messages.filter(
    (m, idx) => !(idx === 0 && m.role === "user" && m.content.startsWith("BRIEF:")),
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [visible.length]);

  if (visible.length === 0) {
    return (
      <p className="text-center text-sm text-neutral-400">
        טוען את ההודעה הראשונה…
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {visible.map((message) => (
        <li key={message.id}>
          <MessageBubble message={message} />
        </li>
      ))}
      <div ref={bottomRef} />
    </ul>
  );
}
