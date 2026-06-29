"""Pydantic スキーマ（入出力・LLM 構造化結果）。

求人（Job）まわりの構造化結果スキーマ・enum・保存/出力スキーマを定義する。
構造化結果スキーマ（`JobParseResult`）は Ollama の `format` に
`model_json_schema()` で渡し、戻りを `model_validate_json()` で検証する用途。

enum の候補値・フィールド名・単位は docs/03_how/02_ai.md / 03_data-model.md の
定義に厳密に合わせる（フロント表示・DB 値との契約のため）。

候補者（Candidate）の構造化結果・保存/出力スキーマもここに定義する。
マッチング（Score）のスキーマもここに定義する。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EmploymentType(StrEnum):
    """雇用形態。不明時は null。"""

    FULL_TIME = "正社員"
    CONTRACT = "契約社員"
    OUTSOURCING = "業務委託"
    DISPATCH = "派遣"
    OTHER = "その他"


class RemoteWork(StrEnum):
    """リモート可否。曖昧だが言及はある場合 `不明`、言及なしは null。"""

    FULL_REMOTE = "フルリモート"
    PARTIAL_REMOTE = "一部リモート"
    ONSITE = "出社"
    UNKNOWN = "不明"


class PositionLevel(StrEnum):
    """ポジションレベル。原文の役割記述から正規化する。"""

    JUNIOR = "ジュニア"
    MIDDLE = "ミドル"
    SENIOR = "シニア"
    LEAD = "リード"
    MANAGER = "マネージャー"


class JobParseResult(BaseModel):
    """求人票の構造化結果（LLM 出力検証用）。

    各 Field の description は LLM への抽出指示としても機能する。
    配列フィールドは null ではなく空配列をデフォルトとする。
    原文（raw_text）はここに含めず、サーバ側で別途保持する。
    """

    title: str | None = Field(
        default=None,
        description="求人タイトル。該当情報がなければ null。",
    )
    description: str | None = Field(
        default=None,
        description="業務内容。該当情報がなければ null。",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description=(
            "必須スキルのタグ配列。1スキル1要素に分割する"
            '（例: 「Python/Django」→ ["Python", "Django"]）。'
            "記載がなければ空配列 []。"
        ),
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="歓迎スキルのタグ配列。必須スキルと区別する。記載がなければ空配列 []。",
    )
    ideal_profile: str | None = Field(
        default=None,
        description="求める人物像。該当情報がなければ null。",
    )
    employment_type: EmploymentType | None = Field(
        default=None,
        description="雇用形態。候補値のいずれかに正規化する。言及がなければ null。",
    )
    location: str | None = Field(
        default=None,
        description="勤務地。該当情報がなければ null。",
    )
    remote_work: RemoteWork | None = Field(
        default=None,
        description=(
            "リモート可否。候補値のいずれかに正規化する。"
            "言及はあるが曖昧な場合は『不明』、言及自体がなければ null。"
        ),
    )
    rate_min: int | None = Field(
        default=None,
        description="単価下限。単位は万円/月の整数。該当情報がなければ null。",
    )
    rate_max: int | None = Field(
        default=None,
        description="単価上限。単位は万円/月の整数。該当情報がなければ null。",
    )
    min_experience_years: int | None = Field(
        default=None,
        description="最低経験年数。単位は年の整数（端数は四捨五入）。該当情報がなければ null。",
    )
    position_level: PositionLevel | None = Field(
        default=None,
        description="ポジションレベル。候補値のいずれかに正規化する。該当情報がなければ null。",
    )
    industry_experience: str | None = Field(
        default=None,
        description="求める業界経験。該当情報がなければ null。",
    )
    certifications: list[str] = Field(
        default_factory=list,
        description="資格要件のタグ配列。1資格1要素。記載がなければ空配列 []。",
    )


class JobCreate(JobParseResult):
    """求人保存用スキーマ（構造化結果 + 原文）。"""

    raw_text: str = Field(description="求人票の原文。LLM には生成させず入力をそのまま保持する。")
    matching_instructions: str | None = Field(
        default=None,
        description="マッチング時に LLM へ追加指示するカスタム評価指針。null なら追加指示なし。",
    )


class JobOut(JobCreate):
    """求人出力用スキーマ（id + 全フィールド + 作成日時）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class CandidateParseResult(BaseModel):
    """応募書類の構造化結果（LLM 出力検証用）。

    各 Field の description は LLM への抽出指示としても機能する。
    配列フィールドは null ではなく空配列をデフォルトとする。
    原文（raw_text）はここに含めず、サーバ側で別途保持する。
    """

    name: str | None = Field(
        default=None,
        description="氏名。該当情報がなければ null。",
    )
    age: int | None = Field(
        default=None,
        description="年齢。単位は歳の整数。該当情報がなければ null。",
    )
    nearest_station: str | None = Field(
        default=None,
        description="最寄り駅。該当情報がなければ null。",
    )
    desired_rate: int | None = Field(
        default=None,
        description="希望単価。単位は万円/月の整数。該当情報がなければ null。",
    )
    experience_years: int | None = Field(
        default=None,
        description="経験年数。単位は年の整数（端数は四捨五入）。該当情報がなければ null。",
    )
    skills: list[str] = Field(
        default_factory=list,
        description=(
            "スキルのタグ配列。1スキル1要素に分割する"
            '（例: 「Python/Django」→ ["Python", "Django"]）。'
            "記載がなければ空配列 []。"
        ),
    )
    certifications: list[str] = Field(
        default_factory=list,
        description=(
            "資格・学位のタグ配列。1資格1要素。技術スキルは含めない。記載がなければ空配列 []。"
        ),
    )
    work_history: str | None = Field(
        default=None,
        description="職歴・職務経歴の要約。該当情報がなければ null。",
    )
    education: str | None = Field(
        default=None,
        description="学歴。該当情報がなければ null。",
    )
    self_pr: str | None = Field(
        default=None,
        description="自己PR・アピール内容。職歴と区別する。該当情報がなければ null。",
    )


