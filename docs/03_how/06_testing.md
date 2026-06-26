# テスト方針 (how)

RabbitPick のテストの**目的・対象・やり方**を定める。テストは「実装のついで」ではなく、**方針に沿って専門エージェント（test-builder-backend / test-builder-frontend）が書く独立工程**として扱う。

## 基本原則

- **個人利用・ローカル単一ユーザ前提**のプロジェクトなので、テストは**壊れやすい中核ロジックの回帰防止**に集中する。網羅率（カバレッジ100%）を目的にしない。
- **外部依存（Ollama）は実際に叩かない**。LLM 応答は不安定・モデル依存なので、必ずモックして固定の構造化結果を返させる。
- **LLM の応答内容そのものの良し悪しは検証対象外**（モデル依存で不安定）。検証するのは「構造化結果をどう処理するか」「ステータスがどう遷移するか」「API の入出力が契約どおりか」。
- テストは**決定的**であること。時刻・乱数・ネットワークに依存して落ちるテストを書かない。
- **既存テスト・既存導線を壊さない**。テスト追加時も全体を回してリグレッションがないことを確認する。

## backend（`backend/tests/`）

- フレームワークは **pytest**。非同期が要るなら `pytest-asyncio`。実行は `uv run pytest`。
- 配置は `backend/tests/` 配下。テストファイルは `test_*.py`、テスト関数は `test_*`。
- FastAPI のエンドポイントは `TestClient`（または `httpx.AsyncClient`）で叩く。DB は**テスト用の SQLite**（インメモリまたは一時ファイル）に差し替え、本番 DB を汚さない。

### 何をテストするか（優先順）

1. **ステータス遷移**: スコア算出の `pending → running → done`、および**失敗時に `failed` になること**。例外時に `pending` のまま放置されないことを必ず担保する。
2. **失敗系ハンドリング**: LLM 出力が壊れている（`ValidationError`）・接続例外のとき、握りつぶさずステータスが `failed` になり、例外がリークしないこと。
3. **API の入出力契約**: 各エンドポイントのステータスコード・レスポンス形が [04_api.md](04_api.md) の定義どおりか。求人が**保存後に編集できない（削除のみ）**こと。
4. **スコアの境界・欠損**: 0〜100 の範囲、null・候補者ゼロ件・スコア未算出（`done` でない）候補のランキング表示が破綻しないこと。
5. **構造化結果の処理**: `model_validate_json` で復元した結果が正しく保存・スコアリングに渡ること（応答内容の質ではなく**通り道**を見る）。

### Ollama のモック方針（厳守）

- LLM 呼び出しは `services/` の関数（または集約した client、例: `services/llm.py`）に**1箇所**で集約されている前提。テストはそこを **monkeypatch / モック**して固定の構造化結果・スコア結果を返させる。
- 正常系は「妥当な JSON を返す」モック、失敗系は「`ValidationError` を誘発する壊れた出力」「接続例外を投げる」モックを用意する。
- モデル名・URL・タイムアウトは `config.py`（pydantic-settings）由来。テストで固定値を散らかさず、必要なら設定をオーバーライドする。

## frontend（`frontend/`）

- ロジック層（`lib/` の API クライアント・hooks・スコア状態管理）を中心にテストする。**画面の見た目（CSS）はテスト対象にしない**。
- backend を実際に叩かず、**API をモック**して固定レスポンスを返させる。
- 実行・検証は `npm run lint && npm run build` を必ず通す（型・ビルドの健全性）。

### テストスタック（確定）

- **Vitest** — テストランナー。Vite ベースで TS/ESM をネイティブに扱い、設定が軽く速い。スクリプトは `npm run test`（CI 用に `vitest run`）。
- **@testing-library/react** + **@testing-library/jest-dom** — hooks・コンポーネントのロジック/状態を検証する（実装詳細でなく振る舞いを見る）。
- **MSW（Mock Service Worker）** — backend API は**ネットワーク層でモック**する。`vi.fn` で fetch を直接潰すのでなく MSW のハンドラで固定レスポンスを返すことで、型整合・契約を実物に近い形で検証する。
- **環境**: `jsdom`（`vitest.config.ts` の `test.environment`）。React のレンダリング・タイマーを扱うため。
- 上記が未導入なら、まず `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom msw` で導入し、`vitest.config.ts`・セットアップファイル（jest-dom 取り込み・MSW server の `beforeAll/afterEach/afterAll`）を用意する。**他のランナー（Jest 等）に勝手に乗り換えない**。

### ポーリングのテスト（要注意）

react-query の `refetchInterval` による算出ステータス監視は、**`vi.useFakeTimers()` でタイマーを制御して決定的にする**。フェイクタイマーと MSW・react-query を併用するときは、タイマーを進める（`vi.advanceTimersByTimeAsync`）と非同期の解決（`await`）の順序に注意する。実時間の `setTimeout` 待ちでテストを安定させようとしない。

### 何をテストするか（優先順）

1. **スコア完了ポーリング**: react-query の `refetchInterval` 等で算出ステータスを監視し、`done` で停止して結果を反映するロジック。途中（`pending`/`running`）と完了で表示が正しく切り替わること。
2. **型整合**: `lib/` の共有型（Job / Candidate / MatchResult・算出ステータス）が backend スキーマ（[03_data-model.md](03_data-model.md) / [04_api.md](04_api.md)）と対応していること。
3. **ランキング表示の破綻防止**: 候補者ゼロ件・スコア未算出・失敗（`failed`）のときに UI が壊れないこと。

## スコープ外（テストでもやらないこと）

- Ollama を実際に起動して応答を検証する E2E（モデル依存で不安定なため書かない）。
- 認証 / マルチユーザ前提のテスト（機能自体がスコープ外）。
- カバレッジ達成そのものを目的にしたテストの量産。
