"""アプリケーション設定。

pydantic-settings で `.env` から型安全に読み込む。
`.env` が存在しなくても妥当なデフォルトで起動できる。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数 / `.env` から読み込む設定値。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama 連携
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"
    ollama_timeout: float = 120.0

    # 構造化・マッチングの LLM 呼び出しリトライ上限（初回 + リトライ）。
    parse_max_retries: int = 3

    # データベース（SQLite）
    database_url: str = "sqlite:///./rabbitpick.db"

    # CORS。frontend（Next.js）からブラウザで API を叩けるよう許可するオリジン。
    # 個人利用・ローカル単一ユーザ前提なので 1 オリジンで十分。
    cors_allow_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
