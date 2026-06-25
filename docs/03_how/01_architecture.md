# 構成・技術スタック (how)

## 構成

* フロントエンド：ユーザに UI を提供
* バックエンド：フロントへ API 提供 / データ保存 / AI 連携
* AI：応募書類・求人要件の構造化、マッチングスコア算出、サマリー生成を担う

```
[ブラウザ] ──HTTP──> [フロントエンド (Next.js)] ──REST──> [バックエンド (FastAPI)] ──> [SQLite]
                                                              │
                                                              └──> [LLM API (Ollama)]
```

## 技術スタック

※基本的には最新安定版を使用

### フロントエンド

| レイヤー | 技術 | 補足 |
|----------|------|------|
| フレームワーク | Next.js / React | App Router を利用 |
| UI / スタイリング | Tailwind CSS / shadcn/ui | テーブル・ダイアログ・タグ等の既製コンポーネント |
| データ取得 | TanStack Query (React Query) | API 取得・キャッシュ・ポーリング（スコア完了検知） |
| Lint / Format | ESLint / Prettier | コード整形・静的解析 |
| 型チェック | TypeScript | 静的型検査 |

### バックエンド

| レイヤー | 技術 | 補足 |
|----------|------|------|
| フレームワーク | FastAPI（Python） | API 提供 |
| データベース | SQLite | データ永続化 |
| パッケージ管理 | uv | Python の依存解決・仮想環境・実行 |
| ORM / バリデーション | SQLAlchemy / Pydantic | DB アクセスと入出力スキーマ定義 |
| 設定管理 | pydantic-settings | モデル名・Ollama の URL 等を `.env` から読み込み |
| AI | Ollama（ローカル）`gemma4:e4b`(2026-06最新) | 構造化・スコアリング・サマリー生成 |
| AI クライアント | ollama（公式 Python SDK） | `format`/JSON Schema 指定で構造化出力 |
| Lint / Format | Ruff | コード整形・静的解析 |
| 型チェック | mypy | 静的型検査 |
| テスト | pytest | 単体・API テスト |

> 個人利用のため、認証・マルチユーザ・スケーリングは対象外。ローカル環境での単一ユーザ利用を前提とする。
> AI もローカルの Ollama で完結させ、外部 API・APIキー・通信コストを発生させない。

## 処理フロー

```
1. 求人要件登録
   生テキスト ──> [POST /jobs/parse] ──> LLM が構造化 ──> 編集 ──> [POST /jobs] で保存

2. 応募書類登録
   生テキスト ──> [POST /candidates/parse] ──> LLM が構造化 ──> 編集 ──> [POST /candidates] で保存
   保存と同時にマッチングスコア算出をバックグラウンドで起動

3. マッチング
   候補者 × 求人 ──> LLM が多軸評価・必須要件チェック・サマリー生成 ──> スコアを保存

4. 結果確認
   [GET /jobs/{id}/rankings] ──> スコア降順で候補者一覧を取得・表示
```
