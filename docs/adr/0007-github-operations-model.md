---
id: "0007"
title: "GitHubをIssue/PR駆動のAI Agent実行層とする（ローカルsandbox連携・継続フロー+velocity観測）"
status: accepted
created: 2026-06-24
updated: 2026-06-24
decision_owner: "プロジェクトリーダー"
---

# GitHubをIssue/PR駆動のAI Agent実行層とする（ローカルsandbox連携・継続フロー+velocity観測）

## コンテキスト

本リポジトリには既に以下が決定・実装済みである。

- **ドキュメント駆動フロー**: `research → ADR → spec → 実装`（[docs/README.md](../README.md)）
- **開発モデル**: Water-Scrum-Fall（上流WF / 実装イテレーション / リリースWF、[roadmap.md](../steering/roadmap.md)）
- **ローカル隔離エージェント基盤**: Docker隔離（[ADR 0003](./0003-agent-execution-docker-isolation.md)）/ 外側supervisor 経由のサブエージェント起動（[ADR 0004](./0004-subagent-execution-pattern.md)）/ observability（[ADR 0005](./0005-observability-stack-langfuse.md)）/ GUI（[ADR 0006](./0006-orchestration-gui-nimbalyst.md)）

一方で、まとめ資料が整理した潮流——「上流はScrum/Kanban、実装はXP、実行単位はIssue/PR、品質保証はCIとレビュー」——のうち、**GitHubを使った運用層が未設計**である。具体的には次が空白になっている。

| 層 | 既存 | 空白 |
|---|---|---|
| 計画(Scrum/Kanban) | spec の MoSCoW | GitHub Projects の field 設計 |
| 実行単位(Issue/PR) | — | Issueテンプレ・ラベル・PR運用・branch戦略 |
| 品質(CI/レビュー) | Hooks/CI方針（[feedback-loop-setup.md](../guides/feedback-loop-setup.md)） | GitHub Actions実体・branch protection |
| Agent⇄GitHub接続 | ローカルsandbox + supervisor | supervisorとGitHub(gh CLI)の繋ぎ |

この空白を埋める運用モデルを決定する。前提として、**[ADR 0003/0004](./0004-subagent-execution-pattern.md) の隔離設計（親agentがホスト権限・認証情報を直接持たない）を崩さない**ことを必須条件とする。

## 検討した選択肢

設計の本筋を分ける軸は3つある。軸ごとに選択肢を比較する。

### 軸1: AI Agent の実行形態

#### 選択肢 1-A: ローカルsandbox主軸 + GitHub連携

- ローカルの隔離エージェント（ADR 0003-0006）が実行主体。supervisor が `gh` CLI で Issue を取得→隔離コンテナで実装→`git push`→`gh pr create` を**仲介**する。GitHub は Issue/PR/CI の「場」に徹する。
- 利点: 既存の隔離設計・supervisor 資産をそのまま使える。親agentに GitHub write 権限を渡さず、supervisor 境界（ADR 0004 のテンプレ強制・入力検証）に閉じ込められる。
- 欠点: supervisor に gh 連携の実装責務が増える。

#### 選択肢 1-B: GitHub-native agent主軸

- GitHub Copilot coding agent / `@claude` GitHub Action に Issue を assign し、クラウド側でPRを作らせる。
- 利点: 構築が手軽。GitHub UI から完結。
- 欠点: 既存の隔離基盤（egress proxy / cap_drop / 監査ログ）と**別系統**になり、ADR 0003-0006 の投資が活きない。実行環境のガードレールがGitHub側の仕様に依存する。

#### 選択肢 1-C: 両対応（ハイブリッド）

- ラベルで振り分け（cloud は @claude、local は supervisor）。
- 利点: 柔軟。
- 欠点: 2系統の運用・監査・権限モデルを維持するコスト。テンプレート初期値としては複雑。

### 軸2: 計画のリズム

#### 選択肢 2-A: Iteration固定スプリント

