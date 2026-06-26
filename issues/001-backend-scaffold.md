# issue: backend プロジェクト初期化（骨組み・ヘルスチェック・設定）

## ステータス

`done`

## 背景・目的

RabbitPick はドキュメント（`docs/`）は整備済みだが `backend/` のコードが一切存在しない。以降の機能 issue（求人/候補者の構造化・スコアリング API 等）を積み上げられるよう、まず FastAPI バックエンドの骨組み（uv プロジェクト・ディレクトリ構成・設定読み込み・起動確認）を立ち上げる。frontend は別 issue（002 予定）で扱う。

## 要件

- [ ] `backend/` に uv プロジェクトを作成する（`pyproject.toml` / `uv.lock`）。依存に FastAPI / uvicorn / SQLAlchemy / Pydantic / pydantic-settings / ollama（公式 Python SDK）、dev 依存に Ruff / mypy / pytest を含める。
- [ ] [docs/03_how/05_setup.md](../docs/03_how/05_setup.md) の想定構成に沿って空のディレクトリ／プレースホルダを用意する: `main.py` / `config.py` / `models.py` / `schemas.py` / `db.py` / `routers/` / `services/` / `tests/`（中身は本 issue の範囲分のみ）。
- [ ] `config.py` に pydantic-settings の `Settings` クラスを定義する（Ollama URL・モデル名 `gemma4:e4b`・SQLite の DB パスを `.env` から読み込む。`.env` 不在でも妥当なデフォルトで起動できる）。`.env.example` を置き、`.env` 本体は `.gitignore` する。
- [ ] `main.py` に FastAPI アプリを定義し、`GET /health` が `200` と `{"status": "ok"}` を返す。
- [ ] `uv run uvicorn main:app --reload` で起動でき、`GET /health` が応答する。
- [ ] Ruff / mypy / pytest が通る設定を `pyproject.toml` に入れ、`GET /health` の最小テストを `tests/` に追加する（`TestClient` 使用、Ollama 呼び出しは発生しない）。

## 対象レイヤー

- [x] backend（`backend/` — FastAPI / SQLAlchemy / Pydantic / Ollama 連携・構造化・スコアリング）
- [ ] frontend（`frontend/` — Next.js App Router / React / TanStack Query / 候補者・求人・ランキング画面）

## 受け入れ条件（Definition of Done）

- [ ] `backend/` で `uv sync` が成功し、依存（FastAPI / uvicorn / SQLAlchemy / Pydantic / pydantic-settings / ollama、dev: Ruff / mypy / pytest）が解決する。
- [ ] `uv run uvicorn main:app --reload` で起動し、`GET /health` が `200` / `{"status": "ok"}` を返す。
- [ ] `cd backend && uv run ruff check` が通る。
- [ ] `cd backend && uv run ruff format --check` が通る。
- [ ] `cd backend && uv run mypy .` が通る。
- [ ] `cd backend && uv run pytest` が通る（`GET /health` の単体テストが緑。Ollama 呼び出しはモック化不要＝そもそも呼ばない）。
- [ ] `config.py` の `Settings` が `.env` 不在でもデフォルト値で読み込め、`.env.example` が存在し、`.env` 本体は `.gitignore` 済み。

## 確認したい受け入れシナリオ

- ターミナルで `cd backend && uv sync && uv run uvicorn main:app --reload` を実行 → 起動後 `curl localhost:8000/health` が `{"status":"ok"}` を返す（ブラウザ画面はまだ無い＝frontend は別 issue のため、API 応答で確認する）。

## スコープ外（やらないこと）

- frontend の初期化（別 issue 002 で扱う）。
- 求人/候補者/ランキングの各 API・LLM 構造化・スコアリング・バックグラウンド処理の実装（後続の機能 issue で扱う）。
- SQLAlchemy の本テーブル定義・`create_all` による DB 初期化（本 issue は骨組みのみ。`models.py` / `db.py` はプレースホルダ）。
- CLAUDE.md「やらないこと」全般: 認証 / マルチユーザ / Docker / Alembic / PostgreSQL / 外部 LLM API / 求人の保存後編集。

## 参考

- [docs/03_how/01_architecture.md](../docs/03_how/01_architecture.md) — 技術スタック・処理フロー
- [docs/03_how/05_setup.md](../docs/03_how/05_setup.md) — 想定ディレクトリ構成・セットアップ手順
- [docs/03_how/06_testing.md](../docs/03_how/06_testing.md) — pytest 方針（本 issue は health の最小テストのみ）
- [docs/03_how/04_api.md](../docs/03_how/04_api.md) — 後続で実装する API 一覧（本 issue では未実装）
- [CLAUDE.md](../CLAUDE.md) — 技術スタック・スコープ外
