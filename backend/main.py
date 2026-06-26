"""FastAPI エントリポイント。

各 router を集約するだけの薄い層に保つ。
ビジネスロジックは services/ に寄せる。
起動時に DB を初期化する（Alembic は使わず create_all）。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import init_db
from routers import jobs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """起動時に DB テーブルを作成する。"""
    init_db()
    yield


app = FastAPI(title="RabbitPick API", lifespan=lifespan)

app.include_router(jobs.router)


@app.get("/health")
def health() -> dict[str, str]:
    """ヘルスチェック。常に 200 / {"status": "ok"} を返す。"""
    return {"status": "ok"}
