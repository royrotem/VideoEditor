import { describe, expect, it } from "vitest";

import { formatBytes, formatDateTime } from "./format";

describe("formatBytes", () => {
  it("formats small values with the B suffix", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
  });

  it("rolls over into KB / MB / GB at 1024 thresholds", () => {
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(1024 * 1024)).toBe("1.0 MB");
    expect(formatBytes(2.5 * 1024 * 1024 * 1024)).toBe("2.5 GB");
  });

  it("renders an em-dash for null / undefined", () => {
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(undefined)).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("renders a Hebrew-locale string for a valid ISO timestamp", () => {
    const output = formatDateTime("2026-04-30T10:00:00Z");
    // We don't pin the exact format string (Intl is locale-data-driven)
    // - just assert it's non-empty and includes the year.
    expect(output).toContain("26");
    expect(output.length).toBeGreaterThan(5);
  });

  it("returns an empty string for invalid input rather than NaN markers", () => {
    expect(formatDateTime("not a date")).toBe("");
  });
});
