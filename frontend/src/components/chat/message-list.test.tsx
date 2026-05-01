import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MessageList } from "./message-list";

// JSDOM doesn't implement scrollIntoView; the auto-scroll effect just
// calls it, so a noop stub keeps the test clean.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe("MessageList", () => {
  it("hides the synthetic BRIEF + ASSET_FACTS opening user turn", () => {
    render(
      <MessageList
        messages={[
          {
            id: "m0",
            session_id: "s",
            role: "user",
            agent_name: null,
            content: "BRIEF:\nרוצה משהו קצר",
            created_at: "2026-04-01T10:00:00Z",
          },
          {
            id: "m1",
            session_id: "s",
            role: "agent",
            agent_name: "creative_director",
            content: "יש לי שתי הצעות",
            created_at: "2026-04-01T10:00:01Z",
          },
        ]}
      />,
    );

    expect(screen.queryByText(/BRIEF:/)).not.toBeInTheDocument();
    expect(screen.getByText("יש לי שתי הצעות")).toBeInTheDocument();
  });

  it("renders both user and agent turns when they are not synthetic", () => {
    render(
      <MessageList
        messages={[
          {
            id: "m0",
            session_id: "s",
            role: "user",
            agent_name: null,
            content: "אני אוהב פופ עברי",
            created_at: "2026-04-01T10:00:00Z",
          },
          {
            id: "m1",
            session_id: "s",
            role: "agent",
            agent_name: "creative_director",
            content: "מעולה!",
            created_at: "2026-04-01T10:00:01Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("אני אוהב פופ עברי")).toBeInTheDocument();
    expect(screen.getByText("מעולה!")).toBeInTheDocument();
  });

  it("shows a loading hint when the list is empty", () => {
    render(<MessageList messages={[]} />);
    expect(screen.getByText(/טוען את ההודעה/)).toBeInTheDocument();
  });
});
