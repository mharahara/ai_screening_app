import * as React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GlobalHeader } from "@/components/global-header";

/**
 * GlobalHeader コンポーネントの振る舞いテスト。
 *
 * - 現在パスに一致するナビリンクに aria-current="page" が付く
 * - 一致しないリンクには aria-current が付かない
 * - 各リンクが正しい href を持つ
 *
 * CSS クラスの有無はテストしない（テスト方針: 見た目はテスト対象外）。
 * usePathname は vi.mock("next/navigation", ...) でモック化する。
 */

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

// vi.mock の後に import する（hoisting のため実際には先頭で評価される）。
import { usePathname } from "next/navigation";

describe("GlobalHeader", () => {
  describe("aria-current の付与", () => {
    it('/jobs/new が現在パスのとき「求人取り込み」に aria-current="page" が付き「候補者取り込み」には付かない', () => {
      vi.mocked(usePathname).mockReturnValue("/jobs/new");

      render(<GlobalHeader />);

      const jobsLink = screen.getByRole("link", { name: "求人取り込み" });
      const candidatesLink = screen.getByRole("link", { name: "候補者取り込み" });

      expect(jobsLink).toHaveAttribute("aria-current", "page");
      expect(candidatesLink).not.toHaveAttribute("aria-current");
    });

    it('/candidates/new が現在パスのとき「候補者取り込み」に aria-current="page" が付き「求人取り込み」には付かない', () => {
      vi.mocked(usePathname).mockReturnValue("/candidates/new");

      render(<GlobalHeader />);

      const jobsLink = screen.getByRole("link", { name: "求人取り込み" });
      const candidatesLink = screen.getByRole("link", { name: "候補者取り込み" });

      expect(candidatesLink).toHaveAttribute("aria-current", "page");
      expect(jobsLink).not.toHaveAttribute("aria-current");
    });

    it("/ が現在パスのときいずれのリンクにも aria-current が付かない", () => {
      vi.mocked(usePathname).mockReturnValue("/");

      render(<GlobalHeader />);

      const jobsLink = screen.getByRole("link", { name: "求人取り込み" });
      const candidatesLink = screen.getByRole("link", { name: "候補者取り込み" });

      expect(jobsLink).not.toHaveAttribute("aria-current");
      expect(candidatesLink).not.toHaveAttribute("aria-current");
    });
  });

  describe("リンクの href", () => {
    it('「RabbitPick」リンクが存在し href="/" を持つ', () => {
      vi.mocked(usePathname).mockReturnValue("/");

      render(<GlobalHeader />);

      const homeLink = screen.getByRole("link", { name: "RabbitPick" });
      expect(homeLink).toHaveAttribute("href", "/");
    });

    it('「求人取り込み」リンクが href="/jobs/new" を持つ', () => {
      vi.mocked(usePathname).mockReturnValue("/");

      render(<GlobalHeader />);

      const jobsLink = screen.getByRole("link", { name: "求人取り込み" });
      expect(jobsLink).toHaveAttribute("href", "/jobs/new");
    });

    it('「候補者取り込み」リンクが href="/candidates/new" を持つ', () => {
      vi.mocked(usePathname).mockReturnValue("/");

      render(<GlobalHeader />);

      const candidatesLink = screen.getByRole("link", { name: "候補者取り込み" });
      expect(candidatesLink).toHaveAttribute("href", "/candidates/new");
    });
  });
});
