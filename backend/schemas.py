"""Pydantic スキーマ（入出力・LLM 構造化結果）。

求人（Job）まわりの構造化結果スキーマ・enum・保存/出力スキーマを定義する。
構造化結果スキーマ（`JobParseResult`）は Ollama の `format` に
`model_json_schema()` で渡し、戻りを `model_validate_json()` で検証する用途。

enum の候補値・フィールド名・単位は docs/03_how/02_ai.md / 03_data-model.md の
定義に厳密に合わせる（フロント表示・DB 値との契約のため）。

候補者（Candidate）・マッチング（Score）のスキーマは後続 issue で追加する。
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


class JobOut(JobCreate):
    """求人出力用スキーマ（id + 全フィールド + 作成日時）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class JobSummary(BaseModel):
    """求人一覧（セレクター）用の軽量スキーマ。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime
