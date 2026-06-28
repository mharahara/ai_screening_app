# RabbitPick

> エンジニア選考をより早く軽やかに

AIを活用したエンジニア採用スクリーニングシステム。フリーランスエンジニアの応募書類（職務経歴書・履歴書等）の生テキストをLLMが構造化し、求人要件とのマッチ度を0〜100点でスコアリングして候補者をランキングします。

個人利用・ローカル単一ユーザ前提のため、認証・マルチユーザ・スケーリングは対象外です。

## 主要機能

- **応募書類の自動解析**: テキストを貼り付けるだけでAIが氏名・スキル・職歴などを自動構造化
- **求人要件の自動解析**: 求人票テキストから必須スキル・歓迎スキル・条件などを自動抽出
- **AIマッチングエンジン**: 候補者を多軸（スキル・経験年数・業界経験・ポジションレベル）で評価し0〜100点でスコアリング
- **必須要件充足チェック**: 求人の必須要件を1件ずつ判定し充足率を算出
- **AIサマリー生成**: 候補者ごとに強み・懸念点・面接での確認事項を自動生成
- **ランキング表示**: スコア順に候補者を一覧表示、詳細ダイアログで根拠を確認

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| フロントエンド | Next.js (App Router) / React / TypeScript / Tailwind CSS / shadcn/ui |
| データ取得 | TanStack Query (ポーリングによるスコア完了検知) |
| バックエンド | FastAPI (Python) / SQLAlchemy / Pydantic |
| データベース | SQLite |
| LLM (デフォルト) | Ollama ローカル (`gemma4:e4b`) |
| LLM (オプション) | Claude (`claude-opus-4-8`) via Anthropic API |
| パッケージ管理 | uv (backend) / npm (frontend) |

## 前提条件

- Python 3.11 以上
- [uv](https://docs.astral.sh/uv/) がインストール済み
- Node.js 18 以上 / npm
- **Ollama を使う場合（デフォルト）**: [Ollama](https://ollama.com/) がインストール・起動済み
- **Claude を使う場合**: Anthropic API キー

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd RabbitPick
```

### 2. LLM プロバイダの準備

#### Ollama（デフォルト）

Ollama をインストールして起動し、使用するモデルを取得します。

```bash
ollama pull gemma4:e4b
```

#### Claude（Anthropic API）

`backend/.env` ファイルを作成して以下を設定します。

```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
# 以下は任意（デフォルト値）
# CLAUDE_MODEL=claude-opus-4-8
# CLAUDE_MAX_TOKENS=4096
```

### 3. バックエンドのセットアップ

```bash
cd backend
uv sync
```

### 4. フロントエンドのセットアップ

```bash
cd frontend
npm install
```

## 起動

バックエンドとフロントエンドをそれぞれ別ターミナルで起動します。

```bash
# バックエンド（http://localhost:8000）
cd backend
uv run uvicorn main:app --reload
```

```bash
# フロントエンド（http://localhost:3000）
cd frontend
npm run dev
```

ブラウザで http://localhost:3000 を開いてください。

## 利用フロー

1. **求人要件を登録する** — ヘッダーの「＋ 求人を追加」から求人票テキストを貼り付けてAI解析・登録
2. **応募書類を登録する** — 「応募書類取り込み」画面で対象求人を選んでレジュメを貼り付けて登録 → マッチングスコアが自動算出
3. **結果を確認する** — 「ランキング」画面でスコア順に候補者を確認、詳細ダイアログでスコア根拠・AIサマリーを閲覧

## ディレクトリ構成

```
RabbitPick/
├── backend/
│   ├── pyproject.toml     # 依存定義（uv で管理）
│   ├── main.py            # FastAPI エントリポイント
│   ├── config.py          # 設定（pydantic-settings）
│   ├── models.py          # SQLAlchemy モデル
│   ├── schemas.py         # Pydantic スキーマ
│   ├── routers/           # jobs / candidates / rankings
│   ├── services/          # LLM連携・スコアリングロジック
│   ├── tests/             # pytest
│   └── db.py              # DBセッション・初期化
├── frontend/
│   ├── app/               # Next.js App Router
│   ├── components/        # UIコンポーネント
│   └── lib/               # API クライアント
└── docs/                  # 設計ドキュメント
```

## ドキュメント

詳細な設計ドキュメントは [docs/](docs/) を参照してください。

| ドキュメント | 内容 |
|---|---|
| [docs/01_overview.md](docs/01_overview.md) | システム概要 |
| [docs/02_what.md](docs/02_what.md) | 主要機能・画面仕様 |
| [docs/03_how/01_architecture.md](docs/03_how/01_architecture.md) | アーキテクチャ・技術スタック |
| [docs/03_how/02_ai.md](docs/03_how/02_ai.md) | AI連携の詳細仕様 |
| [docs/03_how/03_data-model.md](docs/03_how/03_data-model.md) | データモデル |
| [docs/03_how/04_api.md](docs/03_how/04_api.md) | API仕様 |
| [docs/03_how/05_setup.md](docs/03_how/05_setup.md) | セットアップ詳細 |
| [docs/03_how/06_testing.md](docs/03_how/06_testing.md) | テスト方針 |
