"""DB / モデルのテスト。

- `init_db()` 相当（create_all）で `jobs` テーブルが生成されること。
- JSON カラム（required_skills / preferred_skills / certifications）が配列として
  往復保存・取得できること（null も含めて素直に復元されること）。

本番 DB を汚さないため、conftest のインメモリ SQLite（test_engine / db_session）を使う。
"""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db import Base
from models import Job


def test_create_all_generates_jobs_table() -> None:
    """create_all（init_db と同じ仕組み）でインメモリ SQLite に jobs テーブルができる。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        Base.metadata.create_all(bind=engine)
        tables = inspect(engine).get_table_names()
        assert "jobs" in tables

        columns = {c["name"] for c in inspect(engine).get_columns("jobs")}
        # 主要カラムが揃っていること。
        for expected in (
            "id",
            "title",
            "required_skills",
            "preferred_skills",
            "certifications",
            "raw_text",
            "created_at",
        ):
            assert expected in columns
    finally:
        engine.dispose()


def test_json_columns_roundtrip(db_session: Session) -> None:
    """JSON カラムが配列として往復し、null も素直に復元される。"""
    job = Job(
        title="バックエンドエンジニア",
        description=None,
        required_skills=["Python", "FastAPI", "SQLAlchemy"],
        preferred_skills=["Go"],
        certifications=["AWS SAA", "応用情報"],
        rate_min=60,
        rate_max=90,
        raw_text="原文",
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    db_session.expire_all()
    fetched = db_session.get(Job, job_id)
    assert fetched is not None

    assert fetched.required_skills == ["Python", "FastAPI", "SQLAlchemy"]
    assert fetched.preferred_skills == ["Go"]
    assert fetched.certifications == ["AWS SAA", "応用情報"]
    assert isinstance(fetched.required_skills, list)
    assert fetched.description is None
    assert fetched.created_at is not None


def test_json_columns_default_empty_list(db_session: Session) -> None:
    """配列カラムを省略すると空配列がデフォルトで入る。"""
    job = Job(title="最小求人", raw_text="原文")
    db_session.add(job)
    db_session.commit()
    db_session.expire_all()

    fetched = db_session.get(Job, job.id)
    assert fetched is not None
    assert fetched.required_skills == []
    assert fetched.preferred_skills == []
    assert fetched.certifications == []
