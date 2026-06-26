# docs/ ディレクトリ

プロジェクトのドキュメントをライフサイクル管理付きで運用するための構造。

## ディレクトリ構成

```text
docs/
├── steering/         # プロジェクト知識（常時参照・ライフサイクルなし）
├── guides/           # 開発ガイド・ルール（ライフサイクル対象外）
├── adr/              # ADR（意思決定記録）
├── spec/             # 仕様書
├── research/         # 調査・分析
└── design-tokens/    # デザイントークン定義（ライフサイクル対象外）
```

## Steering（常時参照ドキュメント）

`steering/` はAIが毎セッションで参照するプロジェクトの不変知識を格納する。
ライフサイクル管理（wip/accepted/archive）は持たず、frontmatterも不要。
プロジェクトの方針・構成が変わったタイミングで随時更新する。

| ファイル | 内容 |
| --- | --- |
| `steering/product.md` | プロダクト概要・コアバリュー・MVP定義 |
| `steering/tech.md` | 技術スタック・選定理由・禁止事項 |
| `steering/structure.md` | ディレクトリ構成・命名規則・依存ルール |

## ドキュメント種別の責務

| 種別 | 書くべきこと | 書くべきでないこと |
|---|---|---|
| **research** | 調査の目的・方法・結果・候補の提示 | 採否の決定、技術方針の確定 |
| **adr** | 判断の背景・選択肢の比較・決定とその理由 | 詳細な調査データ、実装レベルの仕様 |
| **spec** | 要件定義・技術設計・受け入れ基準 | 意思決定の経緯（ADRを参照） |

> **researchの「推奨」セクションについて:** 候補の提示と根拠の整理にとどめる。採否の最終判断はADRで行う。

## ドキュメント間のフロー

```text
research（調査・分析）
  ↓ 候補・判断材料を提供
adr（意思決定）
  ↓ 技術選定・方針決定
spec（仕様書）
  ↓ 実装の根拠
実装
```

**フロー原則:**

- **スキップ可:** 小規模な決定ではresearchを省略してADRから開始できる。自明な仕様ではADRから直接実装に進めることもある
- **逆流不可:** specからADRの決定を覆さない。決定を変更する場合は新しいADRを作成する

**接続方法:**

- research → ADR: ADRの「参考」セクションでresearchをリンク
- ADR → spec: specのfrontmatter `related_adr` および「背景・ADR参照」セクションでADRをリンク

## ライフサイクル

`adr/`, `spec/`, `research/` 配下のドキュメントには YAML frontmatter で `status` を持たせる。

| ステータス | 意味 |
| --- | --- |
| `wip` | 作成中・レビュー待ち |
| `accepted` | 承認済み・実装の根拠として有効 |
| `archive` | 廃止・過去の記録 |

詳細は [guides/document-lifecycle.md](guides/document-lifecycle.md) を参照。

## ドキュメントの作り方

1. 対象ディレクトリの `_template.md` をコピー
2. ファイル名を `NNNN-タイトル.md` に変更（例: `0002-auth-method.md`）
3. frontmatter を埋めて `status: wip` で作成
4. レビュー・承認後に `status: accepted` に変更

## AIツールとの連携

- AIツールは `status: accepted` のドキュメントのみを実装の根拠とする
- `wip` は明示的に指示がない限り実装に使わない
- 詳細は [guides/document-lifecycle.md](guides/document-lifecycle.md) を参照
