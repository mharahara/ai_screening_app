# issue: ランキングページ求人タイトル表示・ホームページ改善

## ステータス

`done`

## 背景・目的

ランキングページ（`/jobs/[id]/rankings`）の h1 が「候補者ランキング」固定で、複数求人を扱う際にどの求人のランキングか URL を見ないと判断できない。求人タイトルをサブテキストに表示して一目でわかるようにする。また、ホームページ（`/`）が「準備中」のままで、初回起動時に何をすればいいかわからない。求人取り込み・候補者取り込みへのクイックリンクカードを設けてスタート画面として機能させる。

## 要件

**改善①: ランキングページに求人タイトルを表示**

- [ ] `backend/routers/jobs.py` に `GET /jobs/{job_id}` エンドポイントを追加する。レスポンスは既存の `JobSummary` スキーマ（`id`・`title`・`created_at`）を使う。存在しない `job_id` の場合は 404 を返す。
- [ ] `frontend/lib/jobs.ts` に `getJob(jobId: number): Promise<JobListItem>` 関数を追加する。
- [ ] `frontend/app/jobs/[id]/rankings/page.tsx` で `useQuery({ queryKey: ["job", jobId], queryFn: () => getJob(jobId) })` を追加し、h1「候補者ランキング」の下に求人タイトルを `<p>` で表示する。`title` が `null` の場合は「（無題）」と表示する。ローディング中・取得エラー時はタイトル行を非表示にする（ランキング本体の表示は継続する）。

**改善②: ホームページをスタート画面に改善**

- [ ] `frontend/app/page.tsx` を改修し、「準備中」テキストを削除して 2 枚のクイックリンクカードに置き換える。
  - カード①: アイコン＋「求人取り込み」＋「求人票を貼り付けてAIで構造化・保存する」→ `/jobs/new` へリンク
  - カード②: アイコン＋「候補者取り込み」＋「応募書類を貼り付けてAIで構造化・保存する」→ `/candidates/new` へリンク
- [ ] カード UI は Tailwind CSS で自前実装（`rounded-lg border p-6` 等）。shadcn/ui の card は追加しない。
- [ ] アイコンは `lucide-react`（既インストール済み）から選ぶ。
- [ ] 「RabbitPick」h1 とサブタイトルは残す。

## 対象レイヤー

- [x] backend（`GET /jobs/{job_id}` エンドポイント追加）
- [x] frontend（ランキングページ・ホームページ改修）

## 受け入れ条件（Definition of Done）

**backend:**
- [ ] `ruff check` がエラーなし。
- [ ] `ruff format` 後に差分なし。
- [ ] `mypy .` がエラーなし。
- [ ] `pytest` が全件 pass。`GET /jobs/{job_id}` の正常系（レスポンスフィールドが `id / title / created_at` のみであることをフィールドセットで検証）・404 系（存在しない id）のテストを追加する。

**frontend:**
- [ ] `npm run lint` がエラーなし。
- [ ] `npm run build` がエラーなし。
- [ ] `npm run test` が全件 pass。
- [ ] `frontend/test/rankings-page.test.tsx` に求人タイトル表示テストを追加する。`server.use(http.get(\`${API_BASE_URL}/jobs/${jobId}\`, ...))` で MSW モックを追加し、タイトルが表示されること・`null` 時に「（無題）」が表示されることを検証する。既存テストは変更しない。
- [ ] `frontend/test/home-page.test.tsx` を新規追加する。2 枚のカードが `getByRole("link")` で取得でき、各 `href` が `/jobs/new`・`/candidates/new` であることを検証する。

## 確認したい受け入れシナリオ

- ランキングページ（`/jobs/[id]/rankings`）を開くと、h1「候補者ランキング」の下に求人タイトルが表示される。
- 求人タイトルが `null` の場合、「（無題）」と表示される。
- ホームページ（`/`）を開くと、「求人取り込み」「候補者取り込み」の 2 枚のカードが表示される。
- 各カードをクリックすると対応ページへ遷移する。
- 既存のランキング表示・候補者詳細ダイアログ・削除機能・求人一覧ページが従来通り動作する。

## スコープ外（やらないこと）

- ホームページへの統計情報（登録済み求人数・候補者数）の表示
- shadcn/ui card コンポーネントの追加インストール
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API / 求人の保存後編集（CLAUDE.md「やらないこと」）

## 参考

- [`../backend/routers/jobs.py`](../backend/routers/jobs.py) — `GET /jobs/{job_id}` を追加する対象
- [`../backend/schemas.py`](../backend/schemas.py) — `JobSummary` スキーマ（L209〜216）
- [`../docs/03_how/04_api.md`](../docs/03_how/04_api.md) — 新エンドポイント追加後に更新が必要
- [`../frontend/app/jobs/[id]/rankings/page.tsx`](../frontend/app/jobs/[id]/rankings/page.tsx) — 改修対象（h1 部分 L67〜70）
- [`../frontend/app/page.tsx`](../frontend/app/page.tsx) — 改修対象
- [`../frontend/lib/jobs.ts`](../frontend/lib/jobs.ts) — `listJobs` の実装を参考に `getJob` を追加
- [`../frontend/components/global-header.tsx`](../frontend/components/global-header.tsx) — ナビリンクのラベル参照
- [`../frontend/test/rankings-page.test.tsx`](../frontend/test/rankings-page.test.tsx) — テスト追加先
