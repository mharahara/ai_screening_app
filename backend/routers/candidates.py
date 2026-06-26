"""応募書類 API（candidates）。

生テキスト構造化（parse・未保存）/ 保存 / 削除を提供する。
保存後の編集はスコープ外のため PUT/PATCH は提供しない。
ビジネスロジック（LLM 呼び出し）は services/ に委譲し、ここは services 例外を
docs/03_how/02_ai.md のエラーコードへ変換する責務に留める。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db
from models import Candidate, Job
from schemas import CandidateCreate, CandidateOut, CandidateParseResult
from services.llm import (
    LLMTimeoutError,
    LLMUnavailableError,
    ParseFailedError,
)
from services.structuring import structure_candidate

router = APIRouter(prefix="/candidates", tags=["candidates"])


class CandidateParseRequest(BaseModel):
    """応募書類構造化リクエスト（生テキスト）。"""

    raw_text: str = Field(min_length=1, description="応募書類の原文。")


class CandidateParseResponse(CandidateParseResult):
    """応募書類構造化レスポンス（構造化結果 + 原文を同梱・未保存）。"""

    raw_text: str


def _to_error_detail(code: str, message: str, attempts: int | None = None) -> dict[str, object]:
    """02_ai.md のエラーレスポンス形に整形する。"""
    detail: dict[str, object] = {"code": code, "message": message}
    if attempts is not None:
        detail["attempts"] = attempts
    return detail


@router.post("/parse", response_model=CandidateParseResponse)
def parse_candidate(req: CandidateParseRequest) -> CandidateParseResponse:
    """応募書類テキストを構造化して返す（未保存）。

    services の失敗種別を 02_ai.md のエラーコードへ変換する:
    ParseFailedError→502 PARSE_FAILED / LLMTimeoutError→502 LLM_TIMEOUT /
    LLMUnavailableError→503 LLM_UNAVAILABLE。
    """
    try:
        result = structure_candidate(req.raw_text)
    except ParseFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_to_error_detail(
                "PARSE_FAILED",
                "構造化に失敗しました。テキストを確認して再試行してください。",
                exc.attempts,
            ),
        ) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_to_error_detail(
                "LLM_TIMEOUT",
                "LLM 呼び出しがタイムアウトしました。時間をおいて再試行してください。",
                exc.attempts,
            ),
        ) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_to_error_detail(
                "LLM_UNAVAILABLE",
                "LLM サービスに接続できません。Ollama の起動を確認してください。",
            ),
        ) from exc

    # raw_text は LLM に生成させず、リクエスト入力をそのまま同梱して返す。
    return CandidateParseResponse(**result.model_dump(), raw_text=req.raw_text)


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(payload: CandidateCreate, db: Session = Depends(get_db)) -> Candidate:
    """構造化済みの候補者を保存する。

    紐づく求人が存在しない場合は 404。
    NOTE: 後続のマッチング issue では、ここで BackgroundTasks にスコア算出
    （match_candidate）を登録して非同期起動する。本 issue ではスコープ外。
    """
    if db.get(Job, payload.job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="求人が見つかりません。",
        )

    candidate = Candidate(**payload.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)) -> None:
    """候補者を削除する。関連スコアはカスケード削除（後続 issue で関係定義）。"""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="候補者が見つかりません。",
        )
    db.delete(candidate)
    db.commit()
