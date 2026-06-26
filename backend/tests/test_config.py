"""config.Settings の最小テスト。

骨組み段階なので「.env 不在でもデフォルトで成立すること」と
「環境変数でオーバーライドできること」だけを決定的に確認する。
深追いはしない。
"""

import pytest

from config import Settings


def test_settings_defaults() -> None:
    """`.env` を読み込まずにインスタンス化でき、想定どおりのデフォルト値になる。

    `_env_file=None` で開発者ローカルの `.env` の有無に依存せず決定的にする。
    """
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "gemma4:e4b"
    assert settings.ollama_timeout == 120.0
    assert settings.database_url == "sqlite:///./rabbitpick.db"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数で設定値を上書きできる（型変換も含めて1ケースだけ確認）。"""
    monkeypatch.setenv("OLLAMA_MODEL", "other-model")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "30.0")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.ollama_model == "other-model"
    assert settings.ollama_timeout == 30.0
