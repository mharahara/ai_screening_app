"""services/matching.py のユニット・統合テスト。

- compute_total_score: 純粋関数の数値検証
- evaluate_match: structured_chat への通り道（_RecordingStructuredChat パターン）
- match_candidate: DB 保存・upsert・例外を伝播しないこと
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import services.llm as llm_module
import services.matching as matching_module
from models import Candidate, Job, Score
from schemas import MatchResult, RequirementCheck, RequirementStatus
from services.llm import LLMUnavailableError, ParseFailedError

# ---------------------------------------------------------------------------
# テスト用データ定義
# ---------------------------------------------------------------------------

_VALID_MATCH_RESULT = MatchResult(
    skill_score=80,
    experience_score=70,
    industry_score=60,
    position_score=75,
    requirement_checks=[
        RequirementCheck(
            requirement="Python",
            status=RequirementStatus.MET,
            evidence="Python 3年",
        ),
        RequirementCheck(
            requirement="FastAPI",
            status=RequirementStatus.MET,
            evidence="FastAPI 実務経験あり",
        ),
    ],
    strengths="強み",
    concerns="懸念",
    interview_points="確認事項",
)


def _make_job(db: Session, required_skills: list[str] | None = None) -> Job:
    """テスト用 Job を DB に保存して返す。"""
    job = Job(
        title="バックエンドエンジニア",
        required_skills=required_skills if required_skills is not None else ["Python", "FastAPI"],
        raw_text="求人原文",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _make_candidate(db: Session, job_id: int) -> Candidate:
    """テスト用 Candidate を DB に保存して返す。"""
    candidate = Candidate(
        job_id=job_id,
        name="山田太郎",
        skills=["Python", "FastAPI"],
        experience_years=5,
        raw_text="応募書類原文",
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


# ---------------------------------------------------------------------------
# _RecordingStructuredChat パターン
# ---------------------------------------------------------------------------


class _RecordingStructuredChat:
    """`structured_chat` を置き換え、呼び出し kwargs を記録して固定値を返す。"""

    def __init__(self, return_value: object) -> None:
        self._return_value = return_value
        self.calls: list[dict[str, object]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self._return_value


# ---------------------------------------------------------------------------
# compute_total_score の純粋関数テスト
# ---------------------------------------------------------------------------


def test_compute_total_score_equal_weights() -> None:
    """重みが等しいとき単純平均になる。"""
    result = MatchResult(
        skill_score=80,
        experience_score=60,
        industry_score=40,
        position_score=20,
        requirement_checks=[],
        strengths="",
        concerns="",
        interview_points="",
    )
    weights = {"skill": 1.0, "experience": 1.0, "industry": 1.0, "position": 1.0}
    total = matching_module.compute_total_score(result, weights)
    assert total == round((80 + 60 + 40 + 20) / 4)


def test_compute_total_score_weighted_average() -> None:
    """重み付け平均の数値検証: skill=80,exp=60,ind=40,pos=20, 重み 0.4/0.2/0.2/0.2 → 56。"""
    result = MatchResult(
        skill_score=80,
        experience_score=60,
        industry_score=40,
        position_score=20,
        requirement_checks=[],
        strengths="",
        concerns="",
        interview_points="",
    )
    weights = {"skill": 0.4, "experience": 0.2, "industry": 0.2, "position": 0.2}
    total = matching_module.compute_total_score(result, weights)
    expected = round(80 * 0.4 + 60 * 0.2 + 40 * 0.2 + 20 * 0.2)
    assert total == expected  # == 56


def test_compute_total_score_normalizes_weights() -> None:
    """重みの合計が 1.0 でない場合に正規化される（全重みを 2 倍しても結果が同じ）。"""
    result = MatchResult(
        skill_score=80,
        experience_score=60,
        industry_score=40,
        position_score=20,
        requirement_checks=[],
        strengths="",
        concerns="",
        interview_points="",
    )
    weights_a = {"skill": 0.4, "experience": 0.2, "industry": 0.2, "position": 0.2}
    weights_b = {"skill": 0.8, "experience": 0.4, "industry": 0.4, "position": 0.4}
    score_a = matching_module.compute_total_score(result, weights_a)
    score_b = matching_module.compute_total_score(result, weights_b)
    assert score_a == score_b


def test_compute_total_score_boundary() -> None:
    """スコア 0 と 100 の境界値が正しく計算される。"""
    all_zero = MatchResult(
        skill_score=0,
        experience_score=0,
        industry_score=0,
        position_score=0,
        requirement_checks=[],
        strengths="",
        concerns="",
        interview_points="",
    )
    all_hundred = MatchResult(
        skill_score=100,
        experience_score=100,
        industry_score=100,
        position_score=100,
        requirement_checks=[],
        strengths="",
        concerns="",
        interview_points="",
    )
    weights = {"skill": 0.4, "experience": 0.2, "industry": 0.2, "position": 0.2}
    assert matching_module.compute_total_score(all_zero, weights) == 0
    assert matching_module.compute_total_score(all_hundred, weights) == 100


# ---------------------------------------------------------------------------
# evaluate_match の通り道テスト
# ---------------------------------------------------------------------------


def test_evaluate_match_calls_structured_chat_with_expected_args(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """structured_chat が1回呼ばれ、schema=MatchResult・プロンプトに期待キーワードが含まれる。"""
    job = _make_job(db_session, required_skills=["Python", "FastAPI"])
    candidate = _make_candidate(db_session, job_id=job.id)

    fake = _RecordingStructuredChat(_VALID_MATCH_RESULT)
    monkeypatch.setattr(matching_module, "structured_chat", fake)

    result = matching_module.evaluate_match(job, candidate)

    assert result is _VALID_MATCH_RESULT
    assert len(fake.calls) == 1

    kwargs = fake.calls[0]

    # schema=MatchResult で呼ばれること。
    assert kwargs["schema"] is MatchResult

    # system プロンプトに評価観点のキーワードが含まれること。
    system = kwargs["system"]
    assert isinstance(system, str)
    for keyword in (
        "requirement_checks",
        "skill_score",
        "experience_score",
        "industry_score",
        "position_score",
    ):
        assert keyword in system

    # user プロンプトに求人・候補者データが含まれること。
    user = kwargs["user"]
    assert isinstance(user, str)
    assert "Python" in user
    assert "FastAPI" in user
    assert "山田太郎" in user


def test_evaluate_match_retries_on_requirement_checks_count_mismatch(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """requirement_checks 件数が required_skills と不一致のとき再試行し上限超過で失敗する。"""
    # required_skills は 2 件だが、requirement_checks を 1 件しか返すモックを用意する。
    job = _make_job(db_session, required_skills=["Python", "FastAPI"])
    candidate = _make_candidate(db_session, job_id=job.id)

    mismatch_result = MatchResult(
        skill_score=80,
        experience_score=70,
        industry_score=60,
        position_score=75,
        requirement_checks=[
            RequirementCheck(
                requirement="Python",
                status=RequirementStatus.MET,
                evidence="Python 3年",
            ),
            # FastAPI の分が欠落（合計 1 件 → 不一致）
        ],
        strengths="強み",
        concerns="懸念",
        interview_points="確認事項",
    )

    call_count = 0

    def always_mismatch(*args: object, **kwargs: object) -> MatchResult:
        nonlocal call_count
        call_count += 1
        return mismatch_result

    monkeypatch.setattr(matching_module, "structured_chat", always_mismatch)

    from config import settings

    with pytest.raises(ParseFailedError):
        matching_module.evaluate_match(job, candidate)

    # parse_max_retries 回だけ試行したことを確認する。
    assert call_count == settings.parse_max_retries


# ---------------------------------------------------------------------------
# match_candidate のテスト
# ---------------------------------------------------------------------------

# match_candidate は内部で SessionLocal() を生成するため、db モジュールの
# SessionLocal を monkeypatch してテスト用セッションを使わせる。


def _mock_chat_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama をモックして MatchResult 相当の JSON を返す。"""
    import json

    content = json.dumps(
        {
            "skill_score": 80,
            "experience_score": 70,
            "industry_score": 60,
            "position_score": 75,
            "requirement_checks": [
                {"requirement": "Python", "status": "充足", "evidence": "Python 3年"},
                {"requirement": "FastAPI", "status": "充足", "evidence": "FastAPI 実務"},
            ],
            "strengths": "強み",
            "concerns": "懸念",
            "interview_points": "確認事項",
        }
    )

    from types import SimpleNamespace

    monkeypatch.setattr(
        llm_module._client,
        "chat",
        lambda *a, **k: SimpleNamespace(message=SimpleNamespace(content=content)),
    )


