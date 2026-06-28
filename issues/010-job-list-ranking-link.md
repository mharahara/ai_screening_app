# issue: 求人一覧に「ランキング」リンクを追加

## ステータス

`open`

## 背景・目的

候補者登録直後は「ランキングを見る」ボタンが表示されるが、後から別の求人のランキングを確認したい場合や追加登録後に再確認したい場合に、URL を手打ちする以外に方法がない。`/jobs/new` の保存済み求人リストの各行に「ランキング」リンクを追加し、いつでもワンクリックでランキングへ遷移できるようにする。

## 要件

- [ ] `frontend/app/jobs/new/page.tsx` の保存済み求人リスト（各 `<li>`）に、`/jobs/{id}/rankings` へのリンクボタン「ランキング」を追加する。
- [ ] ボタンは `<Button render={<Link href={`/jobs/${job.id}/rankings`} />} nativeButton={false} variant="outline" size="sm">ランキング</Button>` パターンで実装する（`candidates/new` 375〜384 行目と同じパターン）。DOM 上は `<a>` タグとして出力されるため、既存の削除ボタン（`getByRole("button")`）との衝突は発生しない。
- [ ] 右端ボタン群（ランキング・削除）を `<div className="flex items-center gap-2">` で囲み、「ランキング」を左、削除ボタンを右の順に並べる。
- [ ] `next/link` の `Link` を `jobs/new/page.tsx` に import する。

## 対象レイヤー

- [ ] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `npm run lint` がエラーなし。
- [ ] `npm run build` がエラーなし。
- [ ] `frontend/test/jobs-new-page.test.tsx` に、保存済み求人リストの各行で `getByRole("link", { name: "ランキング" })` が取得でき、その `href` 属性が `/jobs/{id}/rankings` になっていることを確認するテストを追加する。既存テストは変更しない。
- [ ] 追加したテストを含む全テスト（`npm run test`）が通る。

## 確認したい受け入れシナリオ

- `/jobs/new` を開き、保存済み求人リストの各行に「ランキング」ボタンが表示される。
- 「ランキング」ボタンをクリックすると `/jobs/{id}/rankings` へ遷移する。
- 削除ボタンの動作（確認ダイアログ表示・削除実行・一覧再取得）が従来通り動作する。
- 候補者取り込みページ（`/candidates/new`）の保存後「ランキングを見る」ボタンは従来通り動作する。

## スコープ外（やらないこと）

- モバイル専用レイアウト・レスポンシブ対応
- 求人詳細ページの作成
- ランキングページ自体への変更
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API / 求人の保存後編集（CLAUDE.md「やらないこと」）

## 参考

- [`../frontend/app/jobs/new/page.tsx`](../frontend/app/jobs/new/page.tsx) — 変更対象（453〜498 行目が保存済み求人リスト）
- [`../frontend/app/candidates/new/page.tsx`](../frontend/app/candidates/new/page.tsx) — `render={<Link />}` パターンの実例（375〜384 行目）
- [`../frontend/components/ui/button.tsx`](../frontend/components/ui/button.tsx) — variant / size の確認
- [`../frontend/lib/jobs.ts`](../frontend/lib/jobs.ts) — `JobListItem` 型（`id: number`）
- [`../frontend/test/jobs-new-page.test.tsx`](../frontend/test/jobs-new-page.test.tsx) — 追加先の既存テストファイル
