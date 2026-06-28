"""candidates API（routers/candidates.py）の契約・失敗系テスト。

Ollama は実際に叩かない。`services.llm._client.chat` を monkeypatch して固定の
構造化結果・例外を返させる。DB は conftest の `client` フィクスチャでテスト用の
インメモリ SQLite に差し替える。test_jobs_api.py と同じヘルパ流儀に揃える。
"""

import json as json_module
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import db as db_module
import services.llm as llm_module
import services.matching as matching_module
from config import settings
from models import Candidate, Job, Score
from schemas import CandidateParseResult, JobParseResult


def _chat_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


_VALID_PARSE = CandidateParseResult(
    name="山田太郎",
    age=32,
    nearest_station="渋谷",
    desired_rate=80,
    experience_years=8,
    skills=["Python", "FastAPI"],
    certifications=["AWS SAA"],
    work_history="Web バックエンド開発に従事。",
    education="情報工学修士",
    self_pr="設計が得意です。",
)

_VALID_JOB_PARSE = JobParseResult(
    title="バックエンドエンジニア",
    required_skills=["Python", "FastAPI"],
)

_VALID_JOB_PAYLOAD = {
    **_VALID_JOB_PARSE.model_dump(),
    "raw_text": "募集: バックエンドエンジニア ...",
}


