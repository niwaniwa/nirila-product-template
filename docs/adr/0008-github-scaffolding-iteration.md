---
id: "0008"
title: "GitHub運用の実装イテレーション分割と .github scaffolding 方針"
status: accepted
created: 2026-06-24
updated: 2026-06-24
decision_owner: "プロジェクトリーダー"
---

# GitHub運用の実装イテレーション分割と .github scaffolding 方針

## コンテキスト

[ADR 0007](./0007-github-operations-model.md) / [spec 0006](../spec/0006-github-workflow.md)（ともに accepted）で GitHub運用層の方針と要件が確定した。spec 0006 の実体ファイルは未整備（現状 `.github/` は `workflows/doc-lint.yml` のみ）であり、これから実装に入る。

実装に入るにあたり2点を決める必要がある。

1. **実装の分割と着手の扱い**: spec 0006 のスコープには「`.github/` scaffolding（A）」と「supervisor の gh連携（B）」が含まれる。これらをどう分割し、どの順で、どのゲートを通して実装するか。
2. **`.github/` scaffolding の実装方針**: 言語非依存テンプレートとして、CI・labels・CODEOWNERS 等をどう実体化するか。

加えて本セッションで、**「accepted spec があるから」とエージェントが手順（着手の人間ゲート）を独断でスキップする**事象が起きた。doc駆動フローと[human-in-the-loop](../guides/human-in-the-loop.md)の人間ゲートが散文の規約でしか定義されておらず、機械的強制がない構造的な穴が露呈した。この再発防止も本ADRの射程に含める。

## 検討した選択肢

### 実装の分割（軸1）

#### 選択肢 1-A: A と B を一括実装

- 利点: まとめて GitHub運用が立ち上がる。
- 欠点: B は ADR 0004 の supervisor 境界に gh操作を足す**意図的な境界変更**を伴い、token設計・policy拡張が必要。A（境界変更なし）と混ぜると安全レビューが粗くなる。

#### 選択肢 1-B: A を先、B は別イテレーション（各々ゲートを通す）

- A（`.github/` scaffolding、境界変更なし）→ 人間ゲート → B（supervisor gh連携、ADR 0004 amend 必須）の順。
- 利点: 境界変更を伴うBを独立レビューできる。Aだけで人間主導の Issue/PR/CI ループが立ち上がる。
- 欠点: 立ち上げが2段階になる。

### `.github/` scaffolding の作り込み度（軸2）

#### 選択肢 2-A: 言語別CIまで作り込む

- 利点: すぐ実プロジェクトで動く。
- 欠点: 本リポジトリは**言語非依存テンプレート**。特定言語を埋め込むと再利用性を損なう。

#### 選択肢 2-B: 言語非依存 scaffolding に留める

- Issue/PRテンプレ・labels・CODEOWNERS と、CIは「プロジェクトのスクリプトに委譲する placeholder + 例コメント」。
- 利点: テンプレートの再利用性を保つ。spec 0006 の方針（placeholder + 例コメント）と一致。
- 欠点: 各プロジェクトで CI スクリプトを埋める一手間が残る。

### 着手ゲートの強制（軸3）

#### 選択肢 3-A: 散文の規約のまま（現状維持）

- 欠点: 本セッションで破綻が実証済み。エージェントの善意依存。

#### 選択肢 3-B: hook + CLAUDE.md で機械的に強制

- PreToolUse hook で「実装ファイルへの Write/Edit 着手」を検知し、着手ゲート（accepted spec の確認・人間の明示承認）をリマインドする。CLAUDE.md に「方向選択（AskUserQuestion）≠ 着手承認」を明文化。
- 利点: feedback-loop の「最初の砦」を実体化。再発を物理的に抑止する方向に倒せる。
- 欠点: 通常実装時にもリマインドが出る（許容範囲）。

## 決定

- **軸1: 1-B（A を先、B は別イテレーション）** を採用。A は本ADR accepted 後に実装、B は ADR 0004 amend を伴う別イテレーションとする。
- **軸2: 2-B（言語非依存 scaffolding）** を採用。具体方針:
  - Issueテンプレ: markdown テンプレ形式（`task.md` / `bug.md` / `config.yml`）。※本セッションで先行作成済み。
  - PRテンプレ: `Closes #NNN` / 変更概要 / 受け入れ基準達成 / テスト有無 / 影響範囲。
  - labels: `labels.yml`（label-sync系Actionで同期できるリスト形式）。`type:*` / `priority:P0-3` / `agent:local` / `human` / `blocked` / `needs-spec`。
  - CI: `ci.yml` に `test / lint / typecheck / build` + `validate-docs`。各ジョブは `scripts/ci/<name>.sh` があれば実行、無ければ「未設定」通知を出して成功扱い（bootstrap時に required check を赤にしない）。TS/Rails例はコメント併記。`permissions` は最小（`contents: read`）。
  - CODEOWNERS: 共同所有で広め。機密パス（`tools/agent-sandbox/supervisor/`, `.github/`）のみ厳格化。オーナー名は未確認のためプレースホルダ + 編集要を明記。
  - required checks 化・branch protection は GitHub UI/`gh` 設定（ファイル化不可）。`ci.yml` にセットアップ手順をコメント記載。
- **軸3: 3-B（hook + CLAUDE.md で強制）** を採用。着手ゲートを機械化する。

### 着手ゲートの定義（明文化対象）

- 「実装ファイルの作成・編集の着手」前に、(1) 対応する accepted な spec/ADR の存在、(2) 人間の**明示的な着手承認**、を確認する。
- **AskUserQuestion での方向選択は着手承認ではない**。方向選択は「次に何を設計/起票するか」を決めるだけ。
- docs（research/ADR/spec/guides）と plan ファイルの作成は、設計ゲート内の作業として着手承認の対象外。

## 影響

- 正: A だけで人間主導の Issue/PR/CI ループが立ち上がる。B の境界変更を独立レビューできる。テンプレートの言語非依存性を保てる。
- 正: 着手ゲートが機械的リマインドになり、手順スキップの再発を抑止できる（[feedback-loop-setup.md](../guides/feedback-loop-setup.md) の「最初の砦」を実体化）。
- 負: CI に各プロジェクトで `scripts/ci/*.sh` を埋める手間が残る。立ち上げが2イテレーションに分かれる。
- リスク: hook が過剰だと通常作業を阻害する。まずはリマインド（非ブロック）で運用し、不足ならブロックへ escalate する。

### 後続作業（本ADR accepted 後）

- A 実装: `pull_request_template.md` / `labels.yml` / `ci.yml` / `CODEOWNERS`（Issueテンプレ3点は作成済み）。
- 着手ゲート hook + CLAUDE.md ルールの追加（本セッションで実装、本ADRはその記録）。
- B（supervisor gh連携）は ADR 0004 amend + 後続 spec で別途。

## 参考

- [ADR 0007: GitHub運用モデル](./0007-github-operations-model.md)
- [spec 0006: GitHub運用ワークフロー](../spec/0006-github-workflow.md)
- [ADR 0004: サブエージェント supervisor](./0004-subagent-execution-pattern.md)（B の前提）
- [guides/human-in-the-loop.md](../guides/human-in-the-loop.md)（人間ゲートの定義）
- [guides/feedback-loop-setup.md](../guides/feedback-loop-setup.md)（Hooks=最初の砦）