- 1-2週固定スプリント + velocity でコミットメント管理。最もGitLab/Scrumらしい。
- 利点: 予実管理が締まる。
- 欠点: 計画イベントのオーバーヘッド。まとめ資料が指摘する通り「XPにスプリントは必須でない」。小規模・AI Agent運用では過剰になりやすい。

#### 選択肢 2-B: 継続フロー（Kanban + WIP制限）

- 固定スプリントなし。小さいIssue→小さいPRを連続で流す。常にmainをgreenに保つXP寄り。
- 利点: AI Agent/XPと相性が良い。計画オーバーヘッドが最小。
- 欠点: 進捗の「速度感」が数値で見えにくい。

#### 選択肢 2-C: 継続フロー + velocity観測

- 基本は継続フロー（2-B）。ただし Projects に `Points`（GitLab Weight相当）と `Iteration`（週区切り）field を持たせ、**velocity を「観測専用メトリクス」**として可視化する。計画コミットメントには使わない（締切固定の道具にしない）。
- 利点: XPの軽さを保ちつつ、プロジェクトごとの「どれくらい進んでいるか」を後追いで見られる。GitLabのWeight/Iterationの良さを観測目的に限定して取り込む。
- 欠点: field運用のルールを「観測専用」と明文化しないと、なし崩しに固定スプリント化するリスク。

### 軸3: ブランチ戦略

#### 選択肢 3-A: GitHub Flow / trunk-based

- 短命feature branch + 小さいPR + 常にmain green。
- 利点: XP「継続的統合」「小さなリリース」と一致。AI AgentのPRを早くmainへ近づけられる。
- 欠点: リリース列を分けたい場合に工夫が要る（タグ/Releaseで対応）。

#### 選択肢 3-B: GitFlow（develop/release/hotfix）

- 利点: 大規模・複数バージョン並行に強い。
- 欠点: 個人〜小規模 + AI Agent + 継続フローには重い。長命ブランチがCIのgreen維持を難しくする。

## 決定

**軸1: 1-A（ローカルsandbox主軸 + GitHub連携）、軸2: 2-C（継続フロー + velocity観測）、軸3: 3-A（trunk-based / GitHub Flow）** を採用する。

### 1. ドキュメント駆動とGitHub駆動の接続点

`accepted な spec の受け入れ基準` を **GitHub Issue に分解**する（spec 1つ → Issue 1〜N）。

- **spec = 契約**（何を満たすべきか）、**Issue = 実行単位**（誰が/いつ着手するか）。
- Issue は本文に `spec: docs/spec/NNNN-*.md` への逆リンクと、対応する受け入れ基準（チェックボックス）を持つ。
- GitLabで言う「Issueの完了条件」= spec の受け入れ基準、という対応で運用する。これにより doc駆動の `wip→accepted` ライフサイクルと、GitHub の Issue/PR 実行が**二重管理にならず一方向に繋がる**。

### 2. Agent実行形態（隔離を崩さない GitHub 連携）

- supervisor（ADR 0004）が GitHub との唯一の接点となり、`gh` CLI 操作を**テンプレ固定**で代行する：Issue取得 → 隔離コンテナで実装 → `git push` → `gh pr create`。
- 親/子 agent コンテナには **GitHub の write トークンを直接渡さない**。トークンは supervisor 境界内に置き、許可された操作（指定Issueの読取・指定branchへのpush・PR作成）だけをスキーマで許す（ADR 0004 のガードレール 1〜6 を踏襲）。
- 親agentが渡せるのは `issue number` / `workspace path` / `prompt` / `task id` 程度に限定する。

### 3. 計画リズム（継続フロー + velocity観測）

- 固定スプリントは**設けない**。WIP制限付きの継続フローを基本とする。
- GitHub Projects に観測用 field（`Points`, `Iteration`）を持たせるが、**velocity は振り返り用の観測メトリクス**であり、計画コミットメントや締切固定の道具にはしない。この「観測専用」原則を spec とガイドに明記する。

