# issue: 求人・候補者取り込み画面にスケルトンローダーを追加

## ステータス

`done`

## 背景・目的

求人要件・候補者書類の取り込み画面でLLMによる構造化処理中、右パネルが空白のまま何も表示されない。処理が進んでいることをユーザーが把握できず、待機中に操作を中断したり混乱するケースがある。処理中はフィールドのラベルを表示しスケルトンバーを添えることで、何が処理されているかを視覚的に伝え、体験を改善する。

## 要件

- [ ] `frontend/app/jobs/new/page.tsx`: `parseMutation.isPending === true` かつ `hasParsed === false` のとき、右パネルに各フィールドのラベル（「タイトル」「業務内容」等）を実テキストで表示し、値が入る箇所にスケルトンバーを表示する
- [ ] `frontend/app/jobs/new/page.tsx`: `parseMutation.isPending === true` かつ `hasParsed === true`（再構造化中）のときは既存のフォームを維持したまま変更しない（スケルトンへの切り替えは行わない）
- [ ] `frontend/app/candidates/new/page.tsx`: LLM出力フィールド（`name`・`age`・`nearest_station`・`desired_rate`・`experience_years`・`skills`・`certifications`・`work_history`・`education`・`self_pr`）に同様のスケルトン表示を追加する。「対象求人」セレクターはLLM出力ではないためスケルトン対象外とし、処理中も通常表示を維持する
- [ ] `frontend/app/candidates/new/page.tsx`: `hasParsed === true` かつ `isPending === true` のときは既存フォームを維持する（jobs/new と同様）
- [ ] shadcn/ui の Skeleton コンポーネントを `frontend/components/ui/skeleton.tsx` として追加する
- [ ] `npm run lint` と `npm run build` が通る

## 対象レイヤー

- [ ] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [x] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `parseMutation.isPending === true` かつ `hasParsed === false` のとき、`jobs/new` 右パネルに各フィールドラベルとスケルトンバーが表示される
- [ ] `parseMutation.isPending === true` かつ `hasParsed === true` のとき、`jobs/new` 右パネルは既存フォームのままで、DOM上にSkeletonコンポーネントが描画されていない
- [ ] `candidates/new` でも同様にスケルトン表示が機能し、「対象求人」セレクターはスケルトン対象外である
- [ ] `cd frontend && npm run lint` がエラーなし
- [ ] `cd frontend && npm run build` が成功する

## 確認したい受け入れシナリオ

- `jobs/new` で左パネルにテキストを貼り付けて「構造化する」を押すと、処理中に右パネルにフィールドラベルとスケルトンバーが表示され、完了後に編集フォームに切り替わる
- `jobs/new` で一度構造化した後に再度「構造化する」を押すと、処理中も右パネルのフォームはスケルトンに切り替わらずそのまま維持される
- `candidates/new` でも同様の動作が確認でき、「対象求人」セレクターは処理中も通常表示のまま
- 既存の「構造化する」ボタン・保存フローに変化がない

## スコープ外（やらないこと）

- エラー状態（`parseMutation.isError`）の表示改善（別途対応）
- 初期状態（何も押していない状態）の右パネル表示変更
- バックエンドAPIの変更
- フロントエンドの自動テスト追加（既存テストなし）
- 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 求人の保存後編集

## 参考

- 変更対象: `frontend/app/jobs/new/page.tsx`（246〜430行: 右パネル状態分岐）
- 変更対象: `frontend/app/candidates/new/page.tsx`（同構造）
- shadcn/ui Skeleton 追加先: `frontend/components/ui/skeleton.tsx`
- 関連issue: `issues/004-job-parse-frontend.md`（求人取り込みフロントエンド実装）
- 関連issue: `issues/006-candidate-parse-frontend.md`（候補者取り込みフロントエンド実装）
