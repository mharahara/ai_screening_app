# issue: グローバルヘッダーの追加

## ステータス

`open`

## 背景・目的

現在ページ間のナビゲーション手段がなく、URL を直接入力する必要がある。すべてのページに共通ヘッダーを設けることで、「求人取り込み」と「候補者取り込み」の画面への導線を確保し、操作効率を上げる。

## 要件

- [ ] `frontend/components/global-header.tsx` を新規作成する。`"use client"` を付与し、`usePathname`（`next/navigation`）で現在パスを取得する。
- [ ] ヘッダー左側に「RabbitPick」テキスト（太字）を表示し、`/` へのリンクを付ける。
- [ ] ヘッダー右側にナビリンクを 2 つ表示する: 「求人取り込み」（`/jobs/new`）と「候補者取り込み」（`/candidates/new`）。
- [ ] 現在のパスに対応するナビリンクにアクティブスタイル（`border-bottom` による下線）を適用し、`aria-current="page"` 属性を付与する。`/` 表示時はいずれのリンクにもアクティブスタイル・`aria-current` を付けない。
- [ ] `frontend/app/layout.tsx` の `<body>` 直下・`<QueryProvider>` の外側に `<GlobalHeader />` を追加する。
- [ ] ヘッダー要素は `<header>` タグを使用する。グローバルヘッダーは `<main>` の外側（`<body>` 直下）に置くため、既存ページ内 `<header>`（`<main>` 内配置、ARIA role=`generic`）との landmark 重複は発生しない。既存ページの `<header>` タグは変更しない。

## 対象レイヤー

- [ ] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `npm run lint` がエラーなし。
- [ ] `npm run build` がエラーなし。
- [ ] すべての既存テスト（`npm run test`）が引き続き通る。`GlobalHeader` 単体テストの追加以外、既存テストファイルは変更しない。
- [ ] `frontend/test/global-header.test.tsx` を新規追加する。`/jobs/new` を現在パスとしたとき「求人取り込み」リンクに `aria-current="page"` が付き、「候補者取り込み」リンクには付かないことを検証する。`usePathname` は `vi.mock("next/navigation", ...)` でモック化する（実際の Next.js バージョンの API に応じて調整可）。

## 確認したい受け入れシナリオ

- どのページ（`/jobs/new`・`/candidates/new`・`/jobs/[id]/rankings`）を開いても、ページ上部にヘッダーが表示される。
- ヘッダー左の「RabbitPick」をクリックすると `/` へ遷移する。
- `/` 表示中は、ナビリンクのいずれにもアクティブスタイル（下線）が付かない。
- `/jobs/new` 表示中、「求人取り込み」リンクに下線が付き、「候補者取り込み」リンクには付かない。
- `/candidates/new` 表示中、「候補者取り込み」リンクに下線が付き、「求人取り込み」リンクには付かない。
- 「求人取り込み」「候補者取り込み」各リンクをクリックすると対応ページへ遷移する。
- 既存の各ページの既存機能に影響がない。

## スコープ外（やらないこと）

- モバイルハンバーガーメニュー
- ダークモードトグル
- ランキングページへのグローバルナビリンク
- ホームページ（`/`）の `<h1>RabbitPick</h1>` の変更（二重表示を許容）
- SVG/画像ロゴアセットの作成
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API / 求人の保存後編集（CLAUDE.md「やらないこと」）

## 参考

- [`../frontend/app/layout.tsx`](../frontend/app/layout.tsx) — 組み込み先
- [`../frontend/app/page.tsx`](../frontend/app/page.tsx) — ホームページ（`<h1>RabbitPick</h1>` あり、変更しない）
- [`../frontend/app/jobs/new/page.tsx`](../frontend/app/jobs/new/page.tsx) — 「求人取り込み」ページ
- [`../frontend/app/candidates/new/page.tsx`](../frontend/app/candidates/new/page.tsx) — 「候補者取り込み」ページ
- [`../frontend/app/jobs/[id]/rankings/page.tsx`](../frontend/app/jobs/[id]/rankings/page.tsx) — `useParams`（`next/navigation`）を使う `"use client"` コンポーネントの実例
- [`../frontend/components/ui/button.tsx`](../frontend/components/ui/button.tsx) — shadcn/ui Button（スタイリング参考）
- [`../frontend/test/rankings-page.test.tsx`](../frontend/test/rankings-page.test.tsx) — `vi.mock("next/navigation", ...)` モックの実例
