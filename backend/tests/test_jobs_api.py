"""jobs API（routers/jobs.py）の契約・失敗系テスト。

Ollama は実際に叩かない。`services.llm._client.chat` を monkeypatch して固定の
構造化結果・例外を返させる。DB は conftest の `client` フィクスチャでテスト用の
インメモリ SQLite に差し替える。
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import services.llm as llm_module
from config import settings
from models import Candidate, Job, Score
from schemas import JobParseResult


def _chat_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


_VALID_PARSE = JobParseResult(
    title="バックエンドエンジニア",
    description="API 開発",
    required_skills=["Python", "FastAPI"],
    preferred_skills=["Go"],
    employment_type=None,
    remote_work=None,
    certifications=["AWS SAA"],
)

_VALID_JOB_PAYLOAD = {
    **_VALID_PARSE.model_dump(),
    "raw_text": "募集: バックエンドエンジニア ...",
}


def _mock_chat(monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    monkeypatch.setattr(llm_module._client, "chat", lambda *a, **k: _chat_response(content))


def _mock_chat_raises(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def _raise(*a: object, **k: object) -> object:
        raise exc

    monkeypatch.setattr(llm_module._client, "chat", _raise)


# --- POST /jobs/parse 正常系 -------------------------------------------------


def test_parse_job_success_returns_structured_with_raw_text(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """妥当な JSON を返す → 200・構造化結果どおり・raw_text 同梱・未保存。"""
    _mock_chat(monkeypatch, _VALID_PARSE.model_dump_json())

    raw = "募集: バックエンドエンジニア。Python/FastAPI 必須。"
    resp = client.post("/jobs/parse", json={"raw_text": raw})

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "バックエンドエンジニア"
    assert body["required_skills"] == ["Python", "FastAPI"]
    assert body["preferred_skills"] == ["Go"]
    assert body["raw_text"] == raw  # 入力をそのまま同梱
    assert "id" not in body  # 未保存（保存スキーマではない）

    # parse は保存しない。
    assert client.get("/jobs").json() == []


def test_parse_job_empty_raw_text_is_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """raw_text が空文字 → 入力検証で 422（LLM は呼ばれない）。"""
    _mock_chat(monkeypatch, _VALID_PARSE.model_dump_json())
    resp = client.post("/jobs/parse", json={"raw_text": ""})
    assert resp.status_code == 422


# --- POST /jobs/parse 失敗系（最重要） --------------------------------------


def test_parse_job_parse_failed_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """壊れた JSON でリトライ上限超過 → 502 PARSE_FAILED（attempts 付き）。"""
    _mock_chat(monkeypatch, '{"required_skills": 123}')

    resp = client.post("/jobs/parse", json={"raw_text": "x"})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "PARSE_FAILED"
    assert detail["attempts"] == settings.parse_max_retries
    assert "message" in detail


def test_parse_job_unavailable_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """接続例外 → 503 LLM_UNAVAILABLE。"""
    _mock_chat_raises(monkeypatch, httpx.ConnectError("refused"))

    resp = client.post("/jobs/parse", json={"raw_text": "x"})

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["code"] == "LLM_UNAVAILABLE"
    assert "message" in detail
    assert "attempts" not in detail  # 接続不可は試行回数を含めない


def test_parse_job_timeout_returns_502_llm_timeout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """タイムアウト → 502 LLM_TIMEOUT（attempts 付き）。"""
    _mock_chat_raises(monkeypatch, httpx.TimeoutException("timed out"))

    resp = client.post("/jobs/parse", json={"raw_text": "x"})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "LLM_TIMEOUT"
    assert detail["attempts"] == settings.parse_max_retries


# --- POST /jobs 保存 ---------------------------------------------------------


def test_create_job_returns_201_job_out(client: TestClient) -> None:
    """妥当な入力 → 201 で JobOut（id / created_at / 全フィールド）。"""
    resp = client.post("/jobs", json=_VALID_JOB_PAYLOAD)

    assert resp.status_code == 201
    body = resp.json()
    assert isinstance(body["id"], int)
    assert body["title"] == "バックエンドエンジニア"
    assert body["required_skills"] == ["Python", "FastAPI"]
    assert body["raw_text"] == _VALID_JOB_PAYLOAD["raw_text"]
    assert "created_at" in body


def test_create_job_missing_required_field_is_422(client: TestClient) -> None:
    """必須フィールド（raw_text）欠落 → 422。"""
    payload = {**_VALID_PARSE.model_dump()}  # raw_text なし
    resp = client.post("/jobs", json=payload)
    assert resp.status_code == 422


def test_create_job_type_mismatch_is_422(client: TestClient) -> None:
    """型不一致（required_skills が配列でない）→ 422。"""
    payload = {**_VALID_JOB_PAYLOAD, "required_skills": "Python"}
    resp = client.post("/jobs", json=payload)
    assert resp.status_code == 422


def test_create_job_invalid_enum_is_422(client: TestClient) -> None:
    """enum 範囲外（employment_type）→ 422。"""
    payload = {**_VALID_JOB_PAYLOAD, "employment_type": "なんでもない"}
    resp = client.post("/jobs", json=payload)
    assert resp.status_code == 422


# --- GET /jobs ---------------------------------------------------------------


def test_list_jobs_empty_returns_empty_list(client: TestClient) -> None:
    """0 件は空配列 []。"""
    resp = client.get("/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_jobs_returns_summary_fields(client: TestClient) -> None:
    """保存済みが id / title / created_at のサマリー形で返る。"""
    client.post("/jobs", json={**_VALID_JOB_PAYLOAD, "title": "求人A"})

    resp = client.get("/jobs")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    # サマリーは id / title / created_at のみ。
    assert set(items[0].keys()) == {"id", "title", "created_at"}
    assert items[0]["title"] == "求人A"


def test_list_jobs_ordered_by_created_at_desc(client: TestClient, db_session: Session) -> None:
    """created_at 降順で返る。

    `func.now()` は秒粒度で同一秒の挿入順は不定になり得るため、created_at を明示的に
    異なる値で投入して決定的に検証する（client と db_session は同じ test_engine を共有）。
    """
    older = Job(
        title="古い求人",
        raw_text="原文",
        created_at=datetime(2026, 1, 1, 10, 0, 0),
    )
    newer = Job(
        title="新しい求人",
        raw_text="原文",
        created_at=datetime(2026, 6, 1, 10, 0, 0),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    items = client.get("/jobs").json()
    titles = [item["title"] for item in items]
    assert titles == ["新しい求人", "古い求人"]


# --- DELETE /jobs/{id} -------------------------------------------------------


def test_delete_job_returns_204_and_removes(client: TestClient) -> None:
    """削除で 204、その後一覧から消える。"""
    created = client.post("/jobs", json=_VALID_JOB_PAYLOAD).json()
    job_id = created["id"]

    resp = client.delete(f"/jobs/{job_id}")
    assert resp.status_code == 204
    assert resp.content == b""

    assert client.get("/jobs").json() == []


def test_delete_job_not_found_returns_404(client: TestClient) -> None:
    """存在しない id の削除 → 404。"""
    resp = client.delete("/jobs/99999")
    assert resp.status_code == 404


# --- 保存後の編集は不可（PUT/PATCH 未実装） ----------------------------------


def test_put_job_not_allowed(client: TestClient) -> None:
    """PUT /jobs/{id} は未実装（404 か 405）。求人は保存後に編集できない。"""
    created = client.post("/jobs", json=_VALID_JOB_PAYLOAD).json()
    resp = client.put(f"/jobs/{created['id']}", json=_VALID_JOB_PAYLOAD)
    assert resp.status_code in (404, 405)


def test_patch_job_not_allowed(client: TestClient) -> None:
    """PATCH /jobs/{id} は未実装（404 か 405）。"""
    created = client.post("/jobs", json=_VALID_JOB_PAYLOAD).json()
    resp = client.patch(f"/jobs/{created['id']}", json={"title": "変更"})
    assert resp.status_code in (404, 405)


# --- 構造化結果の通り道（parse → create） ------------------------------------


def test_parse_then_create_roundtrip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """parse の結果（model_validate_json 復元）をそのまま create に渡して保存できる。"""
    _mock_chat(monkeypatch, _VALID_PARSE.model_dump_json())

    parsed = client.post("/jobs/parse", json={"raw_text": "原文テキスト"}).json()
    created = client.post("/jobs", json=parsed)

    assert created.status_code == 201
    body = created.json()
    assert body["title"] == parsed["title"]
    assert body["required_skills"] == parsed["required_skills"]
    assert body["raw_text"] == "原文テキスト"


# --- GET /jobs/{id} ----------------------------------------------------------


def test_get_job_returns_summary_fields(client: TestClient) -> None:
    """保存済み求人を id で取得すると JobOut の全フィールドが返る。"""
    created = client.post("/jobs", json=_VALID_JOB_PAYLOAD).json()
    job_id = created["id"]

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()

    expected_fields = {
        "id",
        "created_at",
        "raw_text",
        "matching_instructions",
        "title",
        "description",
        "required_skills",
        "preferred_skills",
        "ideal_profile",
        "employment_type",
        "location",
        "remote_work",
        "rate_min",
        "rate_max",
        "min_experience_years",
        "position_level",
        "industry_experience",
        "certifications",
    }
    assert set(body.keys()) == expected_fields
    assert body["id"] == job_id
    assert body["title"] == _VALID_JOB_PAYLOAD["title"]
    assert "raw_text" in body
    assert body["raw_text"] == _VALID_JOB_PAYLOAD["raw_text"]


def test_get_job_not_found_returns_404(client: TestClient) -> None:
    """存在しない job_id は 404 を返す。"""
    resp = client.get("/jobs/99999")
    assert resp.status_code == 404


# --- GET /jobs/{id}/rankings ------------------------------------------------


def _make_candidate_with_score(db: Session, job_id: int, name: str, total_score: int) -> Candidate:
    """スコアあり候補者を DB に保存して返す。"""
    candidate = Candidate(job_id=job_id, name=name, skills=[], raw_text="原文")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    score = Score(
        candidate_id=candidate.id,
        total_score=total_score,
        skill_score=total_score,
        experience_score=total_score,
        industry_score=total_score,
        position_score=total_score,
        required_met=1,
        required_total=1,
        requirement_checks=[],
        strengths="強み",
        concerns="懸念",
        interview_points="確認事項",
        scored_at=datetime.now(tz=UTC),
    )
    db.add(score)
    db.commit()
    return candidate


def _make_candidate_without_score(db: Session, job_id: int, name: str) -> Candidate:
    """スコアなし候補者を DB に保存して返す。"""
    candidate = Candidate(job_id=job_id, name=name, skills=[], raw_text="原文")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def test_get_rankings_returns_candidates_sorted_by_score(
    client: TestClient, db_session: Session
) -> None:
    """スコアありの候補者が total_score 降順で返る。"""
    job = Job(title="求人", required_skills=[], raw_text="原文")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    _make_candidate_with_score(db_session, job.id, "候補者A", total_score=60)
    _make_candidate_with_score(db_session, job.id, "候補者B", total_score=90)
    _make_candidate_with_score(db_session, job.id, "候補者C", total_score=75)

    resp = client.get(f"/jobs/{job.id}/rankings")
    assert resp.status_code == 200
    items = resp.json()
    scores = [item["total_score"] for item in items]
    assert scores == [90, 75, 60]


def test_get_rankings_null_score_candidates_at_end(client: TestClient, db_session: Session) -> None:
    """スコアなし候補者は total_score=null で末尾に含まれる。"""
    job = Job(title="求人", required_skills=[], raw_text="原文")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    _make_candidate_with_score(db_session, job.id, "スコアあり", total_score=80)
    _make_candidate_without_score(db_session, job.id, "スコアなし")

    resp = client.get(f"/jobs/{job.id}/rankings")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert items[0]["total_score"] == 80
    assert items[0]["name"] == "スコアあり"
    assert items[1]["total_score"] is None
    assert items[1]["name"] == "スコアなし"


def test_get_rankings_not_found(client: TestClient) -> None:
    """存在しない job_id への rankings は 404。"""
    resp = client.get("/jobs/99999/rankings")
    assert resp.status_code == 404


def test_get_rankings_empty(client: TestClient, db_session: Session) -> None:
    """候補者が0人のとき空配列を返す。"""
    job = Job(title="求人", required_skills=[], raw_text="原文")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    resp = client.get(f"/jobs/{job.id}/rankings")
    assert resp.status_code == 200
    assert resp.json() == []
