"""ビジネスロジック層（Ollama 連携・構造化・スコアリング）。

- llm.py: Ollama 接続と汎用 `structured_chat`（検証・リトライ・例外）
- structuring.py: 求人・応募書類の構造化（`structure_job` ほか）
- matching.py: マッチング評価・スコア算出（後続 issue で追加）
"""