class CandidateCreate(CandidateParseResult):
    """候補者保存用スキーマ（構造化結果 + 紐づく求人 + 原文）。"""

    job_id: int = Field(description="紐づく求人の id。")
    raw_text: str = Field(description="応募書類の原文。LLM には生成させず入力をそのまま保持する。")


class CandidateOut(CandidateCreate):
    """候補者出力用スキーマ（id + 全フィールド + 作成日時）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class JobSummary(BaseModel):
    """求人一覧（セレクター）用の軽量スキーマ。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# マッチング（Score）関連スキーマ
# ---------------------------------------------------------------------------


class RequirementStatus(StrEnum):
    """必須要件の充足状態。"""

    MET = "充足"
    NOT_MET = "未充足"


class RequirementCheck(BaseModel):
    """必須要件1件の充足判定（LLM 出力の一部）。"""

    requirement: str = Field(description="必須要件のラベル（求人の required_skills の各要素）。")
    status: RequirementStatus = Field(description="充足 / 未充足。")
    evidence: str | None = Field(
        default=None,
        description="充足/未充足と判断した根拠（候補者データ中の該当箇所）。該当なければ null。",
    )


class MatchResult(BaseModel):
    """マッチング評価の LLM 出力スキーマ。

    各軸スコア・必須要件チェック・サマリーを返す。
    総合スコア・必須充足率はコード側で算出するため LLM 出力には含めない。
    """

    skill_score: int = Field(ge=0, le=100, description="スキルスコア（0〜100）。")
    experience_score: int = Field(ge=0, le=100, description="経験年数スコア（0〜100）。")
    industry_score: int = Field(ge=0, le=100, description="業界経験スコア（0〜100）。")
    position_score: int = Field(ge=0, le=100, description="ポジションレベルスコア（0〜100）。")
    requirement_checks: list[RequirementCheck] = Field(
        default_factory=list,
        description=(
            "求人の必須スキル全件に対する充足判定。"
            "required_skills の各要素を1件ずつ判定し、漏れなく列挙する。"
        ),
    )
    strengths: str = Field(description="候補者の強み（日本語の文章）。")
    concerns: str = Field(description="候補者の懸念点（日本語の文章）。")
    interview_points: str = Field(description="面接での確認事項（日本語の文章）。")


class ScoreOut(BaseModel):
    """Score モデルの出力用スキーマ（全フィールド）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    total_score: int
    skill_score: int
    experience_score: int
    industry_score: int
    position_score: int
    required_met: int
    required_total: int
    requirement_checks: list[RequirementCheck]
    strengths: str
    concerns: str
    interview_points: str
    scored_at: datetime


class CandidateRankingItem(BaseModel):
    """ランキング一覧の1行（候補者 + スコアサマリー）。"""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: int
    name: str | None
    created_at: datetime
    total_score: int | None
    skill_score: int | None
    experience_score: int | None
    industry_score: int | None
    position_score: int | None
    required_met: int | None
    required_total: int | None


class CandidateDetailOut(CandidateOut):
    """候補者詳細出力用スキーマ（CandidateOut の全フィールド + スコア）。"""

    model_config = ConfigDict(from_attributes=True)

    score: ScoreOut | None = None
