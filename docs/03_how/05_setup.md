# ディレクトリ構成・セットアップ (how)

## ディレクトリ構成（想定）

```
RabbitPick/
├── backend/
│   ├── pyproject.toml     # 依存定義・Ruff/mypy 設定（uv で管理）
│   ├── uv.lock            # ロックファイル
│   ├── .env               # LLM_PROVIDER・モデル名・Ollama URL / Claude 設定等（pydantic-settings）
│   ├── main.py            # FastAPI エントリポイント
│   ├── config.py          # pydantic-settings の設定クラス
│   ├── models.py          # SQLAlchemy モデル
│   ├── schemas.py         # Pydantic スキーマ
│   ├── routers/           # jobs / candidates / rankings
│   ├── services/          # Ollama 連携・スコアリングロジック
│   ├── tests/             # pytest
│   └── db.py              # DB セッション・初期化
├── frontend/
│   ├── app/               # Next.js App Router
│   ├── components/        # ヘッダー・テーブル・ダイアログ等
│   └── lib/               # API クライアント
└── docs/
```

## セットアップ・起動（想定）

LLM provider は `.env` の `LLM_PROVIDER` で選択する（既定 `ollama`）。

```bash
# --- provider=ollama（デフォルト）の場合 ---
# 前提: Ollama を起動し、モデルを取得しておく
ollama pull gemma4:e4b

# --- provider=claude の場合 ---
# backend/.env に以下を設定（pydantic-settings 経由で SDK へ渡る）
#   LLM_PROVIDER=claude
#   ANTHROPIC_API_KEY=sk-ant-...
# CLAUDE_MODEL / CLAUDE_MAX_TOKENS は任意（既定: claude-opus-4-8 / 4096）

# バックエンド（uv）
cd backend
uv sync                       # 依存をインストール
uv run uvicorn main:app --reload

# フロントエンド
cd frontend
npm install
npm run dev
```
