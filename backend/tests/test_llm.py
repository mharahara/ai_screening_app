"""services/llm.py の構造化・リトライ挙動のユニットテスト。

Ollama は実際に叩かない。`services.llm._client.chat` を monkeypatch して、
固定の応答（妥当 JSON / 壊れた JSON）や例外を返させ、processing/分岐を検証する。
LLM の応答内容そのものの良し悪しは検証しない。
"""

from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from ollama import ResponseError

import services.llm as llm_module
from schemas import JobParseResult
from services.llm import (
    LLMTimeoutError,
    LLMUnavailableError,
    ParseFailedError,
    structured_chat,
)


def _chat_response(content: str) -> SimpleNamespace:
    """`_client.chat` の戻り（.message.content を持つ）を模した最小オブジェクト。"""
    return SimpleNamespace(message=SimpleNamespace(content=content))


_VALID_JOB_JSON = JobParseResult(
    title="バックエンドエンジニア",
    required_skills=["Python", "FastAPI"],
).model_dump_json()


class FakeChat:
    """`_client.chat` を置き換える呼び出し可能オブジェクト。

    呼び出しごとに side_effects を順に返す/送出する（Exception なら raise）。
    各呼び出しの kwargs を `calls` に記録する。
    """

    def __init__(self, side_effects: list[object]) -> None:
        self._side_effects = side_effects
        self.calls: list[dict[str, object]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        effect = self._side_effects[len(self.calls) - 1]
        if isinstance(effect, Exception):
            raise effect
        return effect


def test_structured_chat_success_returns_validated_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """妥当な JSON を返すと検証済みモデルを 1 回の呼び出しで返す。"""
    fake = FakeChat([_chat_response(_VALID_JOB_JSON)])
    monkeypatch.setattr(llm_module._client, "chat", fake)

    result = structured_chat("sys", "user", JobParseResult)

    assert isinstance(result, JobParseResult)
    assert result.title == "バックエンドエンジニア"
    assert result.required_skills == ["Python", "FastAPI"]
    assert len(fake.calls) == 1


def test_structured_chat_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1 回目は ValidationError を誘発する壊れた JSON、2 回目で成功 → 結果を返す。"""
    fake = FakeChat(
        [
            _chat_response('{"required_skills": "Python"}'),  # 配列でない → ValidationError
            _chat_response(_VALID_JOB_JSON),
        ]
    )
    monkeypatch.setattr(llm_module._client, "chat", fake)

    result = structured_chat("sys", "user", JobParseResult)

    assert isinstance(result, JobParseResult)
    assert len(fake.calls) == 2
    # 2 回目の呼び出しではフィードバック用 user メッセージが追加されている。
    second_messages = cast(list[dict[str, str]], fake.calls[1]["messages"])
    assert len(second_messages) == 3  # system + user + フィードバック
    assert second_messages[-1]["role"] == "user"


def test_structured_chat_all_invalid_raises_parse_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全回壊れた JSON → 上限回数試行して ParseFailedError（attempts 付き）。"""
    broken = _chat_response('{"required_skills": 123}')
    fake = FakeChat([broken, broken, broken])
    monkeypatch.setattr(llm_module._client, "chat", fake)

    with pytest.raises(ParseFailedError) as excinfo:
        structured_chat("sys", "user", JobParseResult)

    from config import settings

    assert excinfo.value.attempts == settings.parse_max_retries
    assert len(fake.calls) == settings.parse_max_retries


def test_structured_chat_connection_error_raises_unavailable_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """接続不可は即 LLMUnavailableError（リトライしない）。"""
    fake = FakeChat([httpx.ConnectError("connection refused")])
    monkeypatch.setattr(llm_module._client, "chat", fake)

    with pytest.raises(LLMUnavailableError):
        structured_chat("sys", "user", JobParseResult)

    assert len(fake.calls) == 1  # 打ち切られている


def test_structured_chat_all_timeout_raises_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全回タイムアウト → 上限試行して LLMTimeoutError（最後の失敗がタイムアウト）。"""
    timeout = httpx.TimeoutException("timed out")
    fake = FakeChat([timeout, timeout, timeout])
    monkeypatch.setattr(llm_module._client, "chat", fake)

    with pytest.raises(LLMTimeoutError) as excinfo:
        structured_chat("sys", "user", JobParseResult)

    from config import settings

    assert excinfo.value.attempts == settings.parse_max_retries
    assert len(fake.calls) == settings.parse_max_retries


def test_structured_chat_last_failure_decides_exception_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """最後の失敗がタイムアウトなら LLMTimeoutError、検証失敗なら ParseFailedError に分岐。

    タイムアウト → タイムアウト → 検証失敗 の順で、最後が検証失敗なので ParseFailedError。
    """
    timeout = httpx.TimeoutException("timed out")
    fake = FakeChat([timeout, timeout, _chat_response('{"required_skills": 1}')])
    monkeypatch.setattr(llm_module._client, "chat", fake)

    with pytest.raises(ParseFailedError):
        structured_chat("sys", "user", JobParseResult)


def test_structured_chat_response_error_retried_not_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ResponseError（接続不可でない）はリトライ対象で、最終的に ParseFailedError。"""
    err = ResponseError("server error", status_code=500)
    fake = FakeChat([err, err, err])
    monkeypatch.setattr(llm_module._client, "chat", fake)

    with pytest.raises(ParseFailedError):
        structured_chat("sys", "user", JobParseResult)

    from config import settings

    assert len(fake.calls) == settings.parse_max_retries
