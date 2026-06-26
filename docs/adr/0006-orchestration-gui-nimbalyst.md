---
id: "0006"
title: "オーケストレーション GUI は Nimbalyst を一次推奨とする"
status: accepted
created: 2026-06-21
updated: 2026-06-22
decision_owner: "プロジェクトリーダー"
---

# オーケストレーション GUI は Nimbalyst を一次推奨とする

## コンテキスト

[ADR 0003](./0003-agent-execution-docker-isolation.md) で agent をコンテナに閉じ込め、[ADR 0004](./0004-subagent-execution-pattern.md) で「外側 supervisor が兄弟コンテナを起動」する方式を採用した。この **外側 supervisor の役割を、人間が直接触る UI レイヤとして担えるツール** を選定する必要がある。

[research/0004](../research/0004-agent-observability-gui-tools.md) で比較した通り、現状の選択肢は：

- **Nimbalyst**（旧 Crystal）：Electron、mac/Win/Linux、Claude Code / Codex の並列 worktree 管理、OSS
- **Conductor**（Melty Labs）：macOS app、parallel worktree + checkpoint + multi-model 比較
- **Claudia / opcode**（getAsterisk）：Tauri 2 + React + Rust、**OS レベル sandbox（seccomp / Seatbelt）を内蔵**、完全ローカル
- **Shipyard**：Web SaaS、ローカル要件と矛盾

要件：

- 複数 worktree / セッションの並列起動と差分閲覧
- ADR 0003 / 0004 の Docker 隔離経路と組み合わせ可能（起動コマンドの差し替え）
- 個人開発者の現実的なホスト環境（少なくとも Linux と macOS）で動作

## 検討した選択肢

### 選択肢 A: Nimbalyst（旧 Crystal の後継）

- 利点:
  - mac / Windows / Linux で動く（テンプレートの汎用性が高い）
  - Claude Code と Codex の両方をネイティブサポート
  - parallel worktree モデルが ADR 0004 のサブエージェント実行方式（bare repo + clone）と整合
  - OSS でフォーク / カスタマイズ可能
- 欠点:
  - 起動コマンドを `docker compose run agent` に差し替えるカスタマイズが必要
  - Crystal からのリブランド直後で安定度はまだ要観察

### 選択肢 B: Conductor（Melty Labs）

- 利点:
  - parallel worktree + checkpoint + multi-model 比較が完成度高い
  - Y Combinator 出身チームでメンテ継続性は良好
- 欠点:
  - **macOS 限定** で、Linux / Windows ユーザを抱えるチームでは採用できない
  - Docker 経由起動の差し替え可否が明確でない

### 選択肢 C: Claudia / opcode（getAsterisk）

- 利点:
  - **OS レベル sandbox を内蔵**（Linux seccomp / macOS Seatbelt）
  - mac / Linux / Windows 対応、完全ローカル、外部送信なし
  - checkpoint タイムライン、コスト分析、custom agent 機能が同梱
- 欠点:
  - **Docker 隔離（ADR 0003）と二重サンドボックス**になる：seccomp + コンテナ + cap drop が重なり、デバッグと運用が複雑化
  - ADR 0004 の「supervisor が docker compose run を代行」モデルに合わせるための改造コストが大きい

### 選択肢 D: GUI を採用しない（terminal + ホスト側 script のみ）

- 利点: 依存ゼロ、テンプレートが軽い
- 欠点: 複数 worktree の比較・差分閲覧 UI を独自に作る負担が大きい

## 決定

**選択肢 A: Nimbalyst を一次推奨** とする。テンプレートとしては「推奨」のみで、強制はしない（GUI を使わない運用 = 選択肢 D も許容する）。

**選択肢 C: Claudia / opcode** は **「Docker 隔離を採らず、Claudia の OS sandbox で済ませる軽量ローカルモード」用のオプション** として README に明記する。**Docker 隔離（ADR 0003）と Claudia の OS sandbox を同時に使うことは推奨しない**（二重隔離のオーバヘッドと運用複雑性に見合わない）。

**選択肢 B: Conductor** は macOS 専用チームでの代替案として README に補足する。

### Nimbalyst と ADR 0003/0004 の橋渡し

- Nimbalyst の "agent 起動コマンド" を `docker compose -f tools/agent-sandbox/compose.yml run --rm -v <worktree>:/workspace agent ...` に差し替える。
- 各 worktree が ADR 0004 の bare repo + clone モデルにマップされる。
- 起動コマンド差し替えの手順は `tools/agent-sandbox/README.md` および本テンプレートの guides に記載する。

### 採用条件（将来のレビュー基準）

以下が満たされなくなった場合、本 ADR を再検討する：

- Nimbalyst のメンテナンスが停止
- ADR 0003 の Docker 経路への差し替えが不可能になる upstream 変更
- 並列 worktree モデルが Anthropic 標準のサブエージェント実装と乖離する変更

## 影響

- 正：個人開発者・チームが「複数 agent の並列実行」を視覚的に管理でき、ADR 0004 の supervisor 役を UI で担える。
- 正：選択肢を残すことで、コンテナ隔離が過剰な場合は Claudia、macOS チームは Conductor へ流せる。
- 負：Nimbalyst の起動コマンド差し替え手順をテンプレ側で文書化・保守する必要がある。
- 負：複数 GUI を併記するため、README で選択基準を明示しないと初学者を混乱させる。
- リスク：Nimbalyst が breaking change を入れた場合、起動コマンド差し替え手順が壊れる。テンプレート CI で smoke test を持つのが望ましい。

## 参考

- [research/0004: Claude Code / Agent SDK プロジェクト向け 可視化 GUI・ローカル Observability ツール調査](../research/0004-agent-observability-gui-tools.md)
- [ADR 0003: エージェント実行は Docker Compose で隔離する](./0003-agent-execution-docker-isolation.md)
- [ADR 0004: サブエージェント起動方式](./0004-subagent-execution-pattern.md)
- [ADR 0005: Observability 既定スタック](./0005-observability-stack-langfuse.md)
- [Nimbalyst (旧 Crystal)](https://github.com/stravu/crystal)
- [Conductor (Melty Labs)](https://madewithlove.com/blog/conductor-running-multiple-ai-coding-agents-in-parallel/)
- [Claudia / opcode](https://github.com/getAsterisk/claudia)
