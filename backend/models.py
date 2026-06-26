"""SQLAlchemy モデル（Job / Candidate / Score 等）。

SQLAlchemy 2.0 の `Mapped[...]` 記法で定義する。配列・タグ・チェックリストは
JSON カラムで保持する。日時カラムは `DateTime(timezone=True)`。

本 issue（求人要件登録）のスコープは `Job` モデルの完成までで、Candidate /
Score の本体実装は後続 issue が行う。ただし求人削除時に候補者・スコアを
カスケード削除できるよう、Job 側の関係定義の素地（cascade 設定の意図）を残す。
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from db import Base
from schemas import EmploymentType, PositionLevel, RemoteWork


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
    employment_type: Mapped[EmploymentType | None] = mapped_column(default=None)
    location: Mapped[str | None] = mapped_column(default=None)
    remote_work: Mapped[RemoteWork | None] = mapped_column(default=None)
    rate_min: Mapped[int | None] = mapped_column(default=None)
    rate_max: Mapped[int | None] = mapped_column(default=None)
    min_experience_years: Mapped[int | None] = mapped_column(default=None)
    position_level: Mapped[PositionLevel | None] = mapped_column(default=None)
    industry_experience: Mapped[str | None] = mapped_column(default=None)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list)

    # 原文（LLM には渡すが構造化対象には含めず、サーバが受領した入力をそのまま保持）。
    raw_text: Mapped[str] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # NOTE: 求人削除時に候補者・スコアをカスケード削除するための関係の素地。
    # Candidate モデルは後続 issue で実装する。実装時は以下のような relationship を
    # 追加し、candidates 側 FK の ON DELETE CASCADE と組み合わせて求人配下を
    # 一括削除できるようにする（scores は candidates 経由でさらにカスケード）。
    #
    #   from sqlalchemy.orm import relationship
    #   candidates: Mapped[list["Candidate"]] = relationship(
    #       back_populates="job",
    #       cascade="all, delete-orphan",
    #       passive_deletes=True,
    #   )
