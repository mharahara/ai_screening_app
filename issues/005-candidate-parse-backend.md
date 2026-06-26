# issue: 応募書類取り込み backend（candidates API・構造化・DB）

## ステータス

`open`

## 背景・目的

RabbitPick の処理フロー2「応募書類登録」の backend を実装する。応募書類（職務経歴書・履歴書等）の生テキストを `POST /candidates/parse` で LLM 構造化し、編集後に `POST /candidates` で保存する API を提供する。`Candidate` は `Job.id` に紐づくため、求人登録 backend（003 完了）の次に作るのが処理フロー順として自然で、後続の候補者取り込み画面 frontend・マッチング（スコア算出）が乗る土台になる。

本 issue は **candidates の CRUD と構造化に集中**し、スコア算出（LLM 評価・重み付け集計・BackgroundTasks 起動）と `Score` モデルは後続のマッチング issue に切り出す。003（jobs backend）の実装パターン（router / schema / service / model / test）をそのまま踏襲する。

## 要件

- [ ] **`models.py` に `Candidate` モデルを追加**する（`Job` モデルのパターンを踏襲）。カラムは docs/03_how/03_data-model.md の `candidates` に準拠（id / job_id / name / age / nearest_station / desired_rate / experience_years / skills / certifications / work_history / education / self_pr / raw_text / created_at）。配列フィールド（skills / certifications）は JSON カラムで保持する。
- [ ] **`job_id` 外部キー＋カスケード削除**を実装する。`Candidate.job_id` を `Job.id` への FK にし、`Job.candidates` relationship に `cascade="all, delete-orphan"` を設定。SQLite で `ON DELETE` を効かせるため **`db.py` に `PRAGMA foreign_keys = ON`** を追加する（engine connect イベント等）。既存の `DELETE /jobs/{id}` テストが壊れないことを確認する。
- [ ] **`schemas.py` に candidates スキーマを追加**する（`JobParseResult` → `CandidateParseResult` のパターン）。`CandidateParseResult`（docs/03_how/02_ai.md のフィールド表に厳密準拠: name / age / nearest_station / desired_rate / experience_years / skills / certifications / work_history / education / self_pr）/ `CandidateCreate`（= ParseResult + `job_id` + `raw_text`）/ `CandidateOut`（id + 全フィールド + created_at）。各 `Field(description=...)` は LLM 抽出指示としても機能させる。
- [ ] **`services/structuring.py` に `structure_candidate(raw_text) -> CandidateParseResult` を追加**する（同ファイルの `structure_job` と同構造。`services/llm.py` の汎用 `structured_chat`（リトライ付き）を再利用し、応募書類用の system/user プロンプトを差し替える）。※ services 層は責務ごとに分割済み（`llm.py`＝Ollama 接続と汎用 `structured_chat`、`structuring.py`＝構造化タスク）。
- [ ] **`routers/candidates.py` を新規作成**し、`POST /candidates/parse`（構造化のみ・未保存）/ `POST /candidates`（保存し `CandidateOut` を返す）/ `DELETE /candidates/{id}`（候補者削除、204）を実装する。`POST /candidates` の `job_id` は存在チェックし、無ければ 404。`main.py` に `candidates.router` を `include_router` する。
- [ ] **`POST /candidates` のスコア算出バックグラウンド起動はスコープ外**（後続マッチング issue）。本 issue では保存して `CandidateOut` を返すところまで。コード上は「後続でここに BackgroundTasks を足す」旨のコメントを残してよい。
- [ ] **テストを追加**する（`test_candidates_api.py` を新規。`structure_candidate` のプロンプト・スキーマ検証は `structuring.py` 対応のテストに置く）。Ollama はモック化（既存 `conftest.py` の autouse モックを利用）。

## 対象レイヤー

- [x] backend（`backend/` — candidates の models / schemas / service / router / test、db.py の FK pragma）
- [ ] frontend（対象外。候補者取り込み画面は後続 issue）

## 受け入れ条件（Definition of Done）

