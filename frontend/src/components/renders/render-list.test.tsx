import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RenderList } from "./render-list";

const baseJob = {
  project_id: "p",
  edl_version_id: "e",
  output_bucket: null,
  output_key: null,
  error_message: null,
  created_at: "2026-04-01T10:00:00Z",
  updated_at: "2026-04-01T10:00:00Z",
};

describe("RenderList", () => {
  it("shows the empty-state hint when no jobs are passed", () => {
    render(<RenderList jobs={[]} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText(/עוד אין רנדרים/)).toBeInTheDocument();
  });

  it("renders one row per job with the matching status badge", () => {
    render(
      <RenderList
        jobs={[
          { ...baseJob, id: "j1", status: "succeeded" },
          { ...baseJob, id: "j2", status: "failed", error_message: "boom" },
          { ...baseJob, id: "j3", status: "running" },
        ]}
        selectedId={null}
        onSelect={() => {}}
      />,
    );

    expect(screen.getByText("הושלם")).toBeInTheDocument();
    expect(screen.getByText("נכשל")).toBeInTheDocument();
    expect(screen.getByText("בעיבוד…")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("calls onSelect with the clicked job", async () => {
    const onSelect = vi.fn();
    const job = { ...baseJob, id: "job-x", status: "succeeded" as const };
    render(<RenderList jobs={[job]} selectedId={null} onSelect={onSelect} />);

    const button = screen.getByRole("button");
    button.click();

    expect(onSelect).toHaveBeenCalledWith(job);
  });
});
