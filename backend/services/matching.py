"""マッチングサービス層。

候補者 × 求人のマッチングスコアを LLM で算出し、scores テーブルに保存する。
LLM 呼び出し・検証・リトライは services/llm.py の `structured_chat` に委譲し、
ここはプロンプト構築・スコア算出ロジック・保存を担う。

バックグラウンドから呼ばれる `match_candidate` は全例外をキャッチしてログ出力し、
例外を伝播させない。
"""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from config import settings
from db import SessionLocal
from models import Candidate, Job, Score
from schemas import MatchResult, RequirementStatus
from services.llm import ParseFailedError, structured_chat

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# マッチング用プロンプト
# ---------------------------------------------------------------------------

_MATCHING_SYSTEM_PROMPT = """あなたは採用マッチングアシスタントです。\
構造化済みの求人要件と候補者データを照合し、各軸を評価して JSON で出力してください。

# 評価軸（それぞれ 0〜100 で評価）
- skill_score: スキルマッチ度。求人の必須スキル・歓迎スキルと候補者のスキルを照合する。\
必須スキルを大半満たす=高得点、ほぼ満たさない=低得点
- experience_score: 経験年数マッチ度。求人の最低経験年数と候補者の経験年数を比較する。\
求人要件を超えるほど高得点
- industry_score: 業界経験マッチ度。求人が求める業界経験と候補者の職歴・業界経験を照合する。\
業界経験の言及がなければ中間点（50）を基準にする
- position_score: ポジションレベルマッチ度。求人のポジションレベルと候補者の職歴・役割から\
判断したレベル感を照合する。ポジション情報がなければ中間点（50）を基準にする

# 必須要件チェック（requirement_checks）
- 求人の required_skills 全件（漏れなく）を1件ずつ判定する
- 件数は required_skills の件数と完全一致させる
- status は「充足」か「未充足」のどちらかを設定する
- evidence は候補者データ中の該当箇所を簡潔に示す（日本語）

# サマリー（日本語の文章）
- strengths: 候補者の強み（求人との相性を踏まえた固有の内容）
- concerns: 候補者の懸念点（求人との相性を踏まえた固有の内容）
- interview_points: 面接で確認すべき事項

# ルール
1. 各スコアは 0〜100 の整数で出力する
2. 判断は渡された構造化データのみに基づく（創作・推測をしない）
3. 総合スコア・必須充足率は出力しない（コード側で算出する）
4. 指定 JSON Schema 以外のキー・前後テキストを出力しない
5. 強み・懸念点・確認事項は日本語の文章とし、汎用的な決まり文句を避ける"""


def _build_matching_user_prompt(job: Job, candidate: Candidate) -> str:
    """マッチング評価用の user プロンプトを組み立てる。"""
    job_data = {
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills,
        "preferred_skills": job.preferred_skills,
        "ideal_profile": job.ideal_profile,
        "rate_min": job.rate_min,
        "rate_max": job.rate_max,
        "min_experience_years": job.min_experience_years,
        "position_level": job.position_level,
        "industry_experience": job.industry_experience,
        "certifications": job.certifications,
    }
    candidate_data = {
        "name": candidate.name,
        "age": candidate.age,
        "experience_years": candidate.experience_years,
        "skills": candidate.skills,
        "certifications": candidate.certifications,
        "work_history": candidate.work_history,
        "education": candidate.education,
        "self_pr": candidate.self_pr,
        "desired_rate": candidate.desired_rate,
        "nearest_station": candidate.nearest_station,
    }
    job_json = json.dumps(job_data, ensure_ascii=False, indent=2)
    candidate_json = json.dumps(candidate_data, ensure_ascii=False, indent=2)
    return (
        "以下の求人要件と候補者データを照合し、マッチング評価を行ってください。\n"
        f"<求人要件>\n{job_json}\n</求人要件>\n"
        f"<候補者データ>\n{candidate_json}\n</候補者データ>"
    )


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


