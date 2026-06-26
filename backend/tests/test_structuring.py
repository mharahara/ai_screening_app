"""services/structuring.py の構造化呼び出しの通り道テスト。

structure_candidate が汎用 `structured_chat` を、期待した system/user プロンプト・
schema=CandidateParseResult で呼び、戻りをそのまま返すことを検証する。
`structured_chat` 自体はモックし、LLM・応答内容の質は検証しない（structured_chat
側のリトライ/例外伝播は test_llm.py が担う）。
"""

import pytest

import services.structuring as structuring_module
from schemas import CandidateParseResult


class _RecordingStructuredChat:
    """`structured_chat` を置き換え、呼び出し kwargs を記録して固定値を返す。"""

    def __init__(self, return_value: object) -> None:
        self._return_value = return_value
        self.calls: list[dict[str, object]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self._return_value


def test_structure_candidate_calls_structured_chat_with_expected_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """期待した system/user/schema で structured_chat を呼び、戻りをそのまま返す。"""
    expected = CandidateParseResult(name="山田太郎", skills=["Python"])
    fake = _RecordingStructuredChat(expected)
    monkeypatch.setattr(structuring_module, "structured_chat", fake)

    raw = "氏名: 山田太郎。Python の実務経験あり。"
    result = structuring_module.structure_candidate(raw)

    # 戻りはモックが返した CandidateParseResult をそのまま返す（マッピングの通り道）。
    assert result is expected

    # 1 回だけキーワード引数で呼ばれる。
    assert len(fake.calls) == 1
    kwargs = fake.calls[0]

    # schema は CandidateParseResult。
    assert kwargs["schema"] is CandidateParseResult

    # system プロンプトには応募書類向けの抽出フィールド名が含まれる。
    system = kwargs["system"]
    assert isinstance(system, str)
    for field in ("name", "skills", "work_history", "self_pr", "education"):
        assert field in system

    # user プロンプトには raw_text とデリミタ（タグ）が含まれる。
    user = kwargs["user"]
    assert isinstance(user, str)
    assert raw in user
    assert "<応募書類>" in user
    assert "</応募書類>" in user
