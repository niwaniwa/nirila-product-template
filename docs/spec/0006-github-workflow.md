---
id: "0006"
title: "GitHub運用ワークフロー: Issue/PR/Projects/CI/branch protection と supervisor連携"
status: accepted
phase: mvp
created: 2026-06-24
updated: 2026-06-24
related_adr: ["0007", "0004"]
---

# GitHub運用ワークフロー: Issue/PR/Projects/CI/branch protection と supervisor連携

## 概要

[ADR 0007](../adr/0007-github-operations-model.md) が定めた「GitHubをIssue/PR駆動のAI Agent実行層とする（ローカルsandbox連携・継続フロー+velocity観測）」方針を、**運用ルールと実体ファイルの仕様**に落とす。対象は GitHub Issue / Pull Request / Projects / labels / GitHub Actions(CI) / branch protection、および supervisor と `gh` CLI の連携契約。

## 背景・ADR参照

- [ADR 0007: GitHub運用モデル](../adr/0007-github-operations-model.md)（本specの直接の根拠）
- [ADR 0004: サブエージェントは外側 supervisor 経由で兄弟コンテナ起動する](../adr/0004-subagent-execution-pattern.md)（GitHub連携は本ADRのガードレールを踏襲）

ADR 0007 の決定（接続点 = spec受け入れ基準→Issue、Agent = ローカルsandbox主軸、計画 = 継続フロー+velocity観測、branch = trunk-based）を変更しない。本specは「どう実体化するか」のみを定義する。

## 要件

### 機能要件

#### Issue / 実行単位

- **MUST**:
  - Issueテンプレート（`.github/ISSUE_TEMPLATE/`）に最低2種を用意する: `task`（実装タスク）, `bug`（バグ）。
  - `task` テンプレは [まとめ資料](../../gitlab_github_agile_scrum_xp_ai_agent_summary.md)のIssue例に準拠し、次を含む: 目的 / 受け入れ条件（チェックボックス）/ 実装方針 / テスト方針 / **触ってよい範囲・触ってはいけない範囲** / 対応spec へのリンク欄（`spec: docs/spec/NNNN-*.md`）。
  - Issue は1つあたり「小さい単位（1PRで閉じられる粒度）」を原則とする旨をテンプレに明記。
- **SHOULD**:
  - AI Agent に割り当てる Issue は受け入れ条件が機械検証可能（テストで判定できる）であることをテンプレで促す。
  - Epic は親Issue + Sub-issues（task list）で表現する。

#### ラベル体系

- **MUST**: 次のラベル群を定義する（`.github/labels.yml` 等で管理）:
  - 種別: `type:feature` `type:bug` `type:refactor` `type:docs` `type:chore`
  - 優先度: `priority:P0` `priority:P1` `priority:P2` `priority:P3`
  - 実行主体: `agent:local`（supervisor経由で隔離agentが着手可）, `human`（人間判断が必要）
  - 状態補助: `blocked` `needs-spec`（accepted spec が未整備）
- **SHOULD**: AI Agentに向く/向かない判定の補助として `agent:local` 付与基準を運用ガイドに記す（[まとめ資料](../../gitlab_github_agile_scrum_xp_ai_agent_summary.md)の向き/不向きリストを基準にする）。

#### GitHub Projects（継続フロー + velocity観測）

- **MUST**:
  - Board view を `Backlog / In Progress / Review / Done` の `Status`（Single select）で構成する。
  - 観測専用 field を持つ: `Points`（Number、GitLab Weight相当）, `Iteration`（Iteration field、週区切り）, `Priority`（Single select）, `Area`（Single select）。
  - In Progress に **WIP制限**（目安: 個人開発で同時2-3）を運用ルールとして明記する（GitHubはWIP制限を自動強制しないため運用で守る）。
- **SHOULD**:
  - `Points` と `Iteration` は **velocity観測専用** であり、締切固定・コミットメント強制に使わない旨を Project の説明と運用ガイドに明記する。
- **COULD**: 完了Issueの `Points` 合計を Iteration ごとに集計し、振り返り（[development-loop-playbook.md](../guides/development-loop-playbook.md)）の入力にする。

#### Pull Request

- **MUST**:
  - PRテンプレート（`.github/pull_request_template.md`）に次を含む: 対応Issue（`Closes #NNN`）/ 変更概要 / 受け入れ基準の達成状況（チェックボックス）/ テスト追加の有無 / 影響範囲。
  - 1PR = 1Issue = 小さい差分を原則とする旨を明記。
