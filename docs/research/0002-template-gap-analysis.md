---
id: "0002"
title: "開発フローテンプレート不足要素の調査・分析"
status: wip
created: 2026-03-21
updated: 2026-03-21
research_type: gap-analysis
---

# 開発フローテンプレート不足要素の調査・分析

## 目的

AI支援ドキュメント駆動開発フローにおいて、現行テンプレートに不足している6つの要素を調査し、各要素の業界ベストプラクティス・実践例を整理する。

## 調査方法

- Web検索による最新の実践例・テンプレート収集（2025〜2026年の情報を中心）
- Claude Code公式ドキュメントの精査
- OSSプロジェクト・企業事例の分析
- 計20以上のソースから情報を収集・クロスバリデーション

---

## 調査結果

### 1. リリースチェックリスト

#### 業界標準の構造

リリースチェックリストは一般的に **3フェーズ構成** が標準（<a href="https://pflb.us/blog/successful-software-release-inclusive-checklist/" target="_blank">PFLB</a>、<a href="https://www.apwide.com/the-essential-release-checklist/" target="_blank">Apwide</a>）：

**Pre-release（リリース前）:**
- コードレビュー完了確認
- 全テスト（ユニット・結合・E2E）通過
- セキュリティ検査（脆弱性スキャン、認証確認）
- ドキュメント更新確認（spec/ADRとの整合性）
- パフォーマンステスト
- UI/UX検査（デザイントークンとの一致）

**Deployment（デプロイ）:**
- インフラ・DB構成の検証
- 環境変数・secrets設定確認
- デプロイ手順の確認
- ロールバック計画の準備

**Post-release（リリース後）:**
- 動作確認（スモークテスト）
- モニタリング確認
- リリースノート公開
- フィードバック収集開始
- 次の要求整理への反映

#### 運用上の知見

リリースチェックリストは「生きたドキュメント」として運用し、毎リリース後に振り返りで改善すべきとされる（<a href="https://launchdarkly.com/blog/release-management-checklist/" target="_blank">LaunchDarkly</a>）。

---

### 2. レビュー指針の蓄積

#### Claude Code のレビュー機能

Claude Codeは2026年3月にCode Review機能をリサーチプレビューとして追加（<a href="https://code.claude.com/docs/ja/code-review" target="_blank">公式ドキュメント</a>）。以下の2ファイルでレビューをカスタマイズ可能：

- **`CLAUDE.md`**: 全タスク共通の指示。レビュー時も参照される
- **`REVIEW.md`**: レビュー専用ガイダンス。コードレビュー中にのみ読み取られる

#### REVIEW.mdの推奨構造

公式ドキュメントの例（<a href="https://code.claude.com/docs/ja/code-review" target="_blank">Claude Code Review Docs</a>）：

```markdown
# Code Review Guidelines

## Always check
- New API endpoints have corresponding integration tests
- Database migrations are backward-compatible
- Error messages don't leak internal details to users

## Style
- Prefer `match` statements over chained `isinstance` checks
- Use structured logging, not f-string interpolation in log calls

## Skip
- Generated files under `src/gen/`
- Formatting-only changes in `*.lock` files
```

#### レビュー指針の蓄積パターン

**CyberAgentの実践例**（<a href="https://developers.cyberagent.co.jp/blog/archives/60882/" target="_blank">CyberAgent開発者ブログ</a>）：
- 共通ガイドラインと領域専用ガイドラインを分離
- `docs/guidelines/` に一元化し、AIエージェントが参照しやすい形で管理
- 「組織固有の実装パターン」に限定（標準知識はAIが保有済み）

**ガイドラインテンプレートの標準構造**（<a href="https://github.com/axolo-co/developer-resources/blob/main/code-review-guideline-template/code-review-guideline-template.md" target="_blank">Axolo</a>）：
1. Goals & Objectives（レビューの目的）
2. Roles & Responsibilities（役割定義）
3. Scope & Focus（レビュー範囲と優先領域）
4. Standards（品質基準）
5. Frequency & Timing（頻度とタイミング）
6. Culture（建設的フィードバックの文化）

**AIと人間の役割分担**：
- **AI**: 機械的品質チェック、ガイドライン違反検出、CIエラー対応
- **人間**: 設計判断、ビジネスロジック、マージ判定

#### 重要な知見

> チェックリストがないと、Claudeは1〜2点について長文のコメントを書き、他を無視する傾向がある（<a href="https://futuresearch.ai/blog/claude-review-skill/" target="_blank">FutureSearch</a>）

> フロンティアLLMは約150〜200の指示に合理的な一貫性で従える（<a href="https://code.claude.com/docs/en/best-practices" target="_blank">Claude Code Best Practices</a>）

---

### 3. フィードバックループの設定

#### Claude Code Hooks の概要

Hooksはライフサイクルの特定ポイントで実行されるシェルコマンド（<a href="https://code.claude.com/docs/ja/hooks-guide" target="_blank">公式ガイド</a>）。主要イベント：