### 4. ブランチ戦略・品質ゲート

- trunk-based / GitHub Flow。短命branch + 小さいPR。
- branch protection で `main` への直push・force-push禁止（[tech.md](../steering/tech.md) の既存制約と整合）、PRレビュー必須、CI required checks 必須。
- CI（GitHub Actions）は PRごとに `test / lint / typecheck / build` を回す（まとめ資料「最低限回すもの」に準拠）。受け入れ基準に対応するテストを TDD で先行させ、CIでgateする。
- レビューは三層：**Hooks（ローカル・即時）= 最初の砦 / CI（リモート・網羅）= 最後の砦 / 人間 = 設計・ビジネス判断**（[workflows.md](../guides/workflows.md) の二重構造を人間レビュー込みで拡張）。CODEOWNERS は共同所有（XP）の観点で**厳しくしすぎない**。

### 5. GitLabっぽさの再現マップ

| GitLab | 本プロジェクトでの対応 |
|---|---|
| Weight | Projects `Points`（Number field、観測専用） |
| Iteration / Sprint | Projects `Iteration` field（週区切り・観測専用） |
| Issue Board | Projects Board view（Backlog / In Progress / Review / Done） |
| Epic | 親Issue + Sub-issues |
| Milestone / Release | GitHub Milestone + Releases（タグ） |
| Issueの完了条件 | spec の受け入れ基準（チェックボックス） |

### 禁止事項

- 親/子 agent コンテナへ GitHub write トークンを直接渡すこと（supervisor 境界を越えさせない）。
- `main` への直push / force-push（既存 tech.md と整合）。
- CI required checks 未通過PRのmerge。
- 観測用 `Points` / `Iteration` を締切固定・コミットメント強制の道具に転用すること。

## 影響

- **正**: 既存のローカル隔離基盤（ADR 0003-0006）を一切作り直さずに GitHub 運用層を載せられる。doc駆動（spec受け入れ基準）と GitHub 実行（Issue/PR/CI）が一方向に繋がり、二重管理を避けられる。XPの軽さ（継続フロー）とGitLab的な可視化（velocity観測）を両立できる。
- **正**: 隔離設計を崩さないため、prompt injection で親agentが乗っ取られても GitHub への影響は supervisor のスキーマ内に閉じる。
- **負**: supervisor に `gh` CLI 連携の実装責務が増える（ADR 0004 の拡張が必要）。
- **負**: GitHub-native agent（Copilot等）の手軽さは初期値として享受しない。将来必要になれば軸1-Cへ拡張する別ADRを起こす。
- **リスク**: GitHub token のスコープ設計に穴があると supervisor 経由で想定外の操作が可能になりうる。spec で最小権限トークン（fine-grained PAT / GitHub App）の範囲を厳密に定義する。
- **リスク**: 「velocity観測専用」原則が形骸化し固定スプリント運用に流れる恐れ。ガイドで運用ルールを明記する。

### 後続作業

- [spec 0006](../spec/0006-github-workflow.md): Issue/PR/Projects/labels/CI/branch protection/supervisor連携 の具体仕様（本ADRの実装契約）。
- `.github/`（Issueテンプレ・PRテンプレ・labels・workflows・CODEOWNERS）の実体は spec 0006 受け入れ後の後続イテレーションで作成。
- supervisor の gh 連携拡張は ADR 0004 の amend または後続 spec で扱う。

## 参考

- [ADR 0003: エージェント実行は Docker Compose で隔離する](./0003-agent-execution-docker-isolation.md)
- [ADR 0004: サブエージェントは外側 supervisor 経由で兄弟コンテナ起動する](./0004-subagent-execution-pattern.md)
- [ADR 0006: オーケストレーション GUI（Nimbalyst）](./0006-orchestration-gui-nimbalyst.md)
- [steering/roadmap.md: Water-Scrum-Fall 開発モデル](../steering/roadmap.md)
- [guides/workflows.md: 開発ワークフロー](../guides/workflows.md)
