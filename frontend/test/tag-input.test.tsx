import * as React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TagInput } from "@/components/tag-input";

/**
 * TagInput の振る舞いテスト。見た目（CSS）ではなく、
 * 入力 → onChange（配列状態）への反映を検証する。
 *
 * 制御コンポーネントなので、テスト側で value/onChange を state に束ねた
 * ラッパで描画し、実際の配列遷移を assert する。
 */
function Harness({ initial = [] as string[] }: { initial?: string[] }) {
  const [tags, setTags] = React.useState<string[]>(initial);
  return (
    <div>
      <TagInput id="tags" value={tags} onChange={setTags} placeholder="add" />
      <output data-testid="value">{tags.join("|")}</output>
    </div>
  );
}

describe("TagInput", () => {
  it("Enter でタグを追加する", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const input = screen.getByPlaceholderText("add");
    await user.type(input, "Python{Enter}");

    expect(screen.getByTestId("value")).toHaveTextContent("Python");
    // 入力欄はクリアされる。
    expect(input).toHaveValue("");
  });

  it("カンマでタグを追加する", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const input = screen.getByPlaceholderText("add");
    await user.type(input, "Go,");

    expect(screen.getByTestId("value")).toHaveTextContent("Go");
  });

  it("複数タグを追加し、× で個別削除する", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["Python", "Go", "Rust"]} />);

    expect(screen.getByTestId("value")).toHaveTextContent("Python|Go|Rust");

    // 真ん中（Go）の削除ボタンを押す。aria-label で特定する。
    await user.click(screen.getByRole("button", { name: "Go を削除" }));

    expect(screen.getByTestId("value")).toHaveTextContent("Python|Rust");
    expect(
      screen.queryByRole("button", { name: "Go を削除" }),
    ).not.toBeInTheDocument();
  });

  it("空欄で Backspace を押すと末尾のタグを削除する", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["Python", "Go"]} />);

    const input = screen.getByPlaceholderText("add");
    input.focus();
    await user.keyboard("{Backspace}");

    expect(screen.getByTestId("value")).toHaveTextContent("Python");
  });

  it("重複タグは追加しない", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["Python"]} />);

    const input = screen.getByPlaceholderText("add");
    await user.type(input, "Python{Enter}");

    // 重複は無視され、1 件のまま。
    expect(screen.getByTestId("value")).toHaveTextContent("Python");
    expect(screen.getByTestId("value").textContent).toBe("Python");
  });

  it("カンマ区切りの貼り付けでカンマ確定分を全件タグ化し、末尾は draft に残す", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const input = screen.getByPlaceholderText("add");
    await user.click(input);
    await user.paste("Python,Go,Rust");

    // カンマ手前の Python・Go はどちらもタグ化される。
    expect(screen.getByTestId("value").textContent).toBe("Python|Go");
    // 末尾の Rust は draft（入力欄）に残る。
    expect(input).toHaveValue("Rust");
  });

  it("カンマ貼り付けで重複・空白を除いて全件タグ化する", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["Python"]} />);

    const input = screen.getByPlaceholderText("add");
    await user.click(input);
    // 既存の Python は重複で無視、" Go " は空白トリム、空要素は除去。
    await user.paste("Python, Go ,,Rust,");

    // 末尾がカンマなので末尾断片は空 → draft は空、全件確定。
    expect(screen.getByTestId("value").textContent).toBe("Python|Go|Rust");
    expect(input).toHaveValue("");
  });
});
