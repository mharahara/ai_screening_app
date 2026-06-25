# issues/

初期バージョン完成後の変更は、ここに **issue** を作ってから着手する。issue を起点に、サブエージェントが「実装 → 検証 → レビュー往復 → 受け入れ確認」まで一貫対応する。

## 使い方

1. issue を作る。おすすめは `/create-issue <概要>` — 実態調査＋対話で仕様を詰め、受け入れ条件まで具体化したうえで `issues/NNN-<短いスラッグ>.md` を生成する（承認後に書き出す）。手で作るなら [TEMPLATE.md](TEMPLATE.md) をコピーして `issues/NNN-<短いスラッグ>.md` を作る（番号は連番。例: `001-candidate-skill-filter.md`）。
2. 背景・要件・対象レイヤー・受け入れ条件・受け入れシナリオを埋める。曖昧さを残さない（`/create-issue` ならこの工程を対話で行う）。
3. Claude Code に `/work-issue NNN`（または `/work-issue 001-candidate-skill-filter`）と指示する。
   - メインの Claude がオーケストレーターとなり、issue を読んで実装エージェントに委譲し、検証・レビュー往復・受け入れ確認まで回す。

## 命名規則

- ファイル名: `NNN-<英小文字ケバブのスラッグ>.md`（`001-candidate-skill-filter.md` など）
- `TEMPLATE.md` と `README.md` は issue ではない（番号を付けない）。

## ステータス運用

各 issue の `## ステータス` 欄を `open` → `in-progress` → `done` と更新する。完了済み issue もアーカイブせず残す（変更履歴として参照する）。
