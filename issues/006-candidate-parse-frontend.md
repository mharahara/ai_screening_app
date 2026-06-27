# issue: 応募書類取り込み frontend を実装する

## ステータス

`done`

## 背景・目的

求人要件登録フロー（/jobs/new）は実装済みだが、応募書類登録フローの frontend がまだ存在しない。候補者の生テキスト（職務経歴書等）を貼り付け、LLM で構造化し、確認・編集して保存できる画面を作ることで、採用スクリーニングの入力作業を完結できる。

## 要件

- [ ] `frontend/lib/candidates.ts` を新規作成する。定義する内容:
  - 型: `CandidateParseResult`（構造化結果）・`CandidateParseResponse`（= `CandidateParseResult` + `raw_text`）・`CandidateCreate`・`CandidateOut`
  - API クライアント: `parseCandidate`（POST /candidates/parse、返り値 `CandidateParseResponse`）・`createCandidate`（POST /candidates）
- [ ] `frontend/app/candidates/new/page.tsx` を新規作成する。フローは以下の通り:
  1. 生テキスト貼り付け欄と parse ボタンを表示
  2. parse ボタン押下 → POST /candidates/parse → 編集フォームを表示
  3. 求人セレクター（useQuery で GET /jobs を呼び出し、取得した求人名のドロップダウン）で job_id を選択
  4. フォームフィールドを確認・編集: `name`（Input）、`age`（NumberField）、`experience_years`（NumberField）、`desired_rate`（NumberField）、`nearest_station`（Input）、`skills`（TagInput）、`certifications`（TagInput）、`work_history`（Textarea）、`education`（Textarea）、`self_pr`（Textarea）
  5. 保存ボタン押下 → POST /candidates → 成功メッセージ表示・フォームリセット
- [ ] parse エラー（PARSE_FAILED / LLM_TIMEOUT / LLM_UNAVAILABLE）は jobs/new の `parseErrorMessage` 関数と同一の文言出し分けロジックを `candidates/new/page.tsx` 内に複製して表示する（jobs/new は変更しない）。
- [ ] 求人セレクター: job_id 未選択状態では保存ボタンを disabled にする。GET /jobs が空配列のときは「先に求人を登録してください」を表示して保存ボタンを disabled にする。GET /jobs が失敗したときは「求人一覧の取得に失敗しました。」を表示する。
- [ ] POST /candidates が失敗したときは「保存に失敗しました。再試行してください。」を表示する。
- [ ] 保存後は候補者一覧を表示しない（成功メッセージのみ表示してフォームをリセット）。
- [ ] スコア算出のポーリング UI は実装しない。
- [ ] `frontend/test/candidates.test.ts`（lib/candidates.ts の API クライアント契約テスト）と `frontend/test/candidates-new-page.test.tsx`（画面テスト）を新規作成する。

## 対象レイヤー

- [ ] backend（変更なし）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query）

## 受け入れ条件（Definition of Done）

- [ ] `npm run lint` が通る
- [ ] `npm run build` が通る
- [ ] `npm run test`（vitest run）が全件パスする（jobs 既存テスト含む）
- [ ] `frontend/test/candidates.test.ts` が全件パスする（parseCandidate / createCandidate の API パス・ボディ・エラーコードを MSW でモック）
- [ ] `frontend/test/candidates-new-page.test.tsx` が全件パスする。網羅対象:
  - parse 失敗文言出し分け（PARSE_FAILED / LLM_TIMEOUT / LLM_UNAVAILABLE）
  - parse 成功 → フォームに全フィールドが反映される
  - 求人0件のとき「先に求人を登録してください」が表示される
  - GET /jobs 失敗のとき「求人一覧の取得に失敗しました。」が表示される
  - 求人選択 → job_id がセットされ保存ボタンが有効になる
  - 保存時に全フィールドが POST /candidates のボディに含まれる
  - 保存成功 → 成功メッセージ表示・フォームリセット
  - POST /candidates 失敗 → 「保存に失敗しました。再試行してください。」が表示される
- [ ] `lib/candidates.ts` の型が `backend/schemas.py` の `CandidateParseResult` / `CandidateCreate` / `CandidateOut` と整合している（目視確認）

## 確認したい受け入れシナリオ

- 既存の求人登録フロー（/jobs/new）が壊れていない（画面遷移・保存・削除が正常）
- `/candidates/new` を開くと生テキスト入力欄と parse ボタンが表示される
- 生テキストを貼って parse → 各フィールドに LLM 解析結果が反映される（LLM 応答の品質は人の目で確認）
- 求人ドロップダウンに登録済み求人が表示され、選択できる
- 全フィールド確認・編集後に保存すると成功メッセージが表示される
- parse エラー時に適切な文言が表示される

## スコープ外（やらないこと）

- 候補者の保存後編集（CLAUDE.md「やらないこと」に準拠）
- 候補者一覧表示・削除 UI（後続 issue に委譲）
- `deleteCandidate` API クライアントの定義（一覧・削除 UI が存在しないためこの issue では不要）
- スコア算出のポーリング UI（backend 未実装のため後続 issue に委譲）
- グローバルな求人選択状態の導入（ページローカルのドロップダウンで完結）
- backend の変更

## 参考

- [求人 frontend 参考実装](../frontend/app/jobs/new/page.tsx)
- [candidates API クライアント参考](../frontend/lib/jobs.ts)
- [共通 API 基盤](../frontend/lib/api.ts)
- [TagInput コンポーネント](../frontend/components/tag-input.tsx)
- [candidates backend（005）](../backend/routers/candidates.py)
- [candidates スキーマ](../backend/schemas.py)
- [frontend テスト参考](../frontend/test/jobs.test.ts)
- [frontend 画面テスト参考](../frontend/test/jobs-new-page.test.tsx)
