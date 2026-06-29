import * as React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";

/**
 * ホームページ（app/page.tsx）の振る舞いテスト。
 *
 * - 2 枚のクイックリンクカードが /jobs/new・/candidates/new を指している
 */

describe("ホームページ クイックリンクカード", () => {
  it("求人取り込みカードが /jobs/new へのリンクである", () => {
    render(<Home />);
    const links = screen.getAllByRole("link");
    const jobsLink = links.find(
      (link) => link.getAttribute("href") === "/jobs/new",
    );
    expect(jobsLink).toBeDefined();
  });

  it("候補者取り込みカードが /candidates/new へのリンクである", () => {
    render(<Home />);
    const links = screen.getAllByRole("link");
    const candidatesLink = links.find(
      (link) => link.getAttribute("href") === "/candidates/new",
    );
    expect(candidatesLink).toBeDefined();
  });

  it("リンクカードがちょうど 2 枚ある", () => {
    render(<Home />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
  });
});
