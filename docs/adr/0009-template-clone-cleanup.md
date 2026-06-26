---
id: "0009"
title: "テンプレート複製用クリーンアップスクリプトと固有履歴の線引き"
status: accepted
created: 2026-06-27
updated: 2026-06-27
decision_owner: "プロジェクトリーダー"
---

# テンプレート複製用クリーンアップスクリプトと固有履歴の線引き

## コンテキスト

本リポジトリは AI支援開発のドキュメント駆動フローを提供する**テンプレート**である。一方で、テンプレート自体を構築する過程で `docs/adr/`・`docs/spec/`・`docs/research/` に固有の意思決定・調査が蓄積している（ADR 0002〜0008、spec 0002〜0006、research 0001〜0004）。

このリポジトリを新規プロジェクトのテンプレートとして複製した利用者にとって、**構築過程の固有履歴は読み解く負荷（ノイズ）**になる。複製直後に固有履歴を取り除き、テンプレ機構と必要最小限の根拠だけが残る状態にする手段が必要。

決めるべきは2点。

1. **クリーンアップの仕組み**: どう機構を提供するか。
2. **固有履歴の線引き**: 何を「テンプレ機構（残す）」と「固有履歴（消す）」に分けるか。とくに [tools/agent-sandbox/](../../tools/agent-sandbox/) と [guides/multi-agent-playbook.md](../guides/multi-agent-playbook.md) を残す方針（本セッションで決定）により、それらが依存する ADR/spec/research も連動して残す必要がある。

## 検討した選択肢

### 軸1: クリーンアップの仕組み

#### 選択肢 1-A: 複製済みクリーンブランチ

- 利点: 利用者はそのブランチから複製するだけ。
- 欠点: 本流（`main`）更新のたびにブランチへ追従が必要。二重管理になる。

#### 選択肢 1-B: クリーンアップスクリプト（採用）

- `scripts/init-template.sh` を `main` に置き、複製後に1回実行して固有docを削除する。
- 利点: 本流と二重管理にならず常に最新。スクリプト自身が「何を消すか」のドキュメントになる。
- 欠点: 利用者が1回実行する一手間が残る。

### 軸2: 固有履歴の線引き

判断原則: **残したコード/機構の「根拠」となる doc は残す。テンプレ構築そのものを記録したメタ履歴は消す。**

#### 選択肢 2-A: メタ履歴のみ削除（保守的）

- 削除は「テンプレ構築のメタ」に限定（research 0001/0002・ADR 0002）。capability の根拠（sandbox系・github系 ADR/spec）はすべて残す。
- 利点: 根拠が完全に残る。
- 欠点: 利用者には依然 ~6 ADR が残り「複雑すぎる」課題が十分に解けない。

#### 選択肢 2-B: capability基準で削除（採用・推奨）

- **残す capability の根拠**は残し、**自己記述で足りるもの**と**メタ履歴**は消す。
  - sandbox クラスタ（コードを残すため根拠も残す）: ADR 0003/0004/0005/0006、spec 0002/0003/0004/0005、research 0003/0004。
  - github運用の paper trail は削除: ADR 0007/0008、spec 0006。`.github/` 実体は**ファイル内コメントで自己記述**しており、着手ゲートの根拠は CLAUDE.md と [scripts/hooks/impl-gate.py](../../scripts/hooks/impl-gate.py) 自体に残るため、ADR/spec を消してもテンプレ機構は機能する。
  - メタ履歴を削除: research 0001（他プロジェクト事例調査）、research 0002（不足要素分析）、ADR 0002（不足要素補完方針）。
- 利点: 利用者が読む doc を sandbox の根拠＋テンプレ/example に絞れる。「簡素化」の目的を満たす。
- 欠点: github運用の意思決定経緯は失われる（ただし `.github/` のコメントと guides に運用方法は残る）。

#### 選択肢 2-C: example以外を全削除（最小）

