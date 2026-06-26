# issue: 求人要件登録 backend（jobs API・構造化・DB）

## ステータス

`done`

## 背景・目的

RabbitPick の処理フローの最上流である「求人要件登録」を backend で実現する。求人票の生テキストを LLM が構造化し（`POST /jobs/parse`）、ユーザー編集後に保存（`POST /jobs`）、セレクター用の一覧取得（`GET /jobs`）・削除（`DELETE /jobs/{id}`）までを API として提供する。これにより後続の frontend 画面・応募書類登録・マッチングが乗る土台を作る。frontend の求人要件取り込み画面は別 issue（004 予定）で扱う。

## 要件

- [ ] `db.py` を実装する（`create_engine` / `SessionLocal` / `Base` / 起動時 `init_db()`＝`create_all`。DB は `config.database_url` の SQLite）。`models.py` の `Job` モデルを [docs/03_how/03_data-model.md](../docs/03_how/03_data-model.md) の `jobs` カラムに沿って定義（配列・タグは JSON カラム、`created_at`、求人削除時に候補者・スコアをカスケード削除できる関係定義の素地を入れる）。
- [ ] `schemas.py` に enum（`EmploymentType` / `RemoteWork` / `PositionLevel`）と、構造化結果 `JobParseResult`、保存用 `JobCreate`、出力用 `JobOut`、一覧用の軽量スキーマ（`id` / `title` / `created_at`）を [docs/03_how/02_ai.md](../docs/03_how/02_ai.md) の定義どおり実装する（Optional は null 許容、配列は空配列デフォルト、`Field(description=...)` に抽出指示）。
- [ ] `config.py` に `parse_max_retries`（既定 3、`.env` の `PARSE_MAX_RETRIES`）を追加する。
- [ ] `services/llm.py` を新規作成し、汎用 `structured_chat(system, user, schema) -> T`（`client.chat(format=schema.model_json_schema())`・Pydantic 検証・最大 `parse_max_retries` 回リトライ・失敗時フィードバック付き再実行）と `structure_job(raw_text) -> JobParseResult`（求人用 system/user 構築）を実装する。Ollama 接続例外・タイムアウト・検証失敗を区別して例外送出する。
- [ ] `routers/jobs.py` を新規作成し、`main.py` に `include_router` する:
  - `POST /jobs/parse`: 生テキスト受領 → `structure_job` → `JobParseResult` に `raw_text` を同梱して返す（**未保存**）。失敗時は [docs/03_how/02_ai.md](../docs/03_how/02_ai.md) に従い `PARSE_FAILED`/`LLM_TIMEOUT`/`LLM_UNAVAILABLE` のエラーコードで `502`/`503` を返す。
  - `POST /jobs`: 構造化済み＋`raw_text` を受領して保存し、`JobOut` を返す。
  - `GET /jobs`: 一覧（`id` / `title` / `created_at`）を返す（セレクター用）。
  - `DELETE /jobs/{id}`: 求人と関連データを削除する。存在しなければ `404`。
  - **保存後編集の API（`PUT`/`PATCH /jobs/{id}`）は作らない**（スコープ外）。

## 対象レイヤー

- [x] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [ ] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `cd backend && uv run ruff check` / `uv run ruff format --check` / `uv run mypy .` が通る。
- [ ] `cd backend && uv run pytest` が通る。Ollama 呼び出しは**モック化**し、以下をカバーする（[docs/03_how/06_testing.md](../docs/03_how/06_testing.md) 準拠）:
  - `POST /jobs/parse` 正常系: モックが妥当な `JobParseResult` JSON を返すと 200・`raw_text` 同梱でレスポンスが返る。
  - `POST /jobs/parse` 失敗系: 検証失敗（壊れた JSON）→ リトライ上限超過で `502`/`PARSE_FAILED`、接続例外 → `503`/`LLM_UNAVAILABLE`、タイムアウト → `502`/`LLM_TIMEOUT`。
  - `structured_chat` のリトライ: `ValidationError` 時に最大 `parse_max_retries` 回まで再試行し、成功すれば結果を返す。
  - `POST /jobs` 保存: 妥当な入力で保存され `JobOut` が返る。不正入力は `422`。
  - `GET /jobs`: 保存済みが `id`/`title`/`created_at` の一覧で返る。0 件で空配列。
  - `DELETE /jobs/{id}`: 削除で 200/204、存在しない id は `404`。`PUT`/`PATCH /jobs/{id}` が存在しない（`404`/`405`）。
  - `init_db()` でインメモリ SQLite に `jobs` テーブルが生成される。
  - テスト用 DB はインメモリ／一時ファイルに差し替え、本番 DB を汚さない。Ollama は `services/llm.py` の 1 箇所をモックする。
- [ ] `uv run uvicorn main:app --reload` 起動時に DB 初期化が走り、import エラーが出ない。

## 確認したい受け入れシナリオ

- Ollama 常駐前提で `cd backend && uv run uvicorn main:app --reload` を起動し、`curl -X POST localhost:8000/jobs/parse`（実際の求人票テキスト）→ 構造化 JSON＋`raw_text` が返る → その結果を `POST /jobs` で保存 → `GET /jobs` に現れる → `DELETE /jobs/{id}` で消える、を確認する。**LLM の構造化内容そのものの妥当性（抽出精度）は人の受け入れ確認で担保する**（自動テストはモックで通り道のみ検証）。

## スコープ外（やらないこと）

- frontend の求人要件取り込み画面・グローバルヘッダー・求人セレクター UI（別 issue 004 予定）。
- frontend のテスト基盤（Vitest/MSW/Testing Library）導入（frontend 画面 issue と同時に行う）。
- 応募書類登録（`candidates`）・マッチング・スコアリング・ランキング（後続 issue）。`models.py` の候補者/スコアは本 issue では最小限（Job のカスケード関係の素地まで）に留め、本体実装は後続。
- **求人の保存後編集**（`PUT`/`PATCH /jobs/{id}`。CLAUDE.md「やらないこと」）。
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API。

## 参考

- [docs/03_how/02_ai.md](../docs/03_how/02_ai.md) — 構造化スキーマ・プロンプト・`structured_chat`・堅牢化（リトライ・502/503・エラーコード）
- [docs/03_how/03_data-model.md](../docs/03_how/03_data-model.md) — `jobs` テーブルのカラム・カスケード方針
- [docs/03_how/04_api.md](../docs/03_how/04_api.md) — `POST /jobs/parse` / `POST /jobs` / `GET /jobs` / `DELETE /jobs/{id}`
- [docs/03_how/06_testing.md](../docs/03_how/06_testing.md) — テスト方針（Ollama モック・失敗系・契約）
- [backend/config.py](../backend/config.py) — `Settings`（`parse_max_retries` を追加）
- [backend/schemas.py](../backend/schemas.py) / [backend/models.py](../backend/models.py) / [backend/db.py](../backend/db.py) — 現状プレースホルダ（本 issue で実装）
- [001-backend-scaffold.md](001-backend-scaffold.md) — 依存する backend 骨組み（done）
