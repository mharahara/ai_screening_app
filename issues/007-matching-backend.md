# issue: マッチング backend（スコア算出・rankings API・detail API）

## ステータス

`open`

## 背景・目的

候補者登録後にスコアが算出されないと、ランキング画面で候補者を比較できない。`POST /candidates` 保存と同時に BackgroundTasks でマッチングスコアを LLM が多軸評価し、スコアを DB に保存する。`GET /jobs/{id}/rankings` でスコア降順の候補者一覧を返し、`GET /candidates/{id}/detail` で詳細データを返すことで、次の frontend issue がランキング画面を実装できる状態にする。

## 要件

- [ ] `Score` SQLAlchemy モデルを `models.py` に追加する（テーブル: scores）。カラム: id / candidate_id（FK → candidates.id, ON DELETE CASCADE）/ total_score（int）/ skill_score（int）/ experience_score（int）/ industry_score（int）/ position_score（int）/ required_met（int: 充足件数）/ required_total（int: 全件数）/ requirement_checks（JSON カラム: RequirementCheck 相当の dict のリスト）/ strengths / concerns / interview_points / scored_at（DateTime with timezone）。`Candidate` に `score` relationship（`uselist=False`、`cascade="all, delete-orphan"`）を追加する
- [ ] `docs/03_how/03_data-model.md` の `scores` テーブル定義を「必須充足率（1カラム）」から `required_met`（充足件数）+ `required_total`（全件数）の2カラム表記に更新する
- [ ] `schemas.py` に以下を追加する:
  - `RequirementStatus`（StrEnum: `充足` / `未充足`）
  - `RequirementCheck`（`requirement: str`必須 / `status: RequirementStatus`必須 / `evidence: str | None`Optional）
  - `MatchResult`（LLM 出力用）: `skill_score: int = Field(ge=0, le=100)` / `experience_score: int = Field(ge=0, le=100)` / `industry_score: int = Field(ge=0, le=100)` / `position_score: int = Field(ge=0, le=100)` / `requirement_checks: list[RequirementCheck]`（必須・空配列可）/ `strengths: str` / `concerns: str` / `interview_points: str`
  - `ScoreOut`（Score モデルの出力用スキーマ: 全フィールド）
  - `CandidateRankingItem`（ランキング一覧1行: candidate_id / name / created_at / total_score? / skill_score? / experience_score? / industry_score? / position_score? / required_met? / required_total?）
  - `CandidateDetailOut`（プロフィール全フィールド + `score: ScoreOut | None` + `raw_text`）
- [ ] `services/matching.py` を新規作成し、以下の関数を実装する:
  - `evaluate_match(job: Job, candidate: Candidate) -> MatchResult`: マッチング用 system/user プロンプトを構築し `structured_chat()` を呼ぶ。Pydantic バリデーション失敗（スコア範囲・型不正）または `requirement_checks` 件数が `len(job.required_skills)` と不一致の場合はフィードバック付きで最大 `PARSE_MAX_RETRIES` 回リトライする独自ループを持つ。上限超過時は `ParseFailedError` を送出する
  - `compute_total_score(result: MatchResult, weights: dict) -> int`: 4軸スコアを重み付け平均（重みは合計1.0に正規化）し、四捨五入した 0〜100 の整数を返す（純粋関数）
  - `match_candidate(candidate_id: int) -> None`: 内部で `SessionLocal()` を生成してセッション管理する。candidate と job を取得 → `evaluate_match` → `compute_total_score` → 必須充足率（`required_met` / `required_total`）算出 → scores を candidate_id 単位で upsert。`ParseFailedError` / `LLMTimeoutError` / `LLMUnavailableError` / DB エラーを含む全例外をキャッチしてログ出力し、例外を伝播させない。リトライ上限超過時はスコアを保存しない。candidate が存在しない場合は何もせず正常終了する
