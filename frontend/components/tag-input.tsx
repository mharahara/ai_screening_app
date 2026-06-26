"use client";

import * as React from "react";
import { XIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

/**
 * チップ型のタグ入力。
 *
 * - Enter またはカンマで現在の入力値をタグとして**追加**する。
 * - 各タグの × ボタンで**個別削除**できる。
 * - 値は制御コンポーネントとして親が `value` / `onChange` で保持する。
 *
 * 求人フォームの required_skills / preferred_skills / certifications に使う。
 */
export interface TagInputProps {
  /** 現在のタグ配列。 */
  value: string[];
  /** タグ配列が変化したときに呼ばれる。 */
  onChange: (next: string[]) => void;
  /** 入力欄の placeholder。 */
  placeholder?: string;
  /** 入力欄に紐づける id（Label の htmlFor 用）。 */
  id?: string;
  className?: string;
}

export function TagInput({
  value,
  onChange,
  placeholder,
  id,
  className,
}: TagInputProps) {
  const [draft, setDraft] = React.useState("");

  /**
   * 複数の生文字列をまとめてタグ追加する。
   *
   * 同一イベント内で複数回 `onChange` を呼ぶと、各呼び出しが同じ `value`
   * クロージャを参照して最後の1件しか反映されない。ローカルの新配列に
   * 積んでから 1 回だけ `onChange` を呼ぶことでこれを防ぐ。
   * 空白トリム・空文字除去・（既存/今回追加分との）重複無視を行う。
   */
  function addTags(raws: string[]) {
    const next = [...value];
    for (const raw of raws) {
      const tag = raw.trim();
      if (tag === "") continue;
      if (next.includes(tag)) continue;
      next.push(tag);
    }
    if (next.length !== value.length) {
      onChange(next);
    }
    setDraft("");
  }

  function addTag(raw: string) {
    addTags([raw]);
  }

  function removeTag(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addTag(draft);
      return;
    }
    // 入力が空のときに Backspace で直前のタグを削除する。
    if (event.key === "Backspace" && draft === "" && value.length > 0) {
      event.preventDefault();
      removeTag(value.length - 1);
    }
  }

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const next = event.target.value;
    // カンマ区切りで貼り付けられたケースに対応する。
    if (next.includes(",")) {
      const parts = next.split(",");
      const last = parts.pop() ?? "";
      // カンマ手前の全 part をまとめて 1 回の onChange で反映する。
      addTags(parts);
      setDraft(last);
      return;
    }
    setDraft(next);
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {value.map((tag, index) => (
            <li
              key={`${tag}-${index}`}
              data-slot="tag"
              className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-sm text-secondary-foreground"
            >
              <span>{tag}</span>
              <button
                type="button"
                aria-label={`${tag} を削除`}
                onClick={() => removeTag(index)}
                className="inline-flex items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <XIcon className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <Input
        id={id}
        value={draft}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onBlur={() => addTag(draft)}
        placeholder={placeholder}
      />
    </div>
  );
}
