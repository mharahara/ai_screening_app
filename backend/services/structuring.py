"""構造化サービス層（求人・応募書類）。

生テキストを LLM で構造化し `*ParseResult` を返す。Ollama 呼び出し・検証・
リトライは services/llm.py の汎用 `structured_chat` に委譲し、ここはタスク固有の
プロンプト構築と呼び出しだけを担う。
"""

from enum import StrEnum

from schemas import (
    CandidateParseResult,
    EmploymentType,
    JobParseResult,
    PositionLevel,
    RemoteWork,
)
from services.llm import structured_chat


# gemma 系の小型モデルは JSON Schema の `description` だけではフィールドの意味を
# 取りこぼし、title/description/skills などが軒並み空で返ることがある。そのため
# system プロンプト側で抽出フィールドを明示的に列挙して指示する。enum 候補値は
# スキーマ（schemas.py）と一致させるため StrEnum から動的に組み立てる。
def _enum_values(enum_cls: type[StrEnum]) -> str:
    return "[" + ", ".join(f'"{e.value}"' for e in enum_cls) + "]"


_JOB_SYSTEM_PROMPT = f"""あなたは採用情報の構造化アシスタントです。\
求人票の生テキストから情報を抽出し、JSON で出力してください。

# 抽出するフィールド
- title: 求人タイトル・募集職種（原文の「募集職種」等をそのまま）
- description: 業務内容の要約。原文の「業務内容」「ポジション概要」セクションをまとめる
- required_skills: 必須スキル・技術の配列。「必須要件」「Must」の文脈、および技術スタックとして
  列挙された技術から抽出する。要素は技術名・言語名・ツール名・フレームワーク名などの短いタグにする
  （例: ["Java", "Go", "TypeScript", "AWS", "MySQL"]）
- preferred_skills: 歓迎スキル・経験の配列。「歓迎要件」「Want」の文脈から抽出する。
  技術名・ツール名は required_skills と同じく短いタグに分割する
  （例: 「Docker / Kubernetes」→ ["Docker", "Kubernetes"]）。
  「〜の移行経験」のように技術名で表せない経験要件のみ簡潔なフレーズ1件1要素にする
  （例: ["マイクロサービス移行経験", "スクラムマスター経験"]）。資格・学位の要件はここに入れず
  certifications に入れる
- ideal_profile: 求める人物像の要約。「求める人物像」セクションをまとめる
- employment_type: 雇用形態。{_enum_values(EmploymentType)} のいずれか。言及がなければ null
- location: 勤務地。言及がなければ null
- remote_work: リモート可否。{_enum_values(RemoteWork)} のいずれか。\
言及はあるが曖昧なら "不明"、言及自体がなければ null
- rate_min / rate_max: 単価の下限/上限（万円/月の整数）。言及がなければ null
- min_experience_years: 最低経験年数（年の整数）。「5年前後」「3年以上」等の数値から
  最も低い必須年数を採る。言及がなければ null
- position_level: ポジションレベル。{_enum_values(PositionLevel)} のいずれか。
  「テックリード候補」はリード、明示がなければ役割記述から判断
- industry_experience: 求める業界経験。言及がなければ null
- certifications: 資格・学位要件の配列（資格名や学位のみ。プログラミング言語やツールなどの
  技術スタックは含めない）。「修士・博士号」のように複数候補が並ぶ場合も要素を冗長に展開せず
  簡潔にまとめる（例: 「データサイエンス、または情報理工学系の修士・博士号」→
  ["データサイエンスまたは情報理工学系の修士・博士号"]）。記載がなければ []

# ルール
1. 原文に明示された情報のみを抽出する。推測・補完・創作をしない。
2. 技術スタックセクションに列挙された技術は、歓迎要件として明示されていなければ
   required_skills に入れる。
3. required_skills・preferred_skills とも、技術名・ツール名は短いタグにし1要素1つに分割する
   （例: 「Python/Django」→ ["Python", "Django"]、「Go (Gin / Go-chi)」→ ["Go", "Gin", "Go-chi"]）。
   「〇〇の開発経験」のような文章から技術名を取り出せる場合はタグにする（含まれる技術名だけを取り出す）。
   表記は原文の語をそのまま使い、勝手な言い換えをしない。
4. 単価は万円/月の整数に正規化する（「時給」「年収」表記は概算換算してよいが、不明確なら null）。
5. 該当情報がないフィールドは null、配列フィールドは [] にする。
6. 出力は日本語。指定された JSON 以外のキー・説明文・前後テキストを出力しない。"""


