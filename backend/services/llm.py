"""LLM 連携の汎用基盤サービス層。

LLM 呼び出しを 1 箇所に集約し、`structured_chat` で検証 + リトライ +
フィードバックを一手に担う。構造化（structuring.py）・マッチング（matching.py）双方が
この汎用関数を再利用する。タスク固有のプロンプトや DB アクセスはここに置かず、各サービス
モジュールに分ける。

接続先（provider）は `settings.llm_provider` で切り替える:
- ollama: ローカル `gemma4:e4b`（デフォルト。ローカル完結）
- claude: Anthropic API（高精度。API キー・通信コストが発生する）

provider 差分（SDK・構造化出力の指定方法・例外種別）は各 provider 実装に閉じ込め、
`structured_chat` の「検証 + リトライ + フィードバック」ループは provider 非依存に保つ。
呼び出し側（routers/）が HTTP ステータスへ振り分けられるよう、失敗種別ごとに専用例外
（ParseFailedError / LLMTimeoutError / LLMUnavailableError）を送出する。
"""

import logging
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """LLM 連携の基底例外。"""


class ParseFailedError(LLMError):
    """検証失敗のリトライ上限を超過した（→ HTTP 502 PARSE_FAILED）。"""

    def __init__(self, attempts: int, message: str | None = None) -> None:
        self.attempts = attempts
        super().__init__(message or f"構造化に失敗しました（{attempts} 回試行）。")


class LLMTimeoutError(LLMError):
    """LLM 呼び出しがタイムアウトした（→ HTTP 502 LLM_TIMEOUT）。"""

    def __init__(self, attempts: int, message: str | None = None) -> None:
        self.attempts = attempts
        super().__init__(message or f"LLM 呼び出しがタイムアウトしました（{attempts} 回試行）。")


class LLMUnavailableError(LLMError):
    """LLM に接続できない（未起動・認証不可など。→ HTTP 503 LLM_UNAVAILABLE）。"""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "LLM に接続できません。設定や接続先の起動を確認してください。")


# provider が `structured_chat` のループへ失敗種別を伝えるための内部例外。
# ループ側はこの 2 種 + LLMUnavailableError だけを見れば provider 差分を意識しない。
class ProviderTimeout(LLMError):
    """provider 呼び出しがタイムアウトした（リトライ対象。タイムアウト由来と判定される）。"""


class ProviderRetryable(LLMError):
    """provider 呼び出しが一時的に失敗した（リトライ対象。タイムアウト由来ではない）。"""


class LLMProvider(Protocol):
    """LLM provider の共通インタフェース。

    `complete` は LLM を 1 回呼び、`schema` に従った JSON 文字列（生のテキスト）を返す。
    検証・リトライは呼び出し側（structured_chat）が担うため、provider は検証しない。
    失敗時は LLMUnavailableError（接続不可・認証不可で打ち切り）/ ProviderTimeout /
    ProviderRetryable（リトライ対象）のいずれかを送出する。
    """

    def complete(self, messages: list[dict[str, str]], schema: type[BaseModel]) -> str: ...


# --- Ollama provider -------------------------------------------------------

# Ollama クライアントはモジュールレベルに集約する（routers/ から ollama を直 import しない）。
# `settings.llm_provider` が claude のときも生成自体は無害（接続は complete 呼び出し時のみ）。
from ollama import Client, RequestError, ResponseError  # noqa: E402

_client = Client(host=settings.ollama_base_url, timeout=settings.ollama_timeout)


