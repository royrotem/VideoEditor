import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AssetList } from "./asset-list";

describe("AssetList", () => {
  it("renders the empty-state hint when there are no assets", () => {
    render(<AssetList assets={[]} />);
    expect(screen.getByText(/עדיין אין קבצים/)).toBeInTheDocument();
  });

  it("renders one row per asset with status, size, and timestamp", () => {
    render(
      <AssetList
        assets={[
          {
            id: "a1",
            project_id: "p1",
            filename: "wedding.mp4",
            content_type: "video/mp4",
            size_bytes: 1024 * 1024,
            status: "ready",
            created_at: "2026-04-01T10:00:00Z",
          },
          {
            id: "a2",
            project_id: "p1",
            filename: "broken.mov",
            content_type: "video/quicktime",
            size_bytes: null,
            status: "failed",
            created_at: "2026-04-01T11:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("wedding.mp4")).toBeInTheDocument();
    expect(screen.getByText("broken.mov")).toBeInTheDocument();
    expect(screen.getByText("מוכן")).toBeInTheDocument();
    expect(screen.getByText("נכשל")).toBeInTheDocument();
    // The MB-formatted size shows up at least once.
    expect(screen.getByText(/1\.0 MB/)).toBeInTheDocument();
  });
});
