"""DB セッション・初期化（SQLite）。

SQLAlchemy 2.0。Engine / SessionLocal / Base（DeclarativeBase）を定義し、
起動時に `init_db()` で `create_all` する（Alembic は使わない）。
FastAPI の依存性注入には `get_db()` を使う。
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings

# SQLite はデフォルトで接続を生成したスレッドでしか使えない。
# FastAPI はリクエストごとに別スレッドを使い得るため、check_same_thread を無効化する。
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy モデルの基底クラス。"""


def init_db() -> None:
    """全テーブルを作成する（存在すれば何もしない）。

    モデルを import して `Base.metadata` に登録された状態で呼ぶ必要がある。
    """
    # モデル定義を Base.metadata に登録するために import する。
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """リクエストスコープの DB セッションを供給する依存性。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
