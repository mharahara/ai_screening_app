"""ClaudeProvider の例外マッピングと structured_chat 連携のユニットテスト。

Anthropic API は実際に叩かない。`ClaudeProvider._client.messages.create` を monkeypatch して
固定の応答や SDK 例外を返させ、JSON 文字列の取り出しと例外マッピングを検証する。
provider 差分（接続不可 → LLMUnavailableError、タイムアウト → ProviderTimeout、その他
APIStatusError → ProviderRetryable）が共通ループへ正しく伝わることを確認する。
"""

from types import SimpleNamespace

import anthropic
import httpx
import pytest

import services.llm as llm_module
from schemas import JobParseResult
from services.llm import (
    ClaudeProvider,
    LLMTimeoutError,
    LLMUnavailableError,
    ParseFailedError,
    ProviderRetryable,
    ProviderTimeout,
    structured_chat,
)

_VALID_JOB_JSON = JobParseResult(
    title="バックエンドエンジニア",
    required_skills=["Python", "FastAPI"],
).model_dump_json()


def _make_provider(create_fn: object) -> ClaudeProvider:
    """SDK クライアントを差し替えた ClaudeProvider を作る（実 SDK 初期化は回避）。"""
    provider = ClaudeProvider.__new__(ClaudeProvider)
    provider._client = SimpleNamespace(  # type: ignore[assignment]
        messages=SimpleNamespace(create=create_fn)
    )
    return provider


def _text_response(text: str) -> SimpleNamespace:
    """messages.create の戻り（content に text ブロックを持つ）を模した最小オブジェクト。"""
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block])


def _api_connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


def _api_status_error(status_code: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com")
    response = httpx.Response(status_code, request=request)
    return anthropic.APIStatusError("server error", response=response, body=None)


def test_complete_returns_text_block_content() -> None:
    """text ブロックの中身（JSON 文字列）をそのまま返す。"""
    provider = _make_provider(lambda **kwargs: _text_response(_VALID_JOB_JSON))

    content = provider.complete(
        [{"role": "user", "content": "u"}],
        JobParseResult,
    )

    assert content == _VALID_JOB_JSON


def test_complete_splits_system_message() -> None:
    """messages 先頭の system は system 引数へ切り出し、messages からは除く。"""
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _text_response(_VALID_JOB_JSON)

    provider = _make_provider(fake_create)
    provider.complete(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}],
        JobParseResult,
    )

    assert captured["system"] == "sys"
    assert captured["messages"] == [{"role": "user", "content": "u"}]
    # temperature は送らない（Opus 4.8 では非対応）。
    assert "temperature" not in captured


def test_complete_connection_error_maps_to_unavailable() -> None:
    """接続不可は LLMUnavailableError（即時打ち切り相当）にマップする。"""

    def fake_create(**kwargs: object) -> SimpleNamespace:
        raise _api_connection_error()

    provider = _make_provider(fake_create)

    with pytest.raises(LLMUnavailableError):
        provider.complete([{"role": "user", "content": "u"}], JobParseResult)


def test_complete_timeout_maps_to_provider_timeout() -> None:
    """タイムアウトは ProviderTimeout にマップする（リトライ対象・タイムアウト由来）。"""

    def fake_create(**kwargs: object) -> SimpleNamespace:
        raise anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com"))

    provider = _make_provider(fake_create)

    with pytest.raises(ProviderTimeout):
        provider.complete([{"role": "user", "content": "u"}], JobParseResult)


def test_complete_status_error_maps_to_retryable() -> None:
    """その他 APIStatusError は ProviderRetryable にマップする（リトライ対象）。"""
    provider = _make_provider(lambda **kwargs: (_ for _ in ()).throw(_api_status_error(500)))

    with pytest.raises(ProviderRetryable):
        provider.complete([{"role": "user", "content": "u"}], JobParseResult)


def test_structured_chat_uses_claude_provider_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provider=claude のとき structured_chat が ClaudeProvider 経由で検証済みモデルを返す。"""
    provider = _make_provider(lambda **kwargs: _text_response(_VALID_JOB_JSON))
    # _get_provider のモジュールキャッシュを差し替える。
    monkeypatch.setattr(llm_module, "_provider", provider)

    result = structured_chat("sys", "user", JobParseResult)

    assert isinstance(result, JobParseResult)
    assert result.title == "バックエンドエンジニア"


def test_structured_chat_claude_timeout_raises_llm_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude のタイムアウトが上限まで続くと LLMTimeoutError に集約される。"""

    def fake_create(**kwargs: object) -> SimpleNamespace:
        raise anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com"))

    monkeypatch.setattr(llm_module, "_provider", _make_provider(fake_create))

    with pytest.raises(LLMTimeoutError):
        structured_chat("sys", "user", JobParseResult)


def test_structured_chat_claude_invalid_json_raises_parse_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude が壊れた JSON を返し続けると ParseFailedError に集約される。"""
    provider = _make_provider(lambda **kwargs: _text_response('{"required_skills": 123}'))
    monkeypatch.setattr(llm_module, "_provider", provider)

    with pytest.raises(ParseFailedError):
        structured_chat("sys", "user", JobParseResult)
