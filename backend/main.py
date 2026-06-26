"""FastAPI エントリポイント。

各 router を集約するだけの薄い層に保つ。
ビジネスロジックは services/ に寄せる。
"""

from fastapi import FastAPI

app = FastAPI(title="RabbitPick API")


@app.get("/health")
def health() -> dict[str, str]:
    """ヘルスチェック。常に 200 / {"status": "ok"} を返す。"""
    return {"status": "ok"}


# TODO(後続 issue): routers/ を import して app.include_router(...) で集約する。
