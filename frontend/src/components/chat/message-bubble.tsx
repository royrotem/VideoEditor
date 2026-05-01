import { cn } from "@/lib/cn";
import type { Message } from "@/lib/types";

/**
 * One chat turn. Styled by role: user turns are right-aligned blue,
 * agent turns left-aligned neutral. The Director's "סיכום:" closing
 * message gets a green tint so the user notices the convergence
 * even before the page surfaces a follow-up CTA.
 */
export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isApproval = message.content.trimStart().startsWith("סיכום:");

  return (
    <div
      className={cn(
        "flex w-full",
        isUser ? "justify-start" : "justify-end",
      )}
    >
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm",
          isUser && "bg-blue-950/60 text-blue-50 ring-1 ring-blue-900",
          !isUser && !isApproval &&
            "bg-neutral-900 text-neutral-100 ring-1 ring-neutral-800",
          isApproval &&
            "bg-emerald-950/60 text-emerald-50 ring-1 ring-emerald-900",
        )}
      >
        {message.content}
      </div>
    </div>
  );
}
