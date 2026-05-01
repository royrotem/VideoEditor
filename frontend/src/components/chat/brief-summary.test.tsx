import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BriefSummary } from "./brief-summary";

describe("BriefSummary", () => {
  it("renders title, intent, duration and Hebrew pacing label", () => {
    render(
      <BriefSummary
        brief={{
          title: "חתונה — קאט קצר",
          intent: "סיכום אנרגטי של 30 שניות",
          target_duration_seconds: 30,
          style_notes: ["אנרגטי", "קצב מהיר"],
          music_direction: "פופ עברי",
          pacing: "fast",
        }}
      />,
    );

    expect(screen.getByText("חתונה — קאט קצר")).toBeInTheDocument();
    expect(screen.getByText("סיכום אנרגטי של 30 שניות")).toBeInTheDocument();
    expect(screen.getByText("30s")).toBeInTheDocument();
    expect(screen.getByText("מהיר")).toBeInTheDocument();
    expect(screen.getByText("פופ עברי")).toBeInTheDocument();
    expect(screen.getByText("אנרגטי")).toBeInTheDocument();
  });

  it("omits style notes and music direction when empty", () => {
    render(
      <BriefSummary
        brief={{
          title: "t",
          intent: "i",
          target_duration_seconds: 60,
          style_notes: [],
          music_direction: null,
          pacing: "medium",
        }}
      />,
    );

    expect(screen.queryByText(/הערות סגנון/)).not.toBeInTheDocument();
    expect(screen.queryByText(/כיוון מוזיקלי/)).not.toBeInTheDocument();
  });
});