def _mock_chat(monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    monkeypatch.setattr(llm_module._client, "chat", lambda *a, **k: _chat_response(content))


def _mock_chat_raises(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def _raise(*a: object, **k: object) -> object:
        raise exc

    monkeypatch.setattr(llm_module._client, "chat", _raise)


def _create_job(client: TestClient) -> int:
    """求人を 1 件作成して job_id を返す（候補者保存の前提）。"""
    resp = client.post("/jobs", json=_VALID_JOB_PAYLOAD)
    assert resp.status_code == 201
    return int(resp.json()["id"])


def _count_candidates(db_session: Session) -> int:
    db_session.expire_all()
    return db_session.scalar(select(func.count()).select_from(Candidate)) or 0


# --- POST /candidates/parse 正常系 ------------------------------------------


def test_parse_candidate_success_returns_structured_with_raw_text(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """妥当な JSON を返す → 200・構造化結果どおり・raw_text 同梱・未保存（id なし）。"""
    _mock_chat(monkeypatch, _VALID_PARSE.model_dump_json())

    raw = "氏名: 山田太郎。Python/FastAPI の実務経験 8 年。"
    resp = client.post("/candidates/parse", json={"raw_text": raw})

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "山田太郎"
    assert body["age"] == 32
    assert body["skills"] == ["Python", "FastAPI"]
    assert body["certifications"] == ["AWS SAA"]
    assert body["raw_text"] == raw  # 入力をそのまま同梱
    assert "id" not in body  # 未保存（保存スキーマではない）

    # parse は保存しない（候補者一覧 API が無いため DB で件数 0 を確認）。
    assert _count_candidates(db_session) == 0


def test_parse_candidate_empty_raw_text_is_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """raw_text が空文字 → 入力検証で 422（LLM は呼ばれない）。"""
    _mock_chat(monkeypatch, _VALID_PARSE.model_dump_json())
    resp = client.post("/candidates/parse", json={"raw_text": ""})
    assert resp.status_code == 422


# --- POST /candidates/parse 失敗系（最重要） -------------------------------


def test_parse_candidate_parse_failed_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """壊れた JSON でリトライ上限超過 → 502 PARSE_FAILED（attempts 付き）。"""
    _mock_chat(monkeypatch, '{"skills": 123}')

    resp = client.post("/candidates/parse", json={"raw_text": "x"})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "PARSE_FAILED"
    assert detail["attempts"] == settings.parse_max_retries
    assert "message" in detail


def test_parse_candidate_unavailable_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """接続例外 → 503 LLM_UNAVAILABLE（attempts を含めない）。"""
    _mock_chat_raises(monkeypatch, httpx.ConnectError("refused"))

    resp = client.post("/candidates/parse", json={"raw_text": "x"})

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["code"] == "LLM_UNAVAILABLE"
    assert "message" in detail
    assert "attempts" not in detail  # 接続不可は試行回数を含めない


def test_parse_candidate_timeout_returns_502_llm_timeout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """タイムアウト → 502 LLM_TIMEOUT（attempts 付き）。"""
    _mock_chat_raises(monkeypatch, httpx.TimeoutException("timed out"))

    resp = client.post("/candidates/parse", json={"raw_text": "x"})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "LLM_TIMEOUT"
    assert detail["attempts"] == settings.parse_max_retries


# --- POST /candidates 保存 --------------------------------------------------


def test_create_candidate_returns_201_candidate_out(
    client: TestClient, db_session: Session
) -> None:
    """妥当な入力 → 201 で CandidateOut（id / created_at / 全フィールド）・永続化。"""
    job_id = _create_job(client)

    payload = {
        **_VALID_PARSE.model_dump(),
        "job_id": job_id,
        "raw_text": "応募書類の原文テキスト。",
    }
    resp = client.post("/candidates", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert isinstance(body["id"], int)
    assert body["name"] == "山田太郎"
    assert body["skills"] == ["Python", "FastAPI"]
    assert body["job_id"] == job_id
    assert body["raw_text"] == "応募書類の原文テキスト。"
    assert "created_at" in body

    # DB に永続化されていること（raw_text / job_id を実体で確認）。
    db_session.expire_all()
    saved = db_session.get(Candidate, body["id"])
    assert saved is not None
    assert saved.job_id == job_id
    assert saved.raw_text == "応募書類の原文テキスト。"


def test_create_candidate_unknown_job_id_returns_404(client: TestClient) -> None:
    """存在しない job_id → 404。"""
    payload = {
        **_VALID_PARSE.model_dump(),
        "job_id": 99999,
        "raw_text": "原文。",
    }
    resp = client.post("/candidates", json=payload)
    assert resp.status_code == 404


def test_create_candidate_missing_required_field_is_422(client: TestClient) -> None:
    """必須フィールド（raw_text / job_id）欠落 → 422。"""
    # raw_text 欠落
    payload_no_raw = {**_VALID_PARSE.model_dump(), "job_id": 1}
    assert client.post("/candidates", json=payload_no_raw).status_code == 422

    # job_id 欠落
    payload_no_job = {**_VALID_PARSE.model_dump(), "raw_text": "原文。"}
    assert client.post("/candidates", json=payload_no_job).status_code == 422


# --- DELETE /candidates/{id} ------------------------------------------------


def test_delete_candidate_returns_204(client: TestClient) -> None:
    """作成 → 削除で 204、content 空。"""
    job_id = _create_job(client)
    created = client.post(
        "/candidates",
        json={**_VALID_PARSE.model_dump(), "job_id": job_id, "raw_text": "原文。"},
    ).json()

    resp = client.delete(f"/candidates/{created['id']}")
    assert resp.status_code == 204
    assert resp.content == b""


def test_delete_candidate_not_found_returns_404(client: TestClient) -> None:
    """存在しない id の削除 → 404。"""
    resp = client.delete("/candidates/99999")
    assert resp.status_code == 404


# --- 構造化結果の通り道（parse → create） -----------------------------------


def test_parse_then_create_roundtrip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """parse の結果（model_validate_json 復元）に job_id を足して create に渡せる。"""
    _mock_chat(monkeypatch, _VALID_PARSE.model_dump_json())
    job_id = _create_job(client)

    parsed = client.post("/candidates/parse", json={"raw_text": "原文テキスト"}).json()
    created = client.post("/candidates", json={**parsed, "job_id": job_id})

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == parsed["name"]
    assert body["skills"] == parsed["skills"]
    assert body["raw_text"] == "原文テキスト"
    assert body["job_id"] == job_id


# --- カスケード削除（FK pragma の検証・最重要） -----------------------------


def test_delete_job_cascades_candidates(client: TestClient, db_session: Session) -> None:
    """求人削除で紐づく候補者も DB から消える（FK ON DELETE CASCADE）。

    candidate 取得用 GET API が無いため DB セッションで残存件数を確認する。
    identity-map キャッシュを避けるため expire_all してから select で件数を数える
    （ORM relationship 経由でない経路で「DB レベルで消えた」ことを示す）。
    """
    job_id = _create_job(client)
    created = client.post(
        "/candidates",
        json={**_VALID_PARSE.model_dump(), "job_id": job_id, "raw_text": "原文。"},
    ).json()
    candidate_id = created["id"]

    # 削除前は確かに存在する。
    assert _count_candidates(db_session) == 1

    resp = client.delete(f"/jobs/{job_id}")
    assert resp.status_code == 204

    # 求人配下の候補者が DB から消えていること（件数 0・対象 id も不在）。
    db_session.expire_all()
    assert _count_candidates(db_session) == 0
    remaining = db_session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.id == candidate_id)
    )
    assert remaining == 0


# --- POST /candidates → BackgroundTasks → scores 保存 ----------------------


def _patch_session_local(monkeypatch: pytest.MonkeyPatch, test_engine: object) -> None:
    """match_candidate が内部で生成する SessionLocal をテスト用 engine に向ける。"""
    testing_sl = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)  # type: ignore[call-overload]
    monkeypatch.setattr(db_module, "SessionLocal", testing_sl)
    monkeypatch.setattr(matching_module, "SessionLocal", testing_sl)


def _mock_match_chat(monkeypatch: pytest.MonkeyPatch, required_skills: list[str]) -> None:
    """Ollama をモックし、required_skills に対応する requirement_checks を返す。"""
    checks = [
        {"requirement": s, "status": "充足", "evidence": f"{s} 経験あり"} for s in required_skills
    ]
    content = json_module.dumps(
        {
            "skill_score": 80,
            "experience_score": 70,
            "industry_score": 60,
            "position_score": 75,
            "requirement_checks": checks,
            "strengths": "強み",
            "concerns": "懸念",
            "interview_points": "確認事項",
        }
    )
    monkeypatch.setattr(
        llm_module._client,
        "chat",
        lambda *a, **k: SimpleNamespace(message=SimpleNamespace(content=content)),
    )


def test_create_candidate_triggers_background_match(
    client: TestClient,
    db_session: Session,
    test_engine: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /candidates 後に BackgroundTasks が同期実行され scores に1行保存される。"""
    _patch_session_local(monkeypatch, test_engine)
    # required_skills は _VALID_JOB_PAYLOAD の ["Python", "FastAPI"]。
    _mock_match_chat(monkeypatch, ["Python", "FastAPI"])

    job_id = _create_job(client)
    resp = client.post(
        "/candidates",
        json={**_VALID_PARSE.model_dump(), "job_id": job_id, "raw_text": "原文。"},
    )
    assert resp.status_code == 201

    # TestClient では BackgroundTasks がレスポンス後に同期実行される。
    db_session.expire_all()
    count = db_session.scalar(select(func.count()).select_from(Score))
    assert count == 1


# --- GET /candidates/{id}/detail -------------------------------------------


def _make_score(db: Session, candidate_id: int, total_score: int = 75) -> Score:
    """テスト用 Score を DB に保存して返す。"""
    score = Score(
        candidate_id=candidate_id,
        total_score=total_score,
        skill_score=80,
        experience_score=70,
        industry_score=60,
        position_score=75,
        required_met=2,
        required_total=2,
        requirement_checks=[{"requirement": "Python", "status": "充足", "evidence": "経験あり"}],
        strengths="強み",
        concerns="懸念",
        interview_points="確認事項",
        scored_at=datetime.now(tz=UTC),
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


def test_get_candidate_detail_with_score(client: TestClient, db_session: Session) -> None:
    """スコアがある候補者の detail が 200 でスコアを含めて返る。"""
    job = Job(title="求人", required_skills=["Python"], raw_text="原文")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    candidate = Candidate(job_id=job.id, name="山田太郎", skills=["Python"], raw_text="原文")
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    _make_score(db_session, candidate.id, total_score=85)

    resp = client.get(f"/candidates/{candidate.id}/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == candidate.id
    assert body["name"] == "山田太郎"
    assert body["raw_text"] == "原文"
    assert body["score"] is not None
    assert body["score"]["total_score"] == 85
    assert body["score"]["strengths"] == "強み"
    assert body["score"]["concerns"] == "懸念"


def test_get_candidate_detail_without_score(client: TestClient, db_session: Session) -> None:
    """スコア未算出の候補者の detail が 200 で score=null を返す。"""
    job = Job(title="求人", required_skills=[], raw_text="原文")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    candidate = Candidate(job_id=job.id, name="鈴木花子", skills=[], raw_text="原文")
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    resp = client.get(f"/candidates/{candidate.id}/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == candidate.id
    assert body["score"] is None


def test_get_candidate_detail_not_found(client: TestClient) -> None:
    """存在しない candidate_id への detail は 404。"""
    resp = client.get("/candidates/99999/detail")
    assert resp.status_code == 404
