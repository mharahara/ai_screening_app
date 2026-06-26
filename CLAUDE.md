# RabbitPick

AIエンジニア採用スクリーニングシステム。「エンジニア選考をより早く軽やかに」。

フリーランスエンジニアの応募書類（職務経歴書・履歴書等）の生テキストを Ollama が構造化し、求人要件とのマッチ度を 0〜100 点でスコアリングして候補者をランキングする。**個人利用・ローカル単一ユーザ前提**で、認証・マルチユーザ・スケーリングは対象外。

## 技術スタック

- **バックエンド**: FastAPI（Python） / SQLAlchemy / Pydantic / pydantic-settings。パッケージ管理は **uv**（`uv sync` / `uv run ...`、`pip` を直叩きしない）。Lint/Format は **Ruff**、型は **mypy**、テストは **pytest**。
- **フロントエンド**: Next.js（App Router） / React / TypeScript / Tailwind CSS / shadcn/ui。データ取得は **TanStack Query**（スコア算出完了のポーリングに利用）。Lint は ESLint、整形は Prettier。パッケージ管理は **npm**。
- **AI**: LLM provider は `LLM_PROVIDER` 環境変数で切り替える（構造化・マッチングとも一括）。
  - `ollama`（デフォルト）: **Ollama（ローカル）** のモデル `gemma4:e4b`。**ollama 公式 Python SDK** で `format` に JSON Schema を指定。Ollama は `localhost:11434` で常駐前提。
  - `claude`: **Claude（Anthropic API）** のモデル `claude-opus-4-8`。**anthropic 公式 Python SDK** で `output_config.format` に JSON Schema を指定。`ANTHROPIC_API_KEY` が必要（API キー・通信コストが発生する）。
  - provider 差分は [backend/services/llm.py](backend/services/llm.py) の provider 実装に閉じ込め、検証 + リトライの共通ループは provider 非依存。

## 主要機能・処理フロー

1. **求人要件登録**: 生テキスト → `POST /jobs/parse`（LLM 構造化）→ 編集 → `POST /jobs` で保存。保存後の編集は不可、削除は可。
2. **応募書類登録**: 生テキスト → `POST /candidates/parse`（LLM 構造化）→ 編集 → `POST /candidates` で保存。保存と同時にマッチングスコア算出をバックグラウンド起動。
3. **マッチング**: 候補者 × 求人を LLM が多軸評価・必須要件チェック・サマリー生成し、スコアを保存。
4. **結果確認**: `GET /jobs/{id}/rankings` でスコア降順の候補者一覧を取得・表示（一覧＋詳細ダイアログ）。

## やらないこと（スコープ外）

認証 / マルチユーザ / Docker / Alembic（マイグレーション。テーブルは起動時 `create_all`）/ PostgreSQL（SQLite のみ）。

LLM は **Ollama（ローカル・デフォルト）** または **Claude（Anthropic API）** を `LLM_PROVIDER` で選択する。`claude` 選択時は API キー・通信コストが発生する（個人利用・ローカル単一ユーザという前提自体は変わらない）。

## ドキュメント

プロジェクトのドキュメントは `docs/` 配下にあります。各ドキュメントの一覧と内容は索引 [docs/00_index.md](docs/00_index.md) を参照してください。
