"""アプリケーション設定。

pydantic-settings で `.env` から型安全に読み込む。
`.env` が存在しなくても妥当なデフォルトで起動できる。
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数 / `.env` から読み込む設定値。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider 選択。構造化・マッチングとも一括でどちらか一方を使う。
    # デフォルトはローカル完結の Ollama。`claude` 選択時は Anthropic API（API キー・
    # 通信コストが発生する。ANTHROPIC_API_KEY は SDK が環境変数から直接解決する）。
    llm_provider: Literal["ollama", "claude"] = "ollama"

    # Ollama 連携
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"
    ollama_timeout: float = 120.0

    # Claude（Anthropic API）連携。temperature は Opus 4.8 では送れないため持たない。
    # anthropic SDK は .env を読まないため、API キーは pydantic-settings 経由で受け取り
    # ClaudeProvider が SDK へ明示的に渡す（環境変数 ANTHROPIC_API_KEY からも読める）。
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-4-8"
    claude_max_tokens: int = 4096

    # 構造化・マッチングの LLM 呼び出しリトライ上限（初回 + リトライ）。
    parse_max_retries: int = 3

    # マッチングスコアの各軸重み（合計は正規化するため和が 1.0 でなくてもよい）。
    match_weight_skill: float = 0.40
    match_weight_experience: float = 0.20
    match_weight_industry: float = 0.20
    match_weight_position: float = 0.20

    # データベース（SQLite）
    database_url: str = "sqlite:///./rabbitpick.db"

    # CORS。frontend（Next.js）からブラウザで API を叩けるよう許可するオリジン。
    # 個人利用・ローカル単一ユーザ前提なので 1 オリジンで十分。
    cors_allow_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