def _build_job_user_prompt(raw_text: str) -> str:
    """求人構造化用の user プロンプトを組み立てる。"""
    return f"以下の求人票を構造化してください。\n<求人票>\n{raw_text}\n</求人票>"


def structure_job(raw_text: str) -> JobParseResult:
    """求人票の生テキストを構造化して `JobParseResult` を返す。"""
    return structured_chat(
        system=_JOB_SYSTEM_PROMPT,
        user=_build_job_user_prompt(raw_text),
        schema=JobParseResult,
    )


_CANDIDATE_SYSTEM_PROMPT = """あなたは採用情報の構造化アシスタントです。\
応募書類（職務経歴書・履歴書・スキルシート等）の生テキストから情報を抽出し、\
JSON で出力してください。

# 抽出するフィールド
- name: 応募者の氏名。記載がなければ null
- age: 年齢（歳の整数）。生年月日のみの場合は記載されている年齢を採り、不明確なら null
- nearest_station: 最寄り駅。記載がなければ null
- desired_rate: 希望単価（万円/月の整数）。「希望単価」「希望報酬」等の文脈から抽出する。
  時給・年収表記は概算換算してよいが、不明確なら null
- experience_years: エンジニアとしての経験年数（年の整数）。「実務〇年」「経験〇年」等の
  数値から採る。「3年半」等は四捨五入。記載がなければ null
- skills: 保有スキル・技術の配列。技術名・言語名・ツール名・フレームワーク名などの
  短いタグにする（例: ["Java", "Go", "TypeScript", "AWS", "MySQL"]）。
  「Python/Django」→ ["Python", "Django"]、「Go (Gin / Go-chi)」→ ["Go", "Gin", "Go-chi"]
  のように1要素1つに分割する。表記は原文の語をそのまま使い、勝手な言い換えをしない
- certifications: 保有資格・学位の配列（資格名や学位のみ。プログラミング言語やツールなどの
  技術スキルは含めない。それらは skills に入れる）。記載がなければ []
- work_history: 職歴・職務経歴の要約。所属・期間・担当業務など「これまで何をしてきたか」を
  まとめる。自己アピール文（self_pr）とは区別する
- education: 学歴（最終学歴・卒業校・学部等）。記載がなければ null
- self_pr: 自己PR・アピール内容。「自己PR」「アピールポイント」「得意分野」等、本人が
  強みや志向を語っている記述をまとめる。事実ベースの職歴（work_history）とは区別する

# ルール
1. 原文に明示された情報のみを抽出する。推測・補完・創作をしない。
2. skills は技術名・ツール名の短いタグにし、1要素1つに分割する。
   「〇〇の開発経験」のような文章からは技術名だけを取り出す。
3. certifications は資格・学位のみを入れる（技術スタックは skills へ）。
4. 単価は万円/月の整数に正規化する（「時給」「年収」表記は概算換算してよいが、不明確なら null）。
5. 経験年数・年齢は年/歳の整数にする（「3年半」等は四捨五入）。
6. 該当情報がないフィールドは null、配列フィールドは [] にする。
7. 出力は日本語。指定された JSON 以外のキー・説明文・前後テキストを出力しない。"""


def _build_candidate_user_prompt(raw_text: str) -> str:
    """応募書類構造化用の user プロンプトを組み立てる。"""
    return f"以下の応募書類を構造化してください。\n<応募書類>\n{raw_text}\n</応募書類>"


def structure_candidate(raw_text: str) -> CandidateParseResult:
    """応募書類の生テキストを構造化して `CandidateParseResult` を返す。"""
    return structured_chat(
        system=_CANDIDATE_SYSTEM_PROMPT,
        user=_build_candidate_user_prompt(raw_text),
        schema=CandidateParseResult,
    )
