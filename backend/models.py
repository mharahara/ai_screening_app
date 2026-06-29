"""SQLAlchemy モデル（Job / Candidate / Score 等）。

SQLAlchemy 2.0 の `Mapped[...]` 記法で定義する。配列・タグ・チェックリストは
JSON カラムで保持する。日時カラムは `DateTime(timezone=True)`。

`Job` と `Candidate` を定義する。求人削除時は `candidates.job_id` の
ON DELETE CASCADE と Job 側 relationship の `cascade="all, delete-orphan"` で
候補者を一括削除する。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from db import Base
from schemas import PositionLevel


class Job(Base):
    """求人要件（構造化済み）。

    保存後の編集は不可、削除は可。配列フィールド（required_skills /
    preferred_skills / certifications）は JSON カラムで保持する。
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 構造化フィールド（schemas.JobParseResult に対応）。
    title: Mapped[str | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(default=None)
    required_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    ideal_profile: Mapped[str | None] = mapped_column(default=None)
    rate_min: Mapped[int | None] = mapped_column(default=None)
    rate_max: Mapped[int | None] = mapped_column(default=None)
    min_experience_years: Mapped[int | None] = mapped_column(default=None)
    position_level: Mapped[PositionLevel | None] = mapped_column(default=None)
    industry_experience: Mapped[str | None] = mapped_column(default=None)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list)
    matching_instructions: Mapped[str | None] = mapped_column(default=None)

    # 原文（LLM には渡すが構造化対象には含めず、サーバが受領した入力をそのまま保持）。
    raw_text: Mapped[str] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 求人削除時に候補者（および候補者経由でスコア）をカスケード削除する。
    # candidates 側 FK の ON DELETE CASCADE と組み合わせ、DB レベルでも
    # ORM レベルでも求人配下を一括削除できるようにする。
    candidates: Mapped[list["Candidate"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Candidate(Base):
    """応募書類（構造化済み）。

    `job_id` で求人に紐づく。求人削除時は FK の ON DELETE CASCADE で
    一括削除される。配列フィールド（skills / certifications）は JSON カラムで保持する。
    保存後の編集はスコープ外（削除のみ）。
    """

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
    )

    # 構造化フィールド（schemas.CandidateParseResult に対応）。
    name: Mapped[str | None] = mapped_column(default=None)
    age: Mapped[int | None] = mapped_column(default=None)
    nearest_station: Mapped[str | None] = mapped_column(default=None)
    desired_rate: Mapped[int | None] = mapped_column(default=None)
    experience_years: Mapped[int | None] = mapped_column(default=None)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list)
    work_history: Mapped[str | None] = mapped_column(default=None)
    education: Mapped[str | None] = mapped_column(default=None)
    self_pr: Mapped[str | None] = mapped_column(default=None)

    # 原文（LLM には渡すが構造化対象には含めず、サーバが受領した入力をそのまま保持）。
    raw_text: Mapped[str] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    job: Mapped["Job"] = relationship(back_populates="candidates")

    # Score relationship（1候補者に1スコア）。候補者削除時にカスケード削除する。
    score: Mapped["Score | None"] = relationship(
        back_populates="candidate",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Score(Base):
    """マッチングスコア（候補者 × 求人の評価結果）。

    `candidate_id` で候補者に紐づく（1対1）。候補者削除時は FK の ON DELETE CASCADE で
    一括削除される。`requirement_checks` は各必須スキルの充足判定（JSON 配列）。
    再評価時は candidate_id 単位で上書き（upsert）する。
    """

    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True)

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"),
    )

    # LLM が算出した各軸スコア（0〜100）。
    total_score: Mapped[int] = mapped_column()
    skill_score: Mapped[int] = mapped_column()
    experience_score: Mapped[int] = mapped_column()
    industry_score: Mapped[int] = mapped_column()
    position_score: Mapped[int] = mapped_column()

    # 必須要件充足情報。
    required_met: Mapped[int] = mapped_column()  # 充足件数
    required_total: Mapped[int] = mapped_column()  # 全件数

    # 各必須スキルの充足判定（RequirementCheck を dict にシリアライズして保存）。
    requirement_checks: Mapped[list[Any]] = mapped_column(JSON, default=list)

    # LLM が生成したサマリー（日本語）。
    strengths: Mapped[str] = mapped_column()
    concerns: Mapped[str] = mapped_column()
    interview_points: Mapped[str] = mapped_column()

    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    candidate: Mapped["Candidate"] = relationship(back_populates="score")