- **SHOULD**: PRがspecの受け入れ基準のどれを満たすかを参照できるようにする。

#### CI（GitHub Actions）

- **MUST**:
  - PR（`main` 向け）と `main` push をトリガに、`test / lint / typecheck / build` の各ジョブを実行する workflow（`.github/workflows/ci.yml`）を定義する。
  - これらを branch protection の **required status checks** に設定する。
  - 言語非依存のテンプレートであるため、各ジョブは「プロジェクトのスクリプト（例: `npm run lint` / 同等）に委譲」する構造とし、未設定時はスキップではなく**設定を促すplaceholder**にする。
- **SHOULD**:
  - `bash scripts/validate-docs.sh`（ドキュメントfrontmatter検証）をCIジョブに含める。
- **COULD**: 言語別の例（TypeScript / Rails）をコメントで併記（まとめ資料の例に準拠）。

#### branch protection / レビュー

- **MUST**:
  - `main` へ: 直push禁止・force-push禁止、PR必須、required checks（CI）通過必須、最低1レビュー承認必須。
  - trunk-based: 短命feature branch（命名例 `feat/`, `fix/`, `docs/`）から `main` へ小さいPR。
- **SHOULD**:
  - CODEOWNERS は共同所有（XP）の観点で広めに設定し、特定ファイルのみ厳格化する。
- **COULD**: マージ方式を squash merge に統一し履歴を小さく保つ。

#### supervisor ⇄ GitHub 連携契約

- **MUST**:
  - GitHub への書き込みは **supervisor のみ**が `gh` CLI 経由で行う。親/子 agent コンテナに GitHub write トークンを渡さない（ADR 0004/0007）。
  - supervisor が代行する操作はテンプレ固定: ①指定 Issue の取得（read）②指定 workspace での実装結果の push ③`gh pr create`（対象branch・Issueリンク固定）。
  - 親agentから supervisor へ渡せる入力は `issue_number` / `workspace_path` / `prompt` / `task_id` に限定。任意の `gh` 引数を渡せない。
  - GitHub token は最小権限（fine-grained PAT または GitHub App）とし、許可スコープ（対象リポジトリの contents:write / issues:read / pull_requests:write 程度）を文書化する。
- **SHOULD**:
  - supervisor は Issue→PR の連携を監査ログ（ADR 0004 の AUDIT_LOG）に残す。
- **COULD**: PR作成後にCI結果を supervisor がポーリングし、失敗時に修正タスクを再起票する。

### 非機能要件

- **パフォーマンス**: CI（test/lint/typecheck/build）はテンプレ標準構成でPRあたり目安10分以内に完了する設計とする。
- **セキュリティ**:
  - GitHub token は agent コンテナの env / ファイルに出さない。supervisor プロセスの環境にのみ存在させる。
  - workflow は `permissions:` を最小（既定 read、必要ジョブのみ write）に絞る。
  - fork からのPRで secrets を露出させない（`pull_request_target` を安易に使わない）。

## スコープ

### このフェーズで対応するもの

- 上記 MUST/SHOULD の **仕様定義**（運用ルール + 各実体ファイルが満たすべき要件）。
- GitLab対応マップ（ADR 0007）の運用ルールへの落とし込み。
- supervisor ⇄ gh CLI 連携の入出力契約の定義。

### 対応しないもの（後続フェーズ）

- `.github/` 実体ファイル（Issueテンプレ / PRテンプレ / labels.yml / ci.yml / CODEOWNERS）の**作成**そのもの（本spec accepted 後の実装イテレーション）。
- supervisor の gh 連携コードの実装（ADR 0004 の amend または後続spec）。
- GitHub-native agent（Copilot coding agent / `@claude` Action）への拡張（必要時に別ADR、ADR 0007 軸1-C）。
- 固定スプリント運用・velocity自動集計・自動velocityレポート生成。
- supervisor による CI結果ポーリング→自動再起票（CI失敗は人間検知→agent修正の手動運用）。
- リリース自動化（Releases / changelog 自動生成）は [release-checklist.md](../guides/release-checklist.md) と別途整合。

## 技術設計

### doc駆動 ⇄ GitHub駆動の接続フロー

