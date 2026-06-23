---
id: "0002"
title: "開発フローテンプレートの不足要素補完方針"
status: wip
created: 2026-03-21
updated: 2026-03-21
decision_owner: ""
---

# 開発フローテンプレートの不足要素補完方針

## コンテキスト

[research/0002](../research/0002-template-gap-analysis.md) のギャップ分析により、開発フローに対して現行テンプレートに6つの不足要素が特定された。

1. リリースチェックリストが存在しない
2. レビュー指針の蓄積場所がない
3. フィードバックループの具体的な設定ガイドがない
4. ロードマップ / フェーズ定義ドキュメントがない
5. research_type のガイダンスがない
6. ウォーターフォール×アジャイルのハイブリッド運用が未記述

これらをテンプレートにどう組み込むかの方針を決定する必要がある。

## 検討した選択肢

### 選択肢 A: steering + guides に分散配置

- 常時参照が必要なもの → `steering/` （ロードマップ）
- 手順・ルール → `guides/` （チェックリスト、設定ガイド等）
- レビュー専用指針 → `REVIEW.md`（リポジトリルート）
- 利点: 既存のディレクトリ構成の思想に沿う。AIがスコープに応じて参照先を切り替えられる
- 欠点: ファイル数が増える

### 選択肢 B: guides に一括配置

- 全ての新規ドキュメントを `guides/` に配置
- 利点: シンプル。探す場所が1箇所
- 欠点: steeringの「常時参照」とguidesの「必要時参照」の区別が曖昧になる。ロードマップは開発判断の基準であり、常時参照すべき

### 選択肢 C: 新ディレクトリ（例: `docs/process/`）を新設

- 利点: 開発プロセス関連を独立管理
- 欠点: 既存構造の変更が大きい。steering/guidesとの責務境界が不明確になる

## 決定

**選択肢 A: steering + guides に分散配置** を採用する。

具体的な配置：

| 不足要素 | 配置先 | 理由 |
|---|---|---|
| ロードマップ / フェーズ定義 | `steering/roadmap.md` | 開発判断の基準として常時参照が必要 |
| フィードバックループ設定 | `guides/feedback-loop-setup.md` | 構築手順であり、必要時に参照 |
| レビュー指針 | `guides/review-guidelines.md` + `REVIEW.md` | 運用ルールはguides、AI用指針はREVIEW.md |
| リリースチェックリスト | `guides/release-checklist.md` | リリース時に参照する手順 |
| research_type ガイダンス | `guides/research-type-guide.md` | research作成時に参照するガイド |
| ハイブリッド開発モデル | `guides/workflows.md` に追記 | 既存の開発フロー記述を拡張 |

### 開発モデル

Water-Scrum-Fallを採用する。

- 上流（要求整理〜設計）: ウォーターフォール的にドキュメントで固める
- 中流（実装〜レビュー）: spec単位のイテレーション
- 下流（リリース）: チェックリストに沿って段階的に実施

### フィードバックループ

Claude Code Hooksを「最初の砦」、CIを「最後の砦」とする二重構造を採用する。

### レビュー指針

CLAUDE.md（全般） + REVIEW.md（レビュー専用）の2ファイル構成。指摘パターンはチェックリスト形式で蓄積する。

### 優先度付け

MoSCoWを標準フレームワークとする。specテンプレートの既存MUST/SHOULD/COULD区分をフェーズ割り当てのルールとして活用する。

## 影響

- CLAUDE.md の更新が必要（roadmap.mdの参照追加、guides一覧の更新）
- workflows.md に開発モデルの記述追加が必要
- 新規ファイル5つ + REVIEW.md の追加
- validate-docs.sh への影響はなし（新規ファイルはguides/steeringのためfrontmatter検証対象外）

## 参考

- [research/0002: 開発フローテンプレート不足要素の調査・分析](../research/0002-template-gap-analysis.md)
- [Claude Code Hooks 公式ガイド](https://code.claude.com/docs/ja/hooks-guide)
- [Claude Code コードレビュー 公式ドキュメント](https://code.claude.com/docs/ja/code-review)