- [ ] `config.py` に重み設定を追加: `MATCH_WEIGHT_SKILL=0.40` / `MATCH_WEIGHT_EXPERIENCE=0.20` / `MATCH_WEIGHT_INDUSTRY=0.20` / `MATCH_WEIGHT_POSITION=0.20`（`.env` で可変、コード側で合計1.0に正規化）
- [ ] `routers/candidates.py` の `create_candidate` に `BackgroundTasks` を引数追加し、`match_candidate(candidate.id)` をバックグラウンド登録する。ルーターは即 `201 Created` を返す
- [ ] `routers/jobs.py` に `GET /jobs/{id}/rankings` を追加する。存在しない job_id は 404。指定 job_id に紐づく全候補者（スコア未算出を含む）を total_score 降順（null は末尾）で返す。レスポンスは `list[CandidateRankingItem]`（未算出はスコア系フィールドが null）
- [ ] `routers/candidates.py` に `GET /candidates/{id}/detail` を追加する。存在しない candidate_id は 404。`CandidateDetailOut`（プロフィール + score | null + raw_text）を返す
- [ ] テストを追加する:
  - `compute_total_score` の純粋関数テスト（重み正規化・重み付け平均の数値検証）
  - `evaluate_match` の通り道テスト（`_RecordingStructuredChat` パターンでプロンプト構築確認・`requirement_checks` 件数不一致でリトライされること）
  - `match_candidate` のスコア算出→DB 保存テスト（LLM をモック）
  - `match_candidate` のリトライ上限超過時・`LLMUnavailableError` 時にスコアが保存されず例外がリークしないこと
  - `POST /candidates` の TestClient 実行後（BackgroundTasks が同期実行される）に `scores` テーブルにレコードが保存されていること（LLM はモック）
  - `GET /jobs/{id}/rankings` のスコア降順・未算出候補者が null で末尾に含まれること・存在しない job_id は 404
  - `GET /candidates/{id}/detail` のスコア有/無両方・存在しない candidate_id は 404

## 対象レイヤー

- [x] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [ ] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `cd backend && uv run ruff check` / `uv run ruff format --check` / `uv run mypy .` / `uv run pytest` がすべて通る（LLM は全テストでモック化）
- [ ] `Score` モデルが `create_all` で自動生成され、candidate 削除時にカスケード削除される（テストで担保）
- [ ] `POST /candidates` の TestClient 実行後に `scores` テーブルに1行保存される（テストで担保）
- [ ] `GET /jobs/{id}/rankings` がスコア算出済み候補者をスコア降順で返し、未算出候補者は total_score=null で末尾に含まれる（テストで担保）
- [ ] `GET /candidates/{id}/detail` が候補者プロフィール＋スコア（未算出時は null）＋ raw_text を返す（テストで担保）
- [ ] LLM リトライ上限超過時・`LLMUnavailableError` 時に scores テーブルにレコードが残らない（テストで担保）
- [ ] `compute_total_score` の重み付け平均の数値が単体テストで検証されている
- [ ] 存在しない job_id / candidate_id への 404 がテストで担保されている

## 確認したい受け入れシナリオ

- backend のみの変更のため curl による API 動作確認で代替（ブラウザ観測なし）
- curl で `POST /candidates` → 少し待って `GET /jobs/{id}/rankings` を叩くとスコア降順で候補者が返る
- スコア未算出の候補者は null スコアで含まれる（ポーリングで検知可能）
- `GET /candidates/{id}/detail` でプロフィール・スコア根拠・サマリー・raw_text が取得できる

## スコープ外（やらないこと）

- frontend 実装（ランキング画面・詳細ダイアログ・ポーリング）は後続 issue
- スコア算出のトリガーは `POST /candidates` のみ（再実行 API は設けない）
- BackgroundTasks の失敗をフロントに通知する仕組み（ポーリングで未算出を検知する方針）
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 求人の保存後編集（CLAUDE.md 共通）

## 参考

- `../backend/models.py` — Job / Candidate モデル（Score モデルを追加する）
- `../backend/schemas.py` — 末尾コメントに「マッチング（Score）のスキーマは後続 issue で追加する」
- `../backend/routers/candidates.py` — `create_candidate` の BackgroundTasks コメント（87行目）
- `../backend/services/llm.py` — `structured_chat` 汎用関数（マッチングで再利用）
- `../backend/services/structuring.py` — `evaluate_match` 実装の参考パターン（system プロンプト定数 + `_build_*_user_prompt` 関数構成）
- `../backend/tests/conftest.py` — `_no_real_ollama` fixture・`get_db` 差し替えパターン
- `../backend/tests/test_structuring.py` — `_RecordingStructuredChat` パターン
- `../backend/tests/test_llm.py` — `FakeChat` パターン
- `docs/03_how/02_ai.md` — マッチングの詳細仕様（スキーマ・プロンプト設計・堅牢化・処理フロー）
- `docs/03_how/03_data-model.md` — scores テーブル定義（本 issue で更新対象）
- `docs/03_how/04_api.md` — API エンドポイント一覧