```text
docs/spec/NNNN (accepted)
   │  受け入れ基準を分解
   ▼
GitHub Issue (task テンプレ, spec逆リンク, agent:local ラベル)
   │  supervisor が gh で取得
   ▼
隔離 agent コンテナ (ADR 0003) が実装 + 受け入れテスト先行(TDD)
   │  supervisor が git push + gh pr create
   ▼
Pull Request (Closes #NNN)
   │
   ▼
CI: test / lint / typecheck / build / validate-docs  ← required checks
   │  green
   ▼
人間レビュー (設計・ビジネス判断, 最低1承認)
   │
   ▼
squash merge → main (常に green)
   │  必要なら
   ▼
Milestone / Release (タグ)
```

### `.github/` に用意するファイル（要件のみ。実体作成は後続）

```text
.github/
├── ISSUE_TEMPLATE/
│   ├── task.md         # 目的/受け入れ条件/範囲/テスト/spec逆リンク
│   └── bug.md
├── pull_request_template.md
├── labels.yml          # type:* / priority:* / agent:local / human / blocked
├── workflows/
│   └── ci.yml          # test / lint / typecheck / build / validate-docs
└── CODEOWNERS          # 共同所有（広め）
```

### supervisor ⇄ gh 連携の入出力契約

| 親agentが渡す | supervisorが実行（テンプレ固定） | 禁止 |
|---|---|---|
| `issue_number` | `gh issue view <n>`（read） | 任意 `gh` 引数 |
| `workspace_path` | 当該workspaceで実装結果を `git push` | 任意branchへのpush |
| `prompt` / `task_id` | `gh pr create`（base=main, head=固定branch, body=Issueリンク） | token の agentコンテナへの受け渡し |

トークンは supervisor プロセス環境にのみ存在。状態遷移と監査は ADR 0004 の `SPAWN_REQUEST` / `AUDIT_LOG` モデルを再利用する。

### GitLab対応マップ（運用ルール）

| GitLab | 本プロジェクト | 備考 |
|---|---|---|
| Weight | Projects `Points` | 観測専用 |
| Iteration/Sprint | Projects `Iteration` | 週区切り・観測専用 |
| Issue Board | Projects Board (`Status`) | Backlog/In Progress/Review/Done |
| Epic | 親Issue + Sub-issues | task list |
| Milestone/Release | Milestone + Releases | タグ運用 |
| Issue完了条件 | spec 受け入れ基準 | 機械検証可能を推奨 |

## 受け入れ基準

- [ ] Issueテンプレ要件（task/bug、taskは目的/受け入れ条件/範囲/テスト/spec逆リンクを含む）が定義されている
- [ ] ラベル体系（type:* / priority:* / agent:local / human / blocked / needs-spec）が列挙されている
- [ ] Projects の Board構成（Status 4列）と観測専用 field（Points/Iteration/Priority/Area）、WIP制限の運用ルールが定義されている
- [ ] 「Points/Iteration は velocity観測専用、コミットメント強制に使わない」原則が明記されている
- [ ] PRテンプレ要件（Closes #NNN / 受け入れ基準達成状況 / テスト有無）が定義されている
- [ ] CI workflow 要件（test/lint/typecheck/build + validate-docs、required checks化、最小 permissions）が定義されている
- [ ] branch protection 要件（main直push/force-push禁止、PR必須、CI必須、1承認必須、trunk-based）が定義されている
- [ ] supervisor ⇄ gh 連携契約（書き込みは supervisor のみ、親agentへトークンを渡さない、入力は issue_number/workspace_path/prompt/task_id に限定）が定義されている
- [ ] doc駆動（spec受け入れ基準）→ Issue → PR → CI → review → merge の接続フローが図示されている
- [ ] GitLab対応マップが運用ルールとして定義されている
- [ ] `bash scripts/validate-docs.sh` がエラー 0 で通る

## 決定済みの方針（旧・未解決事項）

- **GitHub token**: MVPは **単一リポジトリの fine-grained PAT** を採用する。**切替トリガー**: 2つ目のリポジトリへ展開する／組織運用に移す時点で **GitHub App** へ移行する（短命 installation token の自動ローテーション・独立した bot identity・組織スケールが必要になるため）。移行時は本specを改訂、または別ADRで判断する。
- **CI 言語別ジョブ**: 本フェーズでは具体化しない。`ci.yml` はプロジェクトのスクリプトに委譲する placeholder + 例コメントに留める（言語非依存テンプレートのため）。
- **velocity 自動集計**: 本フェーズ対象外。`Points` 合計の自動集計は行わず、必要になれば後続で判断する。
- **CI結果ポーリング→自動再起票**: 本フェーズ対象外。CI失敗は人間が検知してagentに修正させる手動フィードバックで運用する。supervisor による自動化は仕組み安定後の後続COULD。

## 未解決事項

