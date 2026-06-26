# RabbitPick backend

FastAPI バックエンド。Ollama 連携・データ保存・スコア算出を担う。

## セットアップ

```bash
uv sync
cp .env.example .env   # 必要に応じて編集（不在でもデフォルトで起動可）
uv run uvicorn main:app --reload
```

`GET /health` が `{"status": "ok"}` を返せば起動成功。

## 開発コマンド

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest
```