| イベント | 発火タイミング | 主な用途 |
|---|---|---|
| `PreToolUse` | ツール実行前 | 危険な操作のブロック、バリデーション |
| `PostToolUse` | ツール実行後 | 自動フォーマット、自動テスト |
| `Stop` | Claude応答完了時 | タスク完了検証 |
| `Notification` | 入力待ち時 | デスクトップ通知 |
| `SessionStart` | セッション開始時 | コンテキスト注入 |

#### 具体的な設定例

**1. 自動フォーマット（PostToolUse）**

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [{
        "type": "command",
        "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write"
      }]
    }]
  }
}
```

**2. テスト自動実行（PostToolUse）**

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "jq -r '.tool_input.file_path' | grep -E '\\.(test|spec)\\.(js|ts)$' | xargs -r npm test -- --findRelatedTests"
      }]
    }]
  }
}
```

**3. 保護ファイルへの編集ブロック（PreToolUse）**

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "bash .claude/hooks/protect-files.sh"
      }]
    }]
  }
}
```

**4. タスク完了検証（Stop hook - エージェントベース）**

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "agent",
        "prompt": "Verify that all unit tests pass. Run the test suite and check the results. $ARGUMENTS",
        "timeout": 120
      }]
    }]
  }
}
```

#### フィードバックループの設計思想

> Hooksは「最初の砦」、CIは「最後の砦」という役割分担が開発生産性を大きく向上させる（<a href="https://syu-m-5151.hatenablog.com/entry/2025/07/14/105812" target="_blank">じゃあ、おうちで学べる</a>）

従来: 編集→コミット→プッシュ→CI失敗→修正（5-10分）
Hooks: 編集→即座に検出・修正（数秒）

3つの hook タイプ：
- `command`: シェルコマンド（決定論的ルール向け）
- `prompt`: シングルターンLLM評価（判断が必要な場合）
- `agent`: マルチターン検証（コードベースの実状態チェック）

---

### 4. ロードマップ / フェーズ定義

#### MVPロードマップの標準構造

6つのフェーズが一般的（<a href="https://wearepresta.com/the-complete-mvp-roadmap-guide-for-2026/" target="_blank">Presta 2026ガイド</a>、<a href="https://www.upsilonit.com/blog/how-to-make-an-mvp-roadmap" target="_blank">Upsilon</a>）：

1. **Discovery（発見）** — 問題検証、ユーザーリサーチ
2. **Feature Prioritization（優先度付け）** — 必須/後回しの分類
3. **User Journey Mapping（ユーザー体験設計）**
4. **Technical Planning（技術計画）**
5. **Launch Strategy（リリース戦略）**
6. **Continuous Iteration（継続改善）**

#### ロードマップの構成要素

- **Timeline**: 開発段階の時間軸表現
- **Goals & Objectives**: 各フェーズの目標
- **Features & Initiatives**: 優先度別の機能リスト
- **Milestones**: リリース・ベータテスト等の重要チェックポイント

#### 優先度付けフレームワーク

| フレームワーク | 概要 | 適用場面 |
|---|---|---|
| **MoSCoW** | Must/Should/Could/Won't | 機能分類の標準手法 |
| **Kano Model** | 基本品質/性能品質/魅力品質 | ユーザー満足度分析 |
| **RICE** | Reach×Impact×Confidence/Effort | 定量的優先度付け |

---

### 5. 調査タイプ（research_type）のガイダンス

#### ソフトウェア開発における調査の分類

8つの実現妥当性調査タイプが標準（<a href="https://www.geeksforgeeks.org/software-engineering/types-of-feasibility-study-in-software-project-development/" target="_blank">GeeksforGeeks</a>）：

| タイプ | 評価内容 |
|---|---|
| **Technical** | 技術的に実現可能か（スキル・ツール・インフラ） |
| **Economic** | コスト対効果（開発費・運用費 vs 収益） |
| **Operational** | 運用・保守が現実的か |
| **Schedule** | スケジュール内に完了可能か |
| **Market** | 市場ニーズ・競合状況 |
| **Legal** | 法規制・コンプライアンス |
| **Cultural/Political** | 組織文化・ステークホルダーの受容性 |
| **Resource** | 人材・技術・資金リソースの充足度 |

#### 開発フローに対応する調査タイプの例

ソフトウェア開発で一般的に見られる調査の分類：

| 調査タイプ | 対応フェーズ | 概要 |
|---|---|---|
| 競合分析 (competitive-analysis) | 要求整理 | 競合調査・市場分析 |
| 市場調査 (market-research) | 要求整理 | 市場ニーズ・ターゲット検証 |
| 技術評価 (tech-evaluation) | 仕様策定・設計 | 技術選定・比較 |
| 実現妥当性検討 (feasibility-study) | 要求整理・設計 | 実現妥当性の多面的検討 |
| ユーザー調査 (user-research) | 要求整理 | ユーザーインタビュー・行動分析 |
| PoC結果報告 (poc-report) | 設計・実装 | 技術検証の結果報告 |
| ギャップ分析 (gap-analysis) | 全フェーズ | 現状と目標のギャップ分析 |

