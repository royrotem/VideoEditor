import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectList } from "./project-list";

describe("ProjectList", () => {
  it("renders the empty-state hint when no projects are passed", () => {
    render(<ProjectList projects={[]} />);
    expect(
      screen.getByText(/עדיין אין פרויקטים/),
    ).toBeInTheDocument();
  });

  it("renders one item per project with a link to its detail page", () => {
    const projects = [
      {
        id: "proj-1",
        name: "סרטון חתונה",
        description: "קאט ראשון",
        created_at: "2026-04-01T10:00:00Z",
        updated_at: "2026-04-01T10:00:00Z",
      },
      {
        id: "proj-2",
        name: "סרטון תאגידי",
        description: null,
        created_at: "2026-04-02T11:00:00Z",
        updated_at: "2026-04-02T11:00:00Z",
      },
    ];

    render(<ProjectList projects={projects} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(screen.getByText("סרטון חתונה")).toBeInTheDocument();
    expect(screen.getByText("סרטון תאגידי")).toBeInTheDocument();

    const link = screen.getByText("סרטון חתונה").closest("a");
    expect(link).toHaveAttribute("href", "/projects/proj-1");
  });
});
