# issue: 保存済み求人の要件確認パネルをランキングページに追加

## ステータス

`done`

## 背景・目的

求人を登録した後、保存済みの詳細要件（スキル・経験年数・雇用形態等）を後から確認する手段がない。ランキングページで候補者を選考する際に要件を参照できないため、別途メモ等を見る必要がある。ランキングページに求人要件の確認パネルを追加し、選考作業を一画面で完結できるようにする。

## 要件

- [ ] `GET /jobs/{job_id}` の `response_model` を `JobSummary` から `JobOut` に変更し、全フィールドを返す
- [ ] `frontend/lib/jobs.ts` の `getJob()` 関数の戻り値型を `JobListItem` から `JobOut` に変更する
- [ ] ランキングページ（`/jobs/[id]/rankings`）の上部に求人要件確認パネルを追加する（折りたたみ可能）
- [ ] パネルには以下の `JobOut` 構造化フィールドを表示する: `title` / `description` / `required_skills` / `preferred_skills` / `ideal_profile` / `employment_type` / `location` / `remote_work` / `rate_min` / `rate_max` / `min_experience_years` / `position_level` / `industry_experience` / `certifications`
- [ ] `raw_text`（原文）はパネル内に「原文を見る」ボタンを設置し、クリックするとモーダルダイアログで表示する（shadcn/ui の `Dialog` を利用）
- [ ] パネルおよびダイアログは読み取り専用で、編集 UI は一切含まない
- [ ] `null` フィールドは「未記載」と表示する（行を省略しない）。既存の `Field` コンポーネントは流用せず、新規コンポーネントとして実装するか、null ラベルを props で渡せるよう拡張して「未記載」を指定する

## 対象レイヤー

- [x] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query）

## 受け入れ条件（Definition of Done）

- [ ] `GET /jobs/{job_id}` が `JobOut` の全フィールドを返す。`backend/tests/test_jobs_api.py` の `test_get_job_returns_summary_fields` を修正し、レスポンスキーが `JobOut` の全フィールドと完全一致すること、および `raw_text` フィールドが含まれることをアサートする
- [ ] `ruff check` / `ruff format` / `mypy .` / `pytest` がすべて通る
- [ ] `npm run lint` / `npm run build` がすべて通る
- [ ] ランキングページで求人要件パネルが表示される（初期状態は展開済み・折りたたみ済みいずれでもよい）
- [ ] パネルの開閉操作が動作し、折りたたみ状態でもランキング一覧が表示される
- [ ] `null` フィールドは「未記載」と表示される
- [ ] 「原文を見る」ボタンをクリックするとモーダルダイアログが開き、`raw_text` の全文が表示される

## 確認したい受け入れシナリオ

- 求人を登録後、ランキングページ（`/jobs/[id]/rankings`）に遷移すると、ページ上部に求人要件パネルが表示される
- パネルに必須スキル・歓迎スキル・経験年数・説明文等の構造化フィールドが正しく表示される
- 「原文を見る」ボタンをクリックするとモーダルダイアログが開き、登録時の原文テキストが表示される。ダイアログを閉じるとパネルに戻る
- パネルを折りたたむと候補者ランキング一覧が広く表示される
- 既存のランキング一覧・詳細ダイアログの動作に変化がない
- 候補者登録・スコアリング等の既存導線が壊れていない

## スコープ外（やらないこと）

- 求人の編集（保存後の変更）
- 求人の新規登録フロー（既存の `/jobs/new` フローは変更しない）
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL

## 参考

- `../backend/routers/jobs.py` — `GET /jobs/{job_id}` エンドポイント（`response_model=JobSummary` を変更）
- `../backend/schemas.py` — `JobOut`（128行目）・`JobSummary`（209行目）・`JobParseResult`（49〜120行目）
- `../backend/tests/test_jobs_api.py` — `test_get_job_returns_summary_fields`（275行目）要修正
- `../frontend/lib/jobs.ts` — `JobOut` 型（77行目）・`getJob()` 関数（113行目、呼び出し元は現在 `rankings/page.tsx` のみ）
- `../frontend/app/jobs/[id]/rankings/page.tsx` — 変更対象のランキングページ（既存 `Field` コンポーネント: 331行目）
- `../issues/010-job-list-ranking-link.md` — 求人一覧と UI 配置の関連 issue