def evaluate_match(job: Job, candidate: Candidate) -> MatchResult:
    """マッチング用 system/user プロンプトを構築し structured_chat を呼ぶ。

    Pydantic バリデーション失敗（スコア範囲・型不正）は structured_chat が内部で
    リトライする。requirement_checks の件数が len(job.required_skills) と不一致の
    場合は外側のループでフィードバック付き再試行を行う。
    上限超過時は ParseFailedError を送出する。

    Raises:
        ParseFailedError: 検証失敗またはカウント不一致が上限を超えた場合。
        LLMTimeoutError: タイムアウトが上限を超えた場合。
        LLMUnavailableError: LLM に接続できない場合。
    """
    max_attempts = max(1, settings.parse_max_retries)
    user = _build_matching_user_prompt(job, candidate)
    expected_count = len(job.required_skills)

    system = _MATCHING_SYSTEM_PROMPT
    if job.matching_instructions and job.matching_instructions.strip():
        system += f"\n\n# カスタム評価指示\n{job.matching_instructions.strip()}"

    for attempt in range(1, max_attempts + 1):
        # structured_chat は Pydantic バリデーション（スコア範囲・型不正）のみ担当し、
        # 内部でリトライする。失敗例外はそのまま伝播させる。
        result = structured_chat(
            system=system,
            user=user,
            schema=MatchResult,
        )

        actual_count = len(result.requirement_checks)
        if actual_count == expected_count:
            return result

        logger.warning(
            "requirement_checks 件数不一致（試行 %d/%d）: 期待 %d 件、実際 %d 件",
            attempt,
            max_attempts,
            expected_count,
            actual_count,
        )

        if attempt < max_attempts:
            feedback = (
                f"requirement_checks の件数が正しくありません。"
                f"求人の required_skills は {expected_count} 件あるため、"
                f"requirement_checks も {expected_count} 件（各スキルに1件ずつ）必要です。"
                f"現在 {actual_count} 件です。すべての必須スキルを漏れなく列挙してください。"
            )
            user = f"{_build_matching_user_prompt(job, candidate)}\n\n{feedback}"

    raise ParseFailedError(
        attempts=max_attempts,
        message=(
            f"requirement_checks の件数が一致しませんでした"
            f"（期待 {expected_count} 件、{max_attempts} 回試行）。"
        ),
    )


def compute_total_score(result: MatchResult, weights: dict[str, float]) -> int:
    """4軸スコアを重み付け平均して総合スコア（0〜100）を返す。

    重みは合計 1.0 に正規化して扱う。重みが全て 0 なら 0 を返す。
    引数 weights のキーは "skill" / "experience" / "industry" / "position"。
    """
    total_weight = sum(weights.values())
    if total_weight == 0.0:
        return 0

    weighted_sum = (
        result.skill_score * weights.get("skill", 0.0)
        + result.experience_score * weights.get("experience", 0.0)
        + result.industry_score * weights.get("industry", 0.0)
        + result.position_score * weights.get("position", 0.0)
    )
    raw = weighted_sum / total_weight
    return max(0, min(100, round(raw)))


def match_candidate(candidate_id: int) -> None:
    """候補者のマッチングスコアを算出して scores テーブルに保存する。

    BackgroundTasks から呼ばれる。SessionLocal を内部で生成してセッション管理する。
    全例外をキャッチしてログ出力し、例外を伝播させない。

    処理手順:
    1. candidate と紐づく job を取得（存在しなければ何もせず正常終了）
    2. evaluate_match で MatchResult を取得
    3. compute_total_score で総合スコアを算出
    4. required_met / required_total を算出
    5. candidate_id 単位で scores を upsert
    """
    db = SessionLocal()
    try:
        candidate = db.get(Candidate, candidate_id)
        if candidate is None:
            logger.info(
                "match_candidate: candidate_id=%d が存在しません。スキップします。",
                candidate_id,
            )
            return

        job = db.get(Job, candidate.job_id)
        if job is None:
            logger.warning(
                "match_candidate: candidate_id=%d に紐づく job_id=%d が存在しません。",
                candidate_id,
                candidate.job_id,
            )
            return

        result = evaluate_match(job, candidate)

        weights: dict[str, float] = {
            "skill": settings.match_weight_skill,
            "experience": settings.match_weight_experience,
            "industry": settings.match_weight_industry,
            "position": settings.match_weight_position,
        }
        total = compute_total_score(result, weights)

        required_met = sum(
            1 for check in result.requirement_checks if check.status == RequirementStatus.MET
        )
        required_total = len(result.requirement_checks)

        # candidate_id で既存 Score を検索し、あれば更新、なければ新規作成（upsert）。
        existing = db.scalar(select(Score).where(Score.candidate_id == candidate_id))
        if existing is None:
            existing = Score(candidate_id=candidate_id)
            db.add(existing)

        existing.total_score = total
        existing.skill_score = result.skill_score
        existing.experience_score = result.experience_score
        existing.industry_score = result.industry_score
        existing.position_score = result.position_score
        existing.required_met = required_met
        existing.required_total = required_total
        existing.requirement_checks = [c.model_dump() for c in result.requirement_checks]
        existing.strengths = result.strengths
        existing.concerns = result.concerns
        existing.interview_points = result.interview_points
        existing.scored_at = datetime.now(tz=UTC)

        db.commit()
        logger.info(
            "match_candidate: candidate_id=%d のスコア算出完了（total=%d）。",
            candidate_id,
            total,
        )

    except Exception:
        logger.exception(
            "match_candidate: candidate_id=%d のスコア算出中に例外が発生しました。",
            candidate_id,
        )
    finally:
        db.close()
