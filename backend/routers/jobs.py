"""求人要件 API（jobs）。

生テキスト構造化（parse・未保存）/ 保存 / 一覧 / 削除を提供する。
保存後の編集はスコープ外のため PUT/PATCH は提供しない。
ビジネスロジック（LLM 呼び出し）は services/ に委譲し、ここは services 例外を
docs/03_how/02_ai.md のエラーコードへ変換する責務に留める。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import Job
from schemas import JobCreate, JobOut, JobParseResult, JobSummary
from services.llm import (
    LLMTimeoutError,
    LLMUnavailableError,
    ParseFailedError,
)
from services.structuring import structure_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobParseRequest(BaseModel):
    """求人構造化リクエスト（生テキスト）。"""

    raw_text: str = Field(min_length=1, description="求人票の原文。")


class JobParseResponse(JobParseResult):
    """求人構造化レスポンス（構造化結果 + 原文を同梱・未保存）。"""

    raw_text: str


def _to_error_detail(code: str, message: str, attempts: int | None = None) -> dict[str, object]:
    """02_ai.md のエラーレスポンス形に整形する。"""
    detail: dict[str, object] = {"code": code, "message": message}
    if attempts is not None:
        detail["attempts"] = attempts
    return detail


@router.post("/parse", response_model=JobParseResponse)
def parse_job(req: JobParseRequest) -> JobParseResponse:
    """求人票テキストを構造化して返す（未保存）。

    services の失敗種別を 02_ai.md のエラーコードへ変換する:
    ParseFailedError→502 PARSE_FAILED / LLMTimeoutError→502 LLM_TIMEOUT /
    LLMUnavailableError→503 LLM_UNAVAILABLE。
    """
    try:
        result = structure_job(req.raw_text)
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
    return JobParseResponse(**result.model_dump(), raw_text=req.raw_text)


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> Job:
    """構造化済みの求人要件を保存する。"""
    job = Job(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobSummary])
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    """求人一覧（id / title / created_at）を作成日時の降順で返す。0 件は空配列。"""
    return list(db.scalars(select(Job).order_by(Job.created_at.desc(), Job.id.desc())).all())


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)) -> None:
    """求人を削除する。関連する候補者・スコアはカスケード削除（後続 issue で関係定義）。"""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="求人が見つかりません。")
    db.delete(job)
    db.commit()
