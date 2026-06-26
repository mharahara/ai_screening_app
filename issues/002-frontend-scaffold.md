# issue: frontend プロジェクト初期化（骨組み・ベース UI 基盤・代表ページ）

## ステータス

`done`

## 背景・目的

[001](001-backend-scaffold.md) で backend の骨組みを立てたのに続き、`frontend/` のコードがまだ存在しない。以降の画面 issue（求人/候補者の取り込み画面・ランキング画面・詳細ダイアログ等）を積み上げられるよう、Next.js フロントエンドの骨組み（プロジェクト生成・Tailwind / shadcn/ui 基盤・TanStack Query Provider・API クライアント雛形・起動確認）を立ち上げる。

## 要件

- [ ] `frontend/` に Next.js（App Router・TypeScript）プロジェクトを作成する（npm 管理）。Tailwind CSS / ESLint / Prettier を有効にする。
- [ ] [docs/03_how/05_setup.md](../docs/03_how/05_setup.md) の想定構成に沿って `app/` / `components/` / `lib/` を用意する（中身は本 issue の範囲分のみ）。
- [ ] shadcn/ui を初期化する（`components.json` 生成・`lib/utils.ts` の `cn` ヘルパー・Tailwind 連携設定）。個別 UI コンポーネントの追加は後続 issue。
- [ ] TanStack Query を導入し、App Router の `app/` に `QueryClientProvider` を提供するクライアント Provider を組み込む（layout から利用）。
- [ ] `lib/` に API クライアントの雛形を置く（backend のベース URL を環境変数 `NEXT_PUBLIC_API_BASE_URL` から読む薄いラッパ。`.env.local.example` を用意し、`.env*.local` は `.gitignore` 済みであること）。
- [ ] 代表ページ（`app/page.tsx`）がプレースホルダ内容で表示される（アプリ名・「準備中」程度。具体的な業務画面は後続 issue）。
- [ ] `npm run dev` で起動でき、代表ページがブラウザに表示される。

## 対象レイヤー

- [ ] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `cd frontend && npm install` が成功し、依存（Next.js / React / TypeScript / Tailwind / shadcn/ui 関連 / @tanstack/react-query / ESLint / Prettier）が解決する。
- [ ] `cd frontend && npm run lint` が通る。
- [ ] `cd frontend && npm run build` が通る。
- [ ] `cd frontend && npm run dev` で起動し、代表ページ（`app/page.tsx`）がプレースホルダ内容で表示される。
- [ ] `components.json` が存在し、`lib/utils.ts` の `cn` が使える（shadcn/ui 初期化済み）。
- [ ] `QueryClientProvider` が `app/` のレイアウトに組み込まれ、ビルド時にエラーにならない。
- [ ] `lib/` の API クライアント雛形が `NEXT_PUBLIC_API_BASE_URL` を参照し、`.env.local.example` が存在、`.env*.local` が `.gitignore` 済み。

## 確認したい受け入れシナリオ

- ターミナルで `cd frontend && npm install && npm run dev` を実行 → ブラウザで `localhost:3000` を開くと、アプリ名入りのプレースホルダ画面が表示される（具体的な業務画面・backend との通信は本 issue では未実装）。

## スコープ外（やらないこと）

- 求人/候補者の取り込み画面・ランキング画面・候補者詳細ダイアログなど具体的な業務 UI の実装（後続の画面 issue で扱う）。
- スコア完了ポーリング・状態管理ロジックの実装、および Vitest / Testing Library / MSW のテスト基盤導入（テスト対象ロジックが生まれる最初の機能 issue で導入する）。
- backend（001 で扱う）との実際の API 通信・型共有の確定。
- 個別 shadcn/ui コンポーネント（button / table / dialog 等）の追加。
- CLAUDE.md「やらないこと」全般: 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API / 求人の保存後編集。

## 参考

- [001-backend-scaffold.md](001-backend-scaffold.md) — backend 骨組み（先行 issue）
- [docs/03_how/01_architecture.md](../docs/03_how/01_architecture.md) — フロント技術スタック・処理フロー
- [docs/03_how/05_setup.md](../docs/03_how/05_setup.md) — 想定ディレクトリ構成・セットアップ手順
- [docs/03_how/06_testing.md](../docs/03_how/06_testing.md) — frontend テスト方針（本 issue ではテスト基盤は未導入、後続で導入）
- [CLAUDE.md](../CLAUDE.md) — 技術スタック・スコープ外
