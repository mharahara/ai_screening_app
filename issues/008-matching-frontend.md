# issue: マッチング frontend（ランキング画面・詳細ダイアログ・ランキング誘導ボタン）

## ステータス

`open`

## 背景・目的

issue007（マッチング backend）が公開する `GET /jobs/{id}/rankings` と `GET /candidates/{id}/detail` を frontend で消費し、候補者スコアのランキング画面を実装する。スコアはバックグラウンド算出されるため TanStack Query のポーリングで完了を検知する。これによりシステムの全主要機能（求人登録 → 応募書類登録 → スコアリング → 結果確認）がブラウザから一貫して使える状態になる。

## 要件

### API クライアント層（`frontend/lib/rankings.ts` 新規作成）

- [ ] 以下の型を定義する:
  - `RequirementCheck`: `{ requirement: string; status: "充足" | "未充足"; evidence: string | null }`
  - `ScoreOut`: `{ id: number; candidate_id: number; total_score: number; skill_score: number; experience_score: number; industry_score: number; position_score: number; required_met: number; required_total: number; requirement_checks: RequirementCheck[]; strengths: string; concerns: string; interview_points: string; scored_at: string }`
  - `CandidateRankingItem`: `{ candidate_id: number; name: string; created_at: string; total_score: number | null; skill_score: number | null; experience_score: number | null; industry_score: number | null; position_score: number | null; required_met: number | null; required_total: number | null }`
  - `CandidateDetailOut`: `{ id: number; job_id: number; name: string; age: number | null; nearest_station: string | null; desired_rate: number | null; experience_years: number | null; skills: string[]; certifications: string[]; work_history: string | null; education: string | null; self_pr: string | null; raw_text: string; created_at: string; score: ScoreOut | null }`（`lib/candidates.ts` の `CandidateOut` フィールドに `raw_text` と `score` を加えた構成）
- [ ] `listRankings(jobId: number): Promise<CandidateRankingItem[]>` を実装する（`apiFetch` を使用、`GET /jobs/{jobId}/rankings`）
- [ ] `getCandidateDetail(candidateId: number): Promise<CandidateDetailOut>` を実装する（`apiFetch` を使用、`GET /candidates/{candidateId}/detail`）

### UI コンポーネント追加

- [ ] `frontend/components/ui/dialog.tsx` を新規作成する（`@base-ui/react/dialog` を `alert-dialog.tsx` と同じパターンでラップする。ヘッダー・ボディ・クローズボタンを含む汎用 Dialog コンポーネント）
- [ ] `frontend/components/ui/tabs.tsx` を新規作成する（`@base-ui/react/tabs` をラップした Tab / TabList / TabPanel コンポーネント）

### ランキングページ（`frontend/app/jobs/[id]/rankings/page.tsx` 新規作成）

- [ ] URL パラメータ `id`（job_id）を使い `listRankings(jobId)` を `useQuery` で取得する
- [ ] スコア未算出候補者（`total_score === null`）が1件以上存在する間は `refetchInterval: 3000` でポーリングする。全員のスコアが確定したら `refetchInterval: false` に切り替えてポーリングを停止する
- [ ] 一覧は `total_score` 降順で表示する（backend のレスポンス順に依存）。スコアが null の行は末尾に表示される
- [ ] スコア算出済み行: total_score / skill_score / experience_score / industry_score / position_score / 必須充足（required_met / required_total）を表示し「詳細」ボタンを有効化する
- [ ] スコア未算出行: スコア欄に「算出中...」テキストを表示し「詳細」ボタンを無効化（disabled）する
- [ ] 「詳細」ボタン押下で当該候補者の詳細ダイアログを開く
- [ ] job_id が 404 のとき（`ApiError.status === 404` または `listRankings` が 404 を返したとき）Next.js の `notFound()` を呼ぶ

### 詳細ダイアログ（ランキングページ内コンポーネント）

- [ ] `getCandidateDetail(candidateId)` を `useQuery` で取得し（`enabled: !!candidateId`）、`dialog.tsx` を使用して表示する
- [ ] 以下の4タブ構成で実装する（`tabs.tsx` を使用）:
  - **基本プロフィール**: 氏名・年齢・最寄り駅・希望単価・経験年数・スキル・資格・学歴（`docs/02_what.md` の仕様に準拠）
  - **スコア根拠**: RequirementCheck 一覧（requirement / status（「充足」「未充足」カラーバッジ）/ evidence）
  - **AIサマリー**: strengths（強み）/ concerns（懸念点）/ interview_points（確認すべき点）
  - **応募書類**: raw_text をプレーンテキストで表示（`<pre>` タグ等）