def _patch_session_local(monkeypatch: pytest.MonkeyPatch, test_engine: object) -> None:
    """match_candidate が内部で生成する SessionLocal をテスト用 engine に向ける。"""
    import db as db_module

    testing_session_local = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)  # type: ignore[call-overload]
    monkeypatch.setattr(db_module, "SessionLocal", testing_session_local)
    # matching.py は db.SessionLocal を直接 import しているため matching_module 側も差し替える。
    monkeypatch.setattr(matching_module, "SessionLocal", testing_session_local)


def test_match_candidate_saves_score_to_db(
    test_engine: object,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """match_candidate 実行後に scores テーブルに 1 行保存され total_score が計算結果と一致する。"""
    _patch_session_local(monkeypatch, test_engine)
    _mock_chat_valid(monkeypatch)

    job = _make_job(db_session)
    candidate = _make_candidate(db_session, job_id=job.id)

    matching_module.match_candidate(candidate.id)

    db_session.expire_all()
    count = db_session.scalar(select(func.count()).select_from(Score))
    assert count == 1

    score = db_session.scalar(select(Score).where(Score.candidate_id == candidate.id))
    assert score is not None

    # total_score は compute_total_score と一致する（設定値の重みで計算）。
    from config import settings

    expected_total = matching_module.compute_total_score(
        _VALID_MATCH_RESULT,
        {
            "skill": settings.match_weight_skill,
            "experience": settings.match_weight_experience,
            "industry": settings.match_weight_industry,
            "position": settings.match_weight_position,
        },
    )
    assert score.total_score == expected_total


def test_match_candidate_upserts_score(
    test_engine: object,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2 回 match_candidate を呼んでも scores テーブルが 1 行のみ（upsert）。"""
    _patch_session_local(monkeypatch, test_engine)
    _mock_chat_valid(monkeypatch)

    job = _make_job(db_session)
    candidate = _make_candidate(db_session, job_id=job.id)

    matching_module.match_candidate(candidate.id)
    matching_module.match_candidate(candidate.id)

    db_session.expire_all()
    count = db_session.scalar(select(func.count()).select_from(Score))
    assert count == 1


def test_match_candidate_does_not_save_on_parse_failed_error(
    test_engine: object,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """structured_chat が常に ParseFailedError を送出するときスコアが保存されない。"""
    _patch_session_local(monkeypatch, test_engine)

    def always_fail(*args: object, **kwargs: object) -> None:
        raise ParseFailedError(attempts=3)

    monkeypatch.setattr(matching_module, "structured_chat", always_fail)

    job = _make_job(db_session)
    candidate = _make_candidate(db_session, job_id=job.id)

    matching_module.match_candidate(candidate.id)

    db_session.expire_all()
    count = db_session.scalar(select(func.count()).select_from(Score))
    assert count == 0


def test_match_candidate_does_not_save_on_llm_unavailable_error(
    test_engine: object,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLMUnavailableError 発生時にスコアが保存されない。"""
    _patch_session_local(monkeypatch, test_engine)

    def unavailable(*args: object, **kwargs: object) -> None:
        raise LLMUnavailableError()

    monkeypatch.setattr(matching_module, "structured_chat", unavailable)

    job = _make_job(db_session)
    candidate = _make_candidate(db_session, job_id=job.id)

    matching_module.match_candidate(candidate.id)

    db_session.expire_all()
    count = db_session.scalar(select(func.count()).select_from(Score))
    assert count == 0


def test_match_candidate_does_not_leak_exception(
    test_engine: object,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLMUnavailableError・ParseFailedError が発生しても match_candidate は例外を伝播させない。"""
    _patch_session_local(monkeypatch, test_engine)

    def always_raise(*args: object, **kwargs: object) -> None:
        raise LLMUnavailableError()

    monkeypatch.setattr(matching_module, "structured_chat", always_raise)

    job = _make_job(db_session)
    candidate = _make_candidate(db_session, job_id=job.id)

    # 例外を送出しないこと（正常終了する）。
    matching_module.match_candidate(candidate.id)


def test_match_candidate_noop_if_candidate_not_found(
    test_engine: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """存在しない candidate_id を渡したとき何もせず正常終了する。"""
    _patch_session_local(monkeypatch, test_engine)

    # structured_chat は呼ばれないはずなので fail で安全網。
    def should_not_be_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("structured_chat が呼ばれてはいけません")

    monkeypatch.setattr(matching_module, "structured_chat", should_not_be_called)

    matching_module.match_candidate(99999)