- [ ] `cd backend && uv run ruff check` / `uv run ruff format --check` / `uv run mypy .` / `uv run pytest` がすべて通る。
- [ ] backend テスト（Ollama はモック。docs/03_how/06_testing.md 準拠）で以下をカバーする:
  - `POST /candidates/parse`: 正常系で `CandidateParseResult` 相当の JSON を返す。LLM 失敗系（`PARSE_FAILED` / `LLM_TIMEOUT` / `LLM_UNAVAILABLE`）で jobs と同じエラーコード・ステータスを返す。
  - `POST /candidates`: 正常系で保存され `CandidateOut`（id / created_at 付き）を返し、`raw_text` と `job_id` が永続化される。存在しない `job_id` で 404。
  - `DELETE /candidates/{id}`: 削除され 204。存在しない id で 404。
  - **カスケード削除**: `DELETE /jobs/{id}` で紐づく候補者も削除される（FK pragma が効いている）。
  - `structure_candidate`: `structured_chat` を期待プロンプト・スキーマで呼び、結果を `CandidateParseResult` にマッピングする（`test_structuring.py` 等。`structure_candidate` は `services/structuring.py`）。
- [ ] 既存の jobs テスト（`test_jobs_api.py` / `test_llm.py`）が引き続き通る（FK pragma 追加で `DELETE /jobs` が壊れない）。

## 確認したい受け入れシナリオ

- `uv run uvicorn main:app --reload` ＋ Ollama 常駐で、`POST /candidates/parse` に応募書類テキストを投げると構造化 JSON が返る。
- 既存の求人を1件作成 → その `job_id` で `POST /candidates` → 候補者が保存され `CandidateOut` が返る → `DELETE /jobs/{id}` でその求人を消すと候補者も消える。
- Ollama 未起動／壊れた応答時に `POST /candidates/parse` がエラーコードを出し分ける（jobs と同じ挙動）。
- **LLM の構造化内容そのものの抽出精度は人の受け入れ確認で担保する**（自動テストはモックで通り道のみ検証）。

## スコープ外（やらないこと）

- **スコア算出・マッチング**（`Score` モデル / `evaluate_match` / `compute_total_score` / `MATCH_WEIGHT_*` / `POST /candidates` の `BackgroundTasks` 起動）。後続のマッチング issue。
- **結果確認系 API**（`GET /jobs/{id}/rankings` / `GET /candidates/{id}/detail`）。後続 issue。
- **候補者取り込み画面 frontend**・グローバルヘッダー（求人セレクター）。後続 issue。
- **候補者の保存後編集**（`PUT`/`PATCH /candidates/{id}` は作らない。削除のみ。求人と同方針）。
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API。

## 参考

- [docs/03_how/04_api.md](../docs/03_how/04_api.md) — `POST /candidates/parse` / `POST /candidates` / `DELETE /candidates/{id}` の契約（非同期スコア算出は後続）
- [docs/03_how/02_ai.md](../docs/03_how/02_ai.md) — `CandidateParseResult` のフィールド表・共通抽出ルール・プロンプト設計
- [docs/03_how/03_data-model.md](../docs/03_how/03_data-model.md) — `candidates` テーブル定義・カスケード削除方針
- [docs/03_how/06_testing.md](../docs/03_how/06_testing.md) — テスト方針（backend は pytest、Ollama モック）
- [backend/models.py](../backend/models.py) — `Job` モデル（踏襲元）／カスケード削除の素地コメント
- [backend/schemas.py](../backend/schemas.py) — `JobParseResult` / `JobCreate` / `JobOut`（踏襲元）
- [backend/services/llm.py](../backend/services/llm.py) — `structured_chat`（汎用基盤・再利用）／ LLM 例外
- [backend/services/structuring.py](../backend/services/structuring.py) — `structure_job`（踏襲元。`structure_candidate` の追加先）
- [backend/routers/jobs.py](../backend/routers/jobs.py) — router 実装パターン（踏襲元）
- [backend/db.py](../backend/db.py) — FK pragma 追加対象
- [backend/main.py](../backend/main.py) — `include_router` 追加対象
- [backend/tests/conftest.py](../backend/tests/conftest.py) / [backend/tests/test_jobs_api.py](../backend/tests/test_jobs_api.py) — テスト基盤・踏襲元
- [003-job-parse-backend.md](003-job-parse-backend.md) — 踏襲する直近の backend issue（done）
