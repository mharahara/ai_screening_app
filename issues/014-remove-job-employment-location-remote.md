# issue: 求人要件から「雇用形態・勤務地・リモート可否」を削除する

## ステータス

`done`

## 背景・目的

求人要件の「雇用形態（employment_type）・勤務地（location）・リモート可否（remote_work）」は候補者スクリーニングのスコアリング（評価軸・必須要件チェック）に使われておらず、選考判断上の重要度が低い。これらを構造化スキーマ・DB・LLM プロンプト・UI・docs から取り除き、入力・表示・マッチングプロンプトを簡素化する。あわせて、勤務地等を LLM がマッチング判定で参考にする余地をなくす。

## 要件

- [ ] backend: `JobParseResult`（schemas.py）から `employment_type` / `location` / `remote_work` を削除（継承する `JobCreate` / `JobOut` に連鎖）。
- [ ] backend: `EmploymentType` / `RemoteWork` enum クラス（schemas.py）を完全削除し、models.py の import 行からも除く。
- [ ] backend: `Job` モデル（models.py）から 3 カラムを削除。
- [ ] backend: `_JOB_SYSTEM_PROMPT`（services/structuring.py）から 3 フィールドの抽出指示を削除。
- [ ] backend: `_build_matching_user_prompt`（services/matching.py）の `job_data` dict から 3 キーを除く（評価軸・必須要件チェックは元々未使用のため評価ロジックは変えない）。
- [ ] frontend: `lib/jobs.ts` から `EmploymentType` / `RemoteWork` 型、`EMPLOYMENT_TYPES` / `REMOTE_WORKS` 定数、`JobParseResult` の 3 フィールドを削除。
- [ ] frontend: `app/jobs/new/page.tsx` の form 初期値から 3 フィールドを除き、雇用形態・リモート可否の `EnumSelect`・勤務地の `Input` を削除。残る `position_level` のグリッドレイアウトを単列基調に調整。
- [ ] frontend: `app/jobs/[id]/rankings/page.tsx` の求人詳細アコーディオンから該当 `JobField` 表示 3 件を削除。
- [ ] backend テスト追随: `test_db_models.py`（EmploymentType / RemoteWork の import・使用・アサート）、`test_jobs_api.py` の `_VALID_PARSE` / `_VALID_JOB_PAYLOAD` フィクスチャ、enum 範囲外→422 テスト、3 フィールドのレスポンス検証テストを更新・削除。
- [ ] frontend テスト追随: `test/jobs.test.ts`・`test/jobs-new-page.test.tsx` の 3 フィールド参照（`employment_type` / `location` / `remote_work` のテストデータ、`createBody?.employment_type` 等の検証）を削除・更新。
- [ ] docs 更新: `docs/02_what.md`・`docs/03_how/02_ai.md`・`docs/03_how/03_data-model.md` から 3 フィールドの記述を除く。

## 対象レイヤー

- [x] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] backend で `ruff check` / `ruff format` / `mypy .` / `pytest` が通る（Ollama 呼び出しはモック化）。
- [ ] frontend で `lint` / `build` / `npm run test`（vitest）が通る。
- [ ] `GET /jobs/{id}` / `POST /jobs` / `POST /jobs/parse` のリクエスト・レスポンスに 3 フィールドが含まれない。
- [ ] `test_jobs_api.py` の「enum 範囲外を送ると 422」テスト・3 フィールドのレスポンス検証が除去され、フィクスチャ（`_VALID_PARSE` / `_VALID_JOB_PAYLOAD`）も追随済み。frontend テストも 3 フィールド参照が残っていない。
- [ ] docs 3 ファイルに「雇用形態 / 勤務地 / リモート可否」「employment_type / location / remote_work / EmploymentType / RemoteWork」の記述が残っていない。
- [ ] 開発環境の SQLite DB ファイル（`*.db`）を削除して再起動後、エラーなく起動でき、求人の登録・保存ができる。

## 確認したい受け入れシナリオ

- /jobs/new で雇用形態・勤務地・リモート可否の入力欄が表示されず、残るフィールド（position_level 等）のレイアウトが崩れていない。生テキストから parse → 編集 → 保存まで通る。
- /jobs/{id}/rankings の求人詳細アコーディオンに 3 フィールドが表示されない。候補者のマッチングスコアが従来どおり算出・表示される。

## スコープ外（やらないこと）

- 候補者（Candidate）側の `nearest_station` 等のフィールド削除（今回は Job 側のみ）。
- 本番運用向けの DB マイグレーション（Alembic 不使用。開発 DB は手動削除で対応）。
- 認証 / マルチユーザ / Docker / PostgreSQL / 求人の保存後編集。

## 参考

- [../backend/schemas.py](../backend/schemas.py)（EmploymentType: 20–27 / RemoteWork: 30–36 / JobParseResult: 81–95）
- [../backend/models.py](../backend/models.py)（import: 19 / Job カラム: 39–41）
- [../backend/services/structuring.py](../backend/services/structuring.py)（_JOB_SYSTEM_PROMPT: 44–47）
- [../backend/services/matching.py](../backend/services/matching.py)（_build_matching_user_prompt: 69–71）
- [../backend/tests/test_db_models.py](../backend/tests/test_db_models.py) / [../backend/tests/test_jobs_api.py](../backend/tests/test_jobs_api.py)
- [../frontend/lib/jobs.ts](../frontend/lib/jobs.ts)（型・定数・interface: 11–61）
- [../frontend/app/jobs/new/page.tsx](../frontend/app/jobs/new/page.tsx)（form 初期値: 96–98 / 入力 UI: 471–545）
- [../frontend/app/jobs/[id]/rankings/page.tsx](../frontend/app/jobs/[id]/rankings/page.tsx)（JobField: 137–139）
- [../frontend/test/jobs.test.ts](../frontend/test/jobs.test.ts) / [../frontend/test/jobs-new-page.test.tsx](../frontend/test/jobs-new-page.test.tsx)
- [../docs/02_what.md](../docs/02_what.md) / [../docs/03_how/02_ai.md](../docs/03_how/02_ai.md) / [../docs/03_how/03_data-model.md](../docs/03_how/03_data-model.md)