---

### 6. ウォーターフォール×アジャイル ハイブリッドモデル

#### Water-Scrum-Fall モデル

Dave West（Forrester）が提唱したハイブリッドモデル。42%の組織がハイブリッド手法を採用（<a href="https://www.createq.com/en/software-engineering-hub/scrumfall-approach" target="_blank">Createq</a>）。

**3段階構造:**
1. **Water（上流）**: 要求整理・アーキテクチャ設計 → ウォーターフォール的に固める
2. **Scrum（中流）**: 実装・テスト → イテレーティブに開発
3. **Fall（下流）**: 統合・リリース → ウォーターフォール的に管理

#### 小規模・個人開発での知見

- フォーマルなスプリント計画は不要、機能単位のイテレーションで十分とされる
- 42%の組織がハイブリッド手法を採用しており、主流となりつつある

---

## 主な発見

1. **リリースチェックリスト**: 3フェーズ構成（Pre-release / Deployment / Post-release）が業界標準
2. **レビュー指針**: Claude CodeはCLAUDE.md（全般）+ REVIEW.md（レビュー専用）の2ファイル構成をサポート。チェックリスト形式が効果的
3. **フィードバックループ**: Claude Code Hooksで「最初の砦」を構築し、CIを「最後の砦」とする二重構造が推奨される
4. **ロードマップ**: MoSCoWが小規模開発で最も軽量。specのphaseフィールドとの連携が鍵
5. **調査分類**: 8タイプの妥当性調査が標準。TELOSフレームワーク（Technical/Economic/Legal/Operational/Schedule）が一般的
6. **ハイブリッドモデル**: Water-Scrum-Fallが最も普及。上流Waterfall + 中流Agile + 下流Waterfall

---

## 補足資料

### Sources

- <a href="https://code.claude.com/docs/ja/hooks-guide" target="_blank">Claude Code Hooks ガイド（公式）</a>
- <a href="https://code.claude.com/docs/ja/code-review" target="_blank">Claude Code コードレビュー（公式）</a>
- <a href="https://code.claude.com/docs/en/best-practices" target="_blank">Claude Code Best Practices（公式）</a>
- <a href="https://pflb.us/blog/successful-software-release-inclusive-checklist/" target="_blank">Checklist for a Successful Software Release - PFLB</a>
- <a href="https://launchdarkly.com/blog/release-management-checklist/" target="_blank">Release Management Checklist - LaunchDarkly</a>
- <a href="https://www.apwide.com/the-essential-release-checklist/" target="_blank">The Essential Release Checklist 2026 - Apwide</a>
- <a href="https://developers.cyberagent.co.jp/blog/archives/60882/" target="_blank">AI時代のコードレビューフロー再設計 - CyberAgent</a>
- <a href="https://techblog.lycorp.co.jp/ja/20260122a" target="_blank">Claude Code × MCPでPRレビュー自動化 - LINE Yahoo</a>
- <a href="https://syu-m-5151.hatenablog.com/entry/2025/07/14/105812" target="_blank">Claude Code Hooksは設定したほうがいい - じゃあ、おうちで学べる</a>
- <a href="https://github.com/axolo-co/developer-resources/blob/main/code-review-guideline-template/code-review-guideline-template.md" target="_blank">Code Review Guideline Template - Axolo</a>
- <a href="https://github.com/mgreiler/code-review-checklist" target="_blank">Code Review Checklist - mgreiler</a>
- <a href="https://www.geeksforgeeks.org/software-engineering/types-of-feasibility-study-in-software-project-development/" target="_blank">Types of Feasibility Study - GeeksforGeeks</a>
- <a href="https://asana.com/resources/feasibility-study" target="_blank">Feasibility Study Guide - Asana</a>
- <a href="https://wearepresta.com/the-complete-mvp-roadmap-guide-for-2026/" target="_blank">MVP Roadmap Guide 2026 - Presta</a>
- <a href="https://www.upsilonit.com/blog/how-to-make-an-mvp-roadmap" target="_blank">Planning an MVP Roadmap - Upsilon</a>
- <a href="https://www.createq.com/en/software-engineering-hub/scrumfall-approach" target="_blank">Scrumfall Approach - Createq</a>
- <a href="https://hybrid-technologies.co.jp/service/waterfall/" target="_blank">ハイブリッド開発手法 - Hybrid Technologies</a>
- <a href="https://claudefa.st/blog/guide/development/feedback-loops" target="_blank">Claude Code Feedback Loops - ClaudeFast</a>
- <a href="https://zenn.dev/a1yama/articles/claude-code-review-skill" target="_blank">Claude Codeの/code-reviewスキルで自動コードレビューを仕組み化する</a>
