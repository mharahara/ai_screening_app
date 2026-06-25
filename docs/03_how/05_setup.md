# ディレクトリ構成・セットアップ (how)

## ディレクトリ構成（想定）

```
RabbitPick/
├── backend/
│   ├── pyproject.toml     # 依存定義・Ruff/mypy 設定（uv で管理）
│   ├── uv.lock            # ロックファイル
│   ├── .env               # モデル名・Ollama URL 等（pydantic-settings）
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

```bash
# 前提: Ollama を起動し、モデルを取得しておく
ollama pull gemma4:e4b

# バックエンド（uv）
cd backend
uv sync                       # 依存をインストール
uv run uvicorn main:app --reload

# フロントエンド
cd frontend
npm install
npm run dev
```
