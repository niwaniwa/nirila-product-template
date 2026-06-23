# CLAUDE.md

AIがこのプロジェクトで作業する際に必ず参照するファイル。

## 必読: Steeringドキュメント

実装・設計・レビューの前に、以下を必ず読むこと：

| ファイル | 内容 |
| --- | --- |
| [docs/steering/product.md](docs/steering/product.md) | プロダクト概要・コアバリュー・MVP定義 |
| [docs/steering/tech.md](docs/steering/tech.md) | 技術スタック・選定理由・禁止事項 |
| [docs/steering/structure.md](docs/steering/structure.md) | ディレクトリ構成・命名規則・依存ルール |
| [docs/steering/roadmap.md](docs/steering/roadmap.md) | ロードマップ・フェーズ定義・優先度付け |

Steeringは「常時有効な参照文書」であり、ライフサイクル管理（wip/accepted/archive）は持たない。
プロジェクトの方針・構成が変わったタイミングで随時更新する。

## docs/ ディレクトリ構成

```
docs/
├── steering/         # プロジェクト知識（常時参照・ライフサイクルなし）
├── guides/           # 開発ガイド・ルール（ライフサイクル対象外）
│   ├── template-overview.md   # テンプレートの使い方・ディレクトリ構成
│   ├── workflows.md           # 開発フロー・ハイブリッドモデル
│   ├── feedback-loop-setup.md # フィードバックループ構築手順
│   ├── review-guidelines.md   # レビュー指針の蓄積・運用ルール
│   ├── release-checklist.md   # リリースチェックリスト
│   ├── research-type-guide.md # research_type の分類ガイド
│   └── human-in-the-loop.md   # 人の導線（決定・境界ゲート / Issue起票境界）
├── adr/              # ADR：技術的意思決定の記録
├── spec/             # 仕様書
├── research/         # 調査・分析
└── design-tokens/    # デザイントークン定義
```

**ドキュメント種別の責務:** research=調査・候補提示、adr=意思決定、spec=仕様定義。
researchに採否判断を書かない。フロー: `research → ADR → spec → 実装`（スキップ可、逆流不可）。
詳細は [docs/README.md](docs/README.md) を参照。

## ドキュメントのライフサイクル

`adr/`, `spec/`, `research/` には YAML frontmatter で `status` を持つ：

| ステータス | 意味 |
| --- | --- |
| `wip` | 作成中・レビュー待ち |
| `accepted` | 承認済み・実装の根拠として有効 |
| `archive` | 廃止・過去の記録 |

- `status: accepted` のドキュメントのみを実装の根拠とする
- `wip` は明示的な指示がない限り実装に使わない

詳細は [docs/guides/document-lifecycle.md](docs/guides/document-lifecycle.md) を参照。

## 実装着手ゲート（重要）

実装/設定ファイル（コード・CI・設定など、`docs/` 配下と `.md` 以外）の**作成・編集に着手する前**に、必ず確認する：

1. 対応する **`status: accepted` な spec/ADR** が存在するか
2. 人間の **明示的な着手承認**を得たか

**AskUserQuestion での方向選択は着手承認ではない。** 「次に何を設計・起票するか」を決めるだけであり、実装着手の許可ではない。未確認なら手を止めて確認を取ること。

- 設計ゲート内の成果物（`docs/` の research/ADR/spec/guides、plan ファイル）の作成はこのゲートの対象外。
- このゲートは PreToolUse hook（[scripts/hooks/impl-gate.py](scripts/hooks/impl-gate.py)）でリマインドされる（feedback-loop の「最初の砦」）。
- 根拠: [docs/adr/0008](docs/adr/0008-github-scaffolding-iteration.md) / [docs/guides/human-in-the-loop.md](docs/guides/human-in-the-loop.md)

## バリデーション

```bash
bash scripts/validate-docs.sh
```

`docs/steering/` はフロントマターなしのため検証対象外。
