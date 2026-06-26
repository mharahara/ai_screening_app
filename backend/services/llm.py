"""Ollama 連携・構造化（求人）サービス層。

Ollama 公式 SDK の Client を 1 箇所に集約し、`structured_chat` で
検証 + リトライ + フィードバックを一手に担う。求人構造化 `structure_job` は
プロンプトを組み立ててこの汎用関数を呼ぶだけにする。

呼び出し側（routers/）が HTTP ステータスへ振り分けられるよう、失敗種別ごとに
専用例外（ParseFailedError / LLMTimeoutError / LLMUnavailableError）を送出する。
"""

import logging
from enum import StrEnum
from typing import TypeVar

import httpx
from ollama import Client, RequestError, ResponseError
from pydantic import BaseModel, ValidationError

from config import settings
from schemas import EmploymentType, JobParseResult, PositionLevel, RemoteWork

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

    抽出タスクは決定論的であってほしいため `temperature=0` を固定する
    （同一入力で結果がブレないようにする）。

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
                options={"temperature": 0},
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


# gemma 系の小型モデルは JSON Schema の `description` だけではフィールドの意味を
# 取りこぼし、title/description/skills などが軒並み空で返ることがある。そのため
# system プロンプト側で抽出フィールドを明示的に列挙して指示する。enum 候補値は
# スキーマ（schemas.py）と一致させるため StrEnum から動的に組み立てる。
def _enum_values(enum_cls: type[StrEnum]) -> str:
    return "[" + ", ".join(f'"{e.value}"' for e in enum_cls) + "]"


_JOB_SYSTEM_PROMPT = f"""あなたは採用情報の構造化アシスタントです。\
求人票の生テキストから情報を抽出し、JSON で出力してください。

# 抽出するフィールド
- title: 求人タイトル・募集職種（原文の「募集職種」等をそのまま）
- description: 業務内容の要約。原文の「業務内容」「ポジション概要」セクションをまとめる
- required_skills: 必須スキル・技術の配列。「必須要件」「Must」の文脈、および技術スタックとして
  列挙された技術から抽出する。要素は技術名・言語名・ツール名・フレームワーク名などの短いタグにする
  （例: ["Java", "Go", "TypeScript", "AWS", "MySQL"]）
- preferred_skills: 歓迎スキル・経験の配列。「歓迎要件」「Want」の文脈から抽出する。
  技術名・ツール名は required_skills と同じく短いタグに分割する
  （例: 「Docker / Kubernetes」→ ["Docker", "Kubernetes"]）。
  「〜の移行経験」のように技術名で表せない経験要件のみ簡潔なフレーズ1件1要素にする
  （例: ["マイクロサービス移行経験", "スクラムマスター経験"]）。資格・学位の要件はここに入れず
  certifications に入れる
- ideal_profile: 求める人物像の要約。「求める人物像」セクションをまとめる
- employment_type: 雇用形態。{_enum_values(EmploymentType)} のいずれか。言及がなければ null
- location: 勤務地。言及がなければ null
- remote_work: リモート可否。{_enum_values(RemoteWork)} のいずれか。\
言及はあるが曖昧なら "不明"、言及自体がなければ null
- rate_min / rate_max: 単価の下限/上限（万円/月の整数）。言及がなければ null
- min_experience_years: 最低経験年数（年の整数）。「5年前後」「3年以上」等の数値から
  最も低い必須年数を採る。言及がなければ null
- position_level: ポジションレベル。{_enum_values(PositionLevel)} のいずれか。
  「テックリード候補」はリード、明示がなければ役割記述から判断
- industry_experience: 求める業界経験。言及がなければ null
- certifications: 資格・学位要件の配列（資格名や学位のみ。プログラミング言語やツールなどの
  技術スタックは含めない）。「修士・博士号」のように複数候補が並ぶ場合も要素を冗長に展開せず
  簡潔にまとめる（例: 「データサイエンス、または情報理工学系の修士・博士号」→
  ["データサイエンスまたは情報理工学系の修士・博士号"]）。記載がなければ []

# ルール
1. 原文に明示された情報のみを抽出する。推測・補完・創作をしない。
2. 技術スタックセクションに列挙された技術は、歓迎要件として明示されていなければ
   required_skills に入れる。
3. required_skills・preferred_skills とも、技術名・ツール名は短いタグにし1要素1つに分割する
   （例: 「Python/Django」→ ["Python", "Django"]、「Go (Gin / Go-chi)」→ ["Go", "Gin", "Go-chi"]）。
   「〇〇の開発経験」のような文章から技術名を取り出せる場合はタグにする（含まれる技術名だけを取り出す）。
   表記は原文の語をそのまま使い、勝手な言い換えをしない。
4. 単価は万円/月の整数に正規化する（「時給」「年収」表記は概算換算してよいが、不明確なら null）。
5. 該当情報がないフィールドは null、配列フィールドは [] にする。
6. 出力は日本語。指定された JSON 以外のキー・説明文・前後テキストを出力しない。"""


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