- `_template.md` と `0001-example` 以外の番号付き doc をすべて削除。
- 欠点: sandbox を残す決定と矛盾（multi-agent-playbook の参照が宙に浮く）。**不採用**。

## 決定

- **軸1: 1-B（`scripts/init-template.sh`）** を採用。
- **軸2: 2-B（capability基準）** を推奨として起票。最終的な削除/保持リストは下表。**本ADRが accepted になるまでスクリプトは実装しない。**

### スクリプト要件（`scripts/init-template.sh`）

- **冪等**: 既に削除済みでも失敗しない（存在チェックして消す）。
- **確認プロンプト**: 破壊的操作のため、実行時に対象一覧を表示し `y/N` 確認（`--yes` で省略可）。
- **末尾で検証**: `bash scripts/validate-docs.sh` を流し、残った doc の frontmatter 整合を確認。
- **自己削除**: 最後に `scripts/init-template.sh` 自身を削除（テンプレ利用後は不要）。

### 削除リスト（固有履歴）

| 対象 | 区分 |
| --- | --- |
| `docs/adr/0002,0007,0008` | メタ / github paper trail |
| `docs/spec/0006` | github paper trail |
| `docs/research/0001,0002` | テンプレ構築メタ |

### 保持リスト（テンプレ機構 + capability根拠）

- sandbox クラスタ: `tools/agent-sandbox/`、`guides/multi-agent-playbook.md`、ADR 0003/0004/0005/0006、spec 0002/0003/0004/0005、research 0003/0004。
- フロー/ゲート機構: 全 `guides/`（multi-agent含む）、`_template.md`×3、`0001-example`（adr/spec）、`steering/*`、`README.md`、`.github/`、`scripts/hooks/`、`scripts/validate-docs.sh`、`design-tokens/`、`CLAUDE.md`。

### 編集リスト（削除に伴う参照除去）

全リポジトリを grep して確定した、削除対象 doc を参照する保持ファイル:

- [CLAUDE.md](../../CLAUDE.md): 着手ゲート節の ADR 0008 への参照を除去（根拠は hook と本節自体に残る）。
- [scripts/hooks/impl-gate.py](../../scripts/hooks/impl-gate.py): 冒頭コメントの ADR 0008 への参照を除去。
- [docs/guides/human-in-the-loop.md](../guides/human-in-the-loop.md): 削除する ADR 0007 / spec 0006 への参照を除去・汎用化。ADR 0004（保持）への参照は残す。
- `.github/labels.yml` / `.github/ISSUE_TEMPLATE/task.md` / `.github/pull_request_template.md` / `.github/workflows/ci.yml` / `.github/CODEOWNERS`: 「spec 0006 / ADR 0008 に準拠」コメントから削除対象への参照を除去。
- 本ADR（0009）自身: 参考節の ADR 0002 / 0008 リンクを delink（削除済みを明記）。

※ `development-loop-playbook.md` は削除対象 doc を参照していない（ADR 0003/0004 は保持対象）ため編集不要。`docs/README.md` line 76 は散文の例示で実リンクではないため対象外。

## 影響

- 正: 複製後の利用者が読む doc が sandbox 根拠＋テンプレ/example に絞られ、「複雑すぎる」課題を緩和。
- 正: 仕組みがスクリプト1本で本流と二重管理にならない。
- 負: github運用の意思決定経緯（ADR 0007/0008）が複製先から失われる。本リポジトリ（`main`）には残るため参照は可能。
- リスク: 破壊的操作。確認プロンプト + `validate-docs` + git管理下での実行を前提に緩和。

## 参考

- [ADR 0002: 不足要素補完方針](./0002-template-extension-policy.md)（削除対象）
- [ADR 0008: GitHub scaffolding iteration](./0008-github-scaffolding-iteration.md)（着手ゲートの根拠・削除対象）
- [guides/template-overview.md](../guides/template-overview.md)（テンプレ利用フロー）
- [guides/document-lifecycle.md](../guides/document-lifecycle.md)
