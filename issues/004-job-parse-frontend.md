# issue: 求人要件取り込み画面 frontend（貼り付け→構造化→編集→保存）

## ステータス

`done`

## 背景・目的

RabbitPick の処理フロー最上流「求人要件登録」を frontend で実現する。求人票の生テキストを貼り付け → `POST /jobs/parse` で LLM 構造化 → 画面で編集 → `POST /jobs` で保存、という導線をユーザーに提供する。backend は issue 003 で完成済みのため、その API を叩く最初の業務画面を作り、後続の候補者取り込み・ランキング画面が乗る frontend の土台（API クライアント・テスト基盤）を整える。

## 要件

- [ ] **backend: CORS 設定**を追加する（`backend/main.py` に `CORSMiddleware`。`allow_origins=["http://localhost:3000"]`、メソッド・ヘッダーは必要十分に許可）。これにより `localhost:3000` → `localhost:8000` のリクエストがブラウザでブロックされない。
- [ ] **`lib/jobs.ts`** を新規作成し、jobs API クライアントと型を実装する（`parseJob(rawText) -> JobParseResponse` / `createJob(JobCreate) -> JobOut` / `listJobs() -> JobListItem[]` / `deleteJob(id) -> void`）。型は backend の `schemas.py`（`JobParseResult` / `JobCreate` / `JobOut` / enum）と一致させる。
- [ ] **`lib/api.ts` の `apiFetch` / `ApiError` を拡張**し、エラーレスポンスの `detail`（`{ code, message, attempts }`）を `ApiError` に保持できるようにする。既存の 204 No Content 処理・呼び出し箇所を壊さない。
- [ ] **`/jobs/new` 専用ページ**（`app/jobs/new/page.tsx`）を実装する:
  - 生テキスト用テキストエリア＋「構造化する」ボタン → `parseJob`（TanStack Query の `useMutation`）。
  - parse 結果を編集フォームにバインド（`title` / enum 3種（`EmploymentType` / `RemoteWork` / `PositionLevel`）/ Optional フィールドは null 許容 / 配列フィールドはタグ UI）。
  - **タグ UI**: `required_skills` / `preferred_skills` / `certifications` を Enter またはカンマで**追加**、×で**個別削除**できるチップ型入力。
  - 「保存する」ボタン → `createJob`（`JobParseResult` の全フィールド＋`raw_text` を送信）。保存成功で完了表示（例: トースト or 一覧へ反映）。
  - parse 失敗時、`ApiError.detail.code` を見て **`PARSE_FAILED`／`LLM_TIMEOUT`／`LLM_UNAVAILABLE` で文言を出し分け**てユーザーに表示する。
- [ ] **保存済み求人一覧**を画面に表示する（`listJobs` を `useQuery`、`id`／`title`／`created_at`）。各行に**削除**（`deleteJob` → `useMutation`、確認ダイアログ付き、成功で一覧を invalidate）。保存後の**再編集導線は出さない**（スコープ外）。
- [ ] 必要な **shadcn/ui コンポーネント**を `npx shadcn add` で追加する（Button / Textarea / Input / Select / Label / Dialog（or AlertDialog）など）。`components.json` の既存設定（style: `base-nova`）に従う。
- [ ] **frontend テスト基盤を導入**する（Vitest ＋ @testing-library/react ＋ jsdom ＋ MSW）。`package.json` に `test` スクリプトを追加し、[docs/03_how/06_testing.md](../docs/03_how/06_testing.md) に沿う。

## 対象レイヤー

- [x] backend（`backend/` — CORS 設定のみ）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 求人取り込み画面）

## 受け入れ条件（Definition of Done）

- [ ] `cd backend && uv run ruff check` / `uv run ruff format --check` / `uv run mypy .` / `uv run pytest` が通る（CORS 追加で既存テストが壊れない）。
- [ ] `cd frontend && npm run lint` / `npm run build` / `npm run test` が通る。
- [ ] frontend テスト（API/fetch は MSW でモック。[docs/03_how/06_testing.md](../docs/03_how/06_testing.md) 準拠）で以下をカバーする:
  - `lib/jobs.ts` の各関数が正しいメソッド・パス・ボディで呼び、レスポンスを期待型にマッピングする。
  - parse → 編集 → 保存の状態遷移: parse 成功でフォームに値が入り、保存で `createJob` が `raw_text` 込みのボディを送る。
  - parse 失敗系: 502/`PARSE_FAILED`・503/`LLM_UNAVAILABLE`・502/`LLM_TIMEOUT` で**コードごとに異なる文言**が表示される。
  - タグ UI: 追加（Enter/カンマ）・個別削除が配列状態へ正しく反映される。
  - 一覧: `listJobs` の結果が描画され、削除後に一覧が更新される（invalidate）。
- [ ] `npm run dev`（frontend）＋ `uv run uvicorn main:app --reload`（backend）＋ Ollama 常駐で、ブラウザから CORS エラーなく `/jobs/new` が動作する。

## 確認したい受け入れシナリオ

- `localhost:3000/jobs/new` で求人票テキストを貼り付け「構造化する」→ 構造化結果がフォームに反映される → タグやフィールドを編集 → 「保存する」→ 保存済み一覧に現れる → 「削除」で確認ダイアログ → 消える、までをブラウザで確認する。
- Ollama 未起動／壊れた応答時に、`/jobs/new` で parse がエラー文言を**出し分けて**表示する（`LLM_UNAVAILABLE`＝未起動、`PARSE_FAILED`＝構造化失敗 など）。
- 既存導線（トップページ `/` の表示）が壊れていない。
- **LLM の構造化内容そのものの妥当性（抽出精度）は人の受け入れ確認で担保する**（自動テストは MSW モックで通り道のみ検証）。

## スコープ外（やらないこと）

- グローバルヘッダー・求人セレクター・選択中求人のアプリ全体状態共有（後続 issue。本 issue は `/jobs/new` 単体に集中）。
- 候補者取り込み・マッチング・スコアリング・ランキング画面（後続 issue）。
- **求人の保存後編集**（`PUT`/`PATCH /jobs/{id}` は backend に存在しない。UI でも再編集導線を出さない。CLAUDE.md「やらないこと」）。
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API。

## 参考

- [docs/03_how/04_api.md](../docs/03_how/04_api.md) — `POST /jobs/parse` / `POST /jobs` / `GET /jobs` / `DELETE /jobs/{id}` の契約
- [docs/03_how/02_ai.md](../docs/03_how/02_ai.md) — 構造化スキーマ・enum・parse 失敗時のエラーコード（`PARSE_FAILED`/`LLM_TIMEOUT`/`LLM_UNAVAILABLE`）
- [docs/03_how/01_architecture.md](../docs/03_how/01_architecture.md) — frontend 構成方針
- [docs/03_how/06_testing.md](../docs/03_how/06_testing.md) — テスト方針（frontend は Vitest/MSW、API モック）
- [backend/routers/jobs.py](../backend/routers/jobs.py) / [backend/schemas.py](../backend/schemas.py) — 叩く API の実装と型
- [backend/main.py](../backend/main.py) — CORS を追加する対象
- [frontend/lib/api.ts](../frontend/lib/api.ts) — `apiFetch` / `ApiError`（拡張対象）
- [frontend/components/query-provider.tsx](../frontend/components/query-provider.tsx) — TanStack Query セットアップ（再利用）
- [frontend/app/layout.tsx](../frontend/app/layout.tsx) / [frontend/components.json](../frontend/components.json) — レイアウト・shadcn/ui 設定
- [003-job-parse-backend.md](003-job-parse-backend.md) — 依存する backend（done）