class OllamaProvider:
    """Ollama（ローカル）provider。

    `format` に JSON Schema を渡して出力を JSON に固定する。抽出タスクは決定論的で
    あってほしいため `temperature=0` を固定する（同一入力で結果がブレないようにする）。
    """

    def complete(self, messages: list[dict[str, str]], schema: type[BaseModel]) -> str:
        try:
            response = _client.chat(
                model=settings.ollama_model,
                messages=messages,
                format=schema.model_json_schema(),
                options={"temperature": 0},
            )
        except (httpx.ConnectError, ConnectionError) as exc:
            # 接続不可は即時に 503 相当。リトライしても無駄なため打ち切る。
            logger.error("Ollama への接続に失敗しました: %s", exc)
            raise LLMUnavailableError(
                "Ollama に接続できません。サービスの起動を確認してください。"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(str(exc)) from exc
        except (ResponseError, RequestError) as exc:
            raise ProviderRetryable(str(exc)) from exc

        return response.message.content or ""


# --- Claude provider -------------------------------------------------------


class ClaudeProvider:
    """Claude（Anthropic API）provider。

    `output_config.format` に JSON Schema を渡して出力を JSON に固定する。schema は
    Anthropic SDK の `transform_schema` で structured outputs 互換に整形する
    （`additionalProperties: false` 付与・`$ref` 展開など）。temperature は Opus 4.8 では
    送れないため指定しない。決定論性は「同一スキーマ + プロンプト」で担保する。
    """

    def __init__(self) -> None:
        import anthropic

        # ANTHROPIC_API_KEY は SDK が環境変数から解決する。
        self._client = anthropic.Anthropic()

    def complete(self, messages: list[dict[str, str]], schema: type[BaseModel]) -> str:
        import anthropic
        from anthropic.lib._parse._transform import transform_schema
        from anthropic.types import MessageParam

        # Anthropic は system を専用引数で受ける。messages 先頭の system を切り出す。
        system = ""
        chat_messages: list[MessageParam] = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                chat_messages.append(
                    MessageParam(role=m["role"], content=m["content"])  # type: ignore[typeddict-item]
                )

        try:
            response = self._client.messages.create(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                system=system,
                messages=chat_messages,
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": transform_schema(schema),
                    }
                },
            )
        except anthropic.APITimeoutError as exc:
            # APITimeoutError は APIConnectionError のサブクラス。接続不可より先に捕まえる。
            raise ProviderTimeout(str(exc)) from exc
        except (anthropic.APIConnectionError, anthropic.AuthenticationError) as exc:
            # 接続不可・認証不可はリトライしても無駄なため打ち切る（503 相当）。
            logger.error("Claude への接続に失敗しました: %s", exc)
            raise LLMUnavailableError(
                "Claude に接続できません。ANTHROPIC_API_KEY や通信を確認してください。"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise ProviderRetryable(str(exc)) from exc

        # 構造化出力では先頭の text ブロックが妥当な JSON 文字列になる。
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""


# --- provider 選択 ---------------------------------------------------------

_provider: LLMProvider | None = None


def _get_provider() -> LLMProvider:
    """`settings.llm_provider` に応じた provider をロードして 1 度だけ生成する。"""
    global _provider
    if _provider is None:
        if settings.llm_provider == "claude":
            _provider = ClaudeProvider()
        else:
            _provider = OllamaProvider()
    return _provider


def structured_chat(system: str, user: str, schema: type[T]) -> T:
    """構造化チャットを実行し、`schema` で検証した結果を返す。

    provider に JSON を生成させ、`message.content` を `schema.model_validate_json()` で
    検証する。検証/JSON エラー時は最大 `settings.parse_max_retries` 回まで、エラー要約を
    添えた追加 user メッセージでフィードバックしつつ再実行する。

    Raises:
        ParseFailedError: 検証失敗が上限を超えた場合。
        LLMTimeoutError: タイムアウトが上限を超えた場合。
        LLMUnavailableError: LLM に接続できない場合（接続不可・認証不可で即時打ち切り）。
    """
    provider = _get_provider()
    max_attempts = max(1, settings.parse_max_retries)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    last_timeout = False
    for attempt in range(1, max_attempts + 1):
        try:
            content = provider.complete(messages, schema)
        except ProviderTimeout as exc:
            last_timeout = True
            logger.warning(
                "LLM 呼び出しがタイムアウトしました（試行 %d/%d）: %s",
                attempt,
                max_attempts,
                exc,
            )
            messages.append(_retry_feedback_on_call_error())
            continue
        except ProviderRetryable as exc:
            last_timeout = False
            logger.warning(
                "LLM 呼び出しに失敗しました（試行 %d/%d）: %s",
                attempt,
                max_attempts,
                exc,
            )
            messages.append(_retry_feedback_on_call_error())
            continue

        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            last_timeout = False
            error_summary = _summarize_validation_error(exc)
            logger.warning(
                "LLM 出力の検証に失敗しました（試行 %d/%d）: %s",
                attempt,
                max_attempts,
                error_summary,
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "直前の出力は指定スキーマに適合しませんでした。"
                        f"エラー要約: {error_summary} "
                        "指定された JSON Schema に厳密に従い、余計なキーや前後テキストを"
                        "含めず JSON のみを再出力してください。"
                    ),
                }
            )

    # 上限超過。タイムアウトが最後の失敗要因なら LLM_TIMEOUT、それ以外は PARSE_FAILED。
    if last_timeout:
        raise LLMTimeoutError(attempts=max_attempts)
    raise ParseFailedError(attempts=max_attempts)


def _retry_feedback_on_call_error() -> dict[str, str]:
    """呼び出し自体が失敗した場合の再試行フィードバック user メッセージ。"""
    return {
        "role": "user",
        "content": (
            "直前の応答取得に失敗しました。指定された JSON Schema に"
            "厳密に従い、JSON のみを再出力してください。"
        ),
    }


def _summarize_validation_error(exc: ValidationError) -> str:
    """ValidationError を LLM フィードバック用に簡潔な文字列へ要約する。"""
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', '')}")
    return " / ".join(parts) if parts else str(exc)