- [ ] score が null（未算出）のときはスコア根拠・AIサマリータブに「スコア算出中です」を表示する

### 「ランキングを見る」誘導ボタン（`frontend/app/candidates/new/page.tsx` 修正）

- [ ] `createMutation` の `onSuccess(data)` で `data.job_id` を `savedJobId` state（`useState<number | null>(null)`）に保存する。既存の `setSelectedJobId(null)` より前に実行する
- [ ] 候補者保存成功後（`saveSuccess === true`）に `Link` ボタン「ランキングを見る」を追加する。`href` は `/jobs/${savedJobId}/rankings`
- [ ] `candidates-new-page.test.tsx` に「保存成功後にランキングへの正しい job_id つきリンクが表示される」ケースを追加する

### テスト

- [ ] `frontend/test/rankings.test.ts` を新規作成する: `listRankings()` / `getCandidateDetail()` の MSW 契約テスト（スコア算出済み・未算出 null フィクスチャの両方）
- [ ] `frontend/test/rankings-page.test.tsx` を新規作成する:
  - スコア算出済み候補者がスコア付きで表示される
  - スコア未算出候補者の行に「算出中...」が表示され「詳細」ボタンが disabled
  - 「詳細」ボタン押下で詳細ダイアログが開き、4タブが描画される
  - job_id が 404 のとき `notFound()` が呼ばれる（`vi.mock('next/navigation', () => ({ notFound: vi.fn() }))` でモックしてコールを確認する）

## 対象レイヤー

- [ ] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `cd frontend && npm run lint` / `npm run build` がすべて通る
- [ ] `GET /jobs/{id}/rankings` のレスポンスをもとに候補者がスコア降順で一覧表示される（テストで担保）
- [ ] スコア未算出候補者の行に「算出中...」が表示され詳細ボタンが無効化される（テストで担保）
- [ ] 詳細ダイアログが4タブ（基本プロフィール / スコア根拠 / AIサマリー / 応募書類）で開く（テストで担保）
- [ ] 未算出のときスコア根拠・AIサマリータブに「スコア算出中です」が表示される（テストで担保）
- [ ] 候補者保存完了後に正しい job_id を持つ「ランキングを見る」リンクボタンが表示される（テストで担保）
- [ ] 存在しない job_id で `notFound()` が呼ばれる（`vi.mock('next/navigation')` によりテストで担保）

## 確認したい受け入れシナリオ

- 求人を作成し、候補者を登録した後 `/jobs/{id}/rankings` にアクセスすると候補者一覧が表示される
- スコア算出中は「算出中...」が表示され、数秒後（ポーリング）にスコアが反映される
- 「詳細」ボタンを押すとダイアログが開き、スコア根拠（RequirementCheck 一覧）・AIサマリー・応募書類原文が確認できる
- 応募書類登録完了後に「ランキングを見る」ボタンを押すと当該求人のランキングページへ遷移する
- 既存導線（求人登録・応募書類登録）が引き続き正常に動作する

## スコープ外（やらないこと）

- ランキング画面からの候補者削除（候補者削除は `candidates/new` ページで行う）
- グローバルヘッダー（求人セレクター + ナビゲーションリンク）の実装
- 詳細ダイアログを表示中にバックグラウンドのスコア算出が完了した場合のリアルタイム更新（ダイアログを閉じて再度開くと反映される）
- CLAUDE.md 記載のスコープ外事項（認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 求人の保存後編集）

## 参考

- API 定義: [`../docs/03_how/04_api.md`](../docs/03_how/04_api.md)
- UI 仕様: [`../docs/02_what.md`](../docs/02_what.md)
- 既存 API クライアント: [`../frontend/lib/api.ts`](../frontend/lib/api.ts) / [`../frontend/lib/candidates.ts`](../frontend/lib/candidates.ts)（`CandidateOut` フィールド参照）
- 既存 UI コンポーネント: [`../frontend/components/ui/alert-dialog.tsx`](../frontend/components/ui/alert-dialog.tsx)（dialog/tabs の実装パターン参考）
- 既存ページ実装: [`../frontend/app/candidates/new/page.tsx`](../frontend/app/candidates/new/page.tsx)（修正対象 / `savedJobId` 追加先）
- QueryProvider: [`../frontend/components/query-provider.tsx`](../frontend/components/query-provider.tsx)（ポーリング設計方針のコメント）
- 依存 issue: [`007-matching-backend.md`](007-matching-backend.md)（本 issue の着手前に完了が必要）
- テスト参考: [`../frontend/test/jobs.test.ts`](../frontend/test/jobs.test.ts) / [`../frontend/test/candidates-new-page.test.tsx`](../frontend/test/candidates-new-page.test.tsx)
