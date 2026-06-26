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
    _extract_json,
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


def test_complete_splits_system_and_appends_schema_instruction() -> None:
    """system は system 引数へ切り出し、JSON Schema 指示を末尾に添える。messages からは除く。"""
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _text_response(_VALID_JOB_JSON)

    provider = _make_provider(fake_create)
    provider.complete(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}],
        JobParseResult,
    )

    system = captured["system"]
    assert isinstance(system, str)
    assert system.startswith("sys")  # 元の system 指示を保持
    # JSON Schema を提示し、JSON のみの出力を指示している（output_config.format は使わない）。
    assert "json_schema" in system
    assert "required_skills" in system  # スキーマのフィールドが埋め込まれている
    assert "output_config" not in captured
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


def test_complete_missing_api_key_maps_to_unavailable() -> None:
    """ANTHROPIC_API_KEY 未設定（SDK が TypeError）は LLMUnavailableError にマップする。"""

    def fake_create(**kwargs: object) -> SimpleNamespace:
        raise TypeError(
            "Could not resolve authentication method. Expected one of api_key, "
            "auth_token, or credentials to be set."
        )

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


def test_complete_5xx_status_error_maps_to_retryable() -> None:
    """5xx（サーバ一時障害）は ProviderRetryable にマップする（リトライ対象）。"""
    provider = _make_provider(lambda **kwargs: (_ for _ in ()).throw(_api_status_error(500)))

    with pytest.raises(ProviderRetryable):
        provider.complete([{"role": "user", "content": "u"}], JobParseResult)


def test_complete_4xx_status_error_maps_to_unavailable() -> None:
    """4xx（残高不足・無効リクエスト等）はリトライせず LLMUnavailableError にマップする。"""
    provider = _make_provider(lambda **kwargs: (_ for _ in ()).throw(_api_status_error(400)))

    with pytest.raises(LLMUnavailableError):
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),  # そのまま
        ('```json\n{"a": 1}\n```', '{"a": 1}'),  # json コードフェンス
        ("```\n{\"a\": 1}\n```", '{"a": 1}'),  # 言語指定なしコードフェンス
        ('以下が結果です。\n{"a": 1}\n以上です。', '{"a": 1}'),  # 前後の説明文
        ('  {"a": 1}  ', '{"a": 1}'),  # 前後空白
    ],
)
def test_extract_json_strips_wrapping(raw: str, expected: str) -> None:
    """コードフェンス・前後の説明文・空白を剥がして JSON 本体を取り出す。"""
    assert _extract_json(raw) == expected


def test_complete_extracts_json_from_fenced_response() -> None:
    """応答がコードフェンスで囲まれていても JSON 本体を返す。"""
    fenced = f"```json\n{_VALID_JOB_JSON}\n```"
    provider = _make_provider(lambda **kwargs: _text_response(fenced))

    content = provider.complete([{"role": "user", "content": "u"}], JobParseResult)

    assert content == _VALID_JOB_JSON
