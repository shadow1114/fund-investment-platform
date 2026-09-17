import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App shell", () => {
  it("renders the four M1.7 navigation destinations", () => {
    render(<App />);

    expect(screen.getByRole("link", { name: "基金研究" })).toHaveAttribute(
      "href",
      "/funds",
    );
    expect(screen.getByRole("link", { name: "候选池" })).toHaveAttribute(
      "href",
      "/universes",
    );
    expect(screen.getByRole("link", { name: "组合决策" })).toHaveAttribute(
      "href",
      "/portfolios",
    );
    expect(screen.getByRole("link", { name: "回测" })).toHaveAttribute(
      "href",
      "/backtests",
    );
  });
});
