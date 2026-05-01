import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders the Hebrew title", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: /עורך וידאו AI/ })).toBeInTheDocument();
  });
});
