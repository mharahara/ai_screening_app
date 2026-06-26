"""テスト共通フィクスチャ。

- 本番 DB を汚さないため、`get_db` 依存性をテスト用のインメモリ SQLite に差し替える。
  インメモリ SQLite は接続ごとに別 DB になり、TestClient が別スレッドを使い得るため、
  `StaticPool` + `check_same_thread=False` で 1 接続を共有して決定的にする。
- LLM は実際に叩かない。デフォルト provider（Ollama）の呼び出しは各テスト側で
  `services.llm._client.chat` を monkeypatch する（このファイルでは差し替えない）。
  Claude provider のテストは `ClaudeProvider` の SDK クライアントをモックする。
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401  # Base.metadata に Job を登録するため import する。
from db import Base, get_db
from main import app


@pytest.fixture
def test_engine():  # type: ignore[no-untyped-def]
    """テスト 1 件ごとに独立したインメモリ SQLite エンジンを供給する。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    """テスト用エンジンに紐づく DB セッション（モデルの往復確認などに使う）。"""
    testing_session_local = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    """get_db をテスト用 DB に差し替えた TestClient。

    lifespan（起動時 init_db）が本番 engine に対して create_all し、本番 DB ファイルを
    生成してしまうため、`init_db` を no-op に差し替えてから lifespan を起動する。
    テーブルは test_engine フィクスチャ側で作成済み。
    """
    testing_session_local = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    # main は init_db を直 import しているため、main 側参照を no-op に差し替える。
    import main as main_module

    monkeypatch.setattr(main_module, "init_db", lambda: None)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _no_real_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """安全網: テスト中に誤って実 Ollama を叩いたら即失敗させる。

    各テストで `services.llm._client.chat` を上書きするのが前提だが、上書き漏れの
    テストがネットワークに出ていかないようデフォルトを差し替えておく。
    """

    def _fail(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "実 Ollama が呼ばれました。テストは services.llm._client.chat を"
            "monkeypatch してください。"
        )

    import services.llm as llm_module

    monkeypatch.setattr(llm_module._client, "chat", _fail)
