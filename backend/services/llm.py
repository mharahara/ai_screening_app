"""Ollama 連携・構造化（求人）サービス層。

Ollama 公式 SDK の Client を 1 箇所に集約し、`structured_chat` で
検証 + リトライ + フィードバックを一手に担う。求人構造化 `structure_job` は
プロンプトを組み立ててこの汎用関数を呼ぶだけにする。

呼び出し側（routers/）が HTTP ステータスへ振り分けられるよう、失敗種別ごとに
専用例外（ParseFailedError / LLMTimeoutError / LLMUnavailableError）を送出する。
"""

import logging
from typing import TypeVar

import httpx
from ollama import Client, RequestError, ResponseError
from pydantic import BaseModel, ValidationError

from config import settings
from schemas import JobParseResult

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
    """Ollama に接続できない（未起動など。→ HTTP 503 LLM_UNAVAILABLE）。"""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "Ollama に接続できません。サービスの起動を確認してください。")


# Ollama クライアントはここに集約する。routers/ から ollama を直 import しない。
_client = Client(host=settings.ollama_base_url, timeout=settings.ollama_timeout)


def _is_timeout(exc: Exception) -> bool:
    """例外がタイムアウト由来か判定する。"""
    return isinstance(exc, httpx.TimeoutException)


def structured_chat(system: str, user: str, schema: type[T]) -> T:
    """構造化チャットを実行し、`schema` で検証した結果を返す。

    `format` に `schema.model_json_schema()` を渡して出力を JSON に固定し、
    `message.content` を `schema.model_validate_json()` で検証する。検証/JSON
    エラー時は最大 `settings.parse_max_retries` 回まで、エラー要約を添えた追加
    user メッセージでフィードバックしつつ再実行する。

    Raises:
        ParseFailedError: 検証失敗が上限を超えた場合。
        LLMTimeoutError: タイムアウトが上限を超えた場合。
        LLMUnavailableError: Ollama に接続できない場合。
    """
    max_attempts = max(1, settings.parse_max_retries)
    json_schema = schema.model_json_schema()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    last_timeout = False
    for attempt in range(1, max_attempts + 1):
        try:
            response = _client.chat(
                model=settings.ollama_model,
                messages=messages,
                format=json_schema,
            )
        except (httpx.ConnectError, ConnectionError) as exc:
            # 接続不可は即時に 503 相当。リトライしても無駄なため打ち切る。
            logger.error("Ollama への接続に失敗しました: %s", exc)
            raise LLMUnavailableError() from exc
        except (httpx.TimeoutException, ResponseError, RequestError) as exc:
            last_timeout = _is_timeout(exc)
            logger.warning(
                "LLM 呼び出しに失敗しました（試行 %d/%d）: %s",
                attempt,
                max_attempts,
                exc,
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "直前の応答取得に失敗しました。指定された JSON Schema に"
                        "厳密に従い、JSON のみを再出力してください。"
                    ),
                }
            )
            continue

        content = response.message.content or ""
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


def _summarize_validation_error(exc: ValidationError) -> str:
    """ValidationError を LLM フィードバック用に簡潔な文字列へ要約する。"""
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', '')}")
    return " / ".join(parts) if parts else str(exc)


_JOB_SYSTEM_PROMPT = (
    "あなたは採用情報の構造化アシスタントです。求人票の生テキストから、"
    "指定された JSON Schema のフィールドを抽出してください。\n"
    "共通ルール:\n"
    "1. 原文に明示された情報のみを抽出する。推測・補完・創作をしない。\n"
    "2. 該当情報がないフィールドは null（配列フィールドは []）にする。\n"
    '3. スキルは1スキル1要素に分割する（例: 「Python/Django」→ ["Python", "Django"]）。'
    "表記は原文の語をそのまま使い、勝手な言い換えをしない。\n"
    "4. 単価は万円/月の整数に正規化する（「時給」「年収」表記がある場合のみ概算換算して"
    "よいが、不明確なら null）。\n"
    "5. 経験年数は年（整数）。「3年半」等は四捨五入する。\n"
    "6. enum フィールドは指定された候補値のいずれかに正規化する。\n"
    "7. 出力は日本語。指定 JSON Schema 以外のキー・説明文・前後テキストを出力しない。\n"
    "求人固有の注意: 必須スキル（required_skills）と歓迎スキル（preferred_skills）を"
    "原文の文脈から区別する。"
)


def _build_job_user_prompt(raw_text: str) -> str:
    """求人構造化用の user プロンプトを組み立てる。"""
    return f"以下の求人票を構造化してください。\n<求人票>\n{raw_text}\n</求人票>"


def structure_job(raw_text: str) -> JobParseResult:
    """求人票の生テキストを構造化して `JobParseResult` を返す。"""
    return structured_chat(
        system=_JOB_SYSTEM_PROMPT,
        user=_build_job_user_prompt(raw_text),
        schema=JobParseResult,
    )
