# 開発ループ運用 Playbook

> 「要求整理 → 設計 → 実装」を **AI と一緒に反復する** ための実践ガイド。
> 全体フロー定義は [workflows.md](./workflows.md) を参照。本ガイドは **ループの回し方** に焦点。

## 1. 1 イテレーションの基本ループ

```text
[アイデア / 課題]
     │
     ▼
┌────────────────────┐
│ research (任意)    │ status: wip → accepted
│ 候補と根拠を並べる │
└─────────┬──────────┘
          │ 採否の判断材料
          ▼
┌────────────────────┐
│ ADR                │ status: wip → accepted
│ 何を採用するか決定 │
└─────────┬──────────┘
          │ 決定の確定
          ▼
┌────────────────────┐
│ spec               │ status: wip → accepted
│ 要件・受入基準     │
└─────────┬──────────┘
          │ 実装契約
          ▼
┌────────────────────┐
│ 実装 + 受入テスト  │
└─────────┬──────────┘
          │
   ┌──────┴──────┐
   ▼             ▼
[OK 完了]    [想定外発覚]
              │
              ▼
        ADR amend or 再起票
        (ループに戻る)
```

**重要なのは右下の枝**：実装中に想定外が出るのが普通。そのときは ADR を **amend** または **archive + 新規** で対応する。再実装ではなく、決定を更新する。

## 2. 各フェーズの所要作業

### research（必要に応じて）

書く対象：

- 競合・市場・技術の候補比較
- 「判断材料」が主であり「判断」は ADR で行う

成果物テンプレ：[docs/research/_template.md](../research/_template.md)
種別ガイド：[research-type-guide.md](./research-type-guide.md)

`status: wip` で書き始め、合意が取れたら `accepted` に。

### ADR（意思決定）

書く対象：

- 選択肢の比較
- 採用と理由
- 影響（正 / 負 / リスク）

成果物テンプレ：[docs/adr/_template.md](../adr/_template.md)

**accepted への昇格は実装前**。実装中に揺れたら amend する（後述）。

### spec（仕様）

書く対象：

- 機能要件（MUST / SHOULD / COULD）
- 非機能要件
- スコープと非スコープ
- **受け入れ基準（チェックボックス）**
- 未解決事項

成果物テンプレ：[docs/spec/_template.md](../spec/_template.md)

**受け入れ基準が spec の心臓**。後述の通り、これが実装の契約になる。

### 実装 + 受け入れテスト

- accepted な spec の受け入れ基準を 1 つずつ満たす
- チェックボックスを `- [ ]` から `- [x]` に変えていく
- 満たせない項目があったら **嘘をつかない**。`未達` と明記して archive 化するか、ADR を amend する

## 3. 「壁にぶつかった時」の amend ループ

実装中に「採用した方針では動かない / 過剰 / コストに合わない」と分かるのは普通のこと。このときの選択肢：

| 選択 | いつ使う | 例（今回のセッション）|
| --- | --- | --- |
| **ADR を amend**（accepted のまま）| 方針の本筋は維持、選択肢だけ差し替え | ADR 0005: Langfuse → Phoenix → Collector（3 段 amend）|
| **ADR を archive + 新規 ADR** | 方針自体を撤回し、別軸の決定に切り替え | ADR 0005 / spec 0004 を archive 化（MVP から observability を削除）|
| **spec を改訂**（accepted のまま）| 受け入れ基準だけ変える、決定は同じ | spec 0004: Phoenix → Collector に伴う基準書き換え |
| **未解決事項に残置** | 上流が原因で当面解決不能（CI のバージョン待ち等）| CLI v2.1.185 で OTel emit が来ない問題 |

### amend を書く時の作法

ADR の冒頭に `> Amend 履歴:` ブロックを置き、追記する：

```markdown
> Amend 履歴:
>
> - 2026-06-22（初稿）: A 案を採用
> - 2026-06-22（amend 1）: ○○ の理由で B 案に変更
> - 2026-06-22（amend 2 / archive）: ○○ の理由で取り下げ
```

履歴は **消さない**。なぜ今こうなっているかが追えなくなる。

### archive を選ぶ時の作法

- frontmatter `status: archive`
- 冒頭に「本 ADR は archive 済み。実装の根拠としては使用しない」と明記
- 再導入時の方針も書く（「新 ADR を起票し、本 ADR を過去の検討として参照」）

## 4. 状態遷移ルール

```text
wip ──(レビュー)──► accepted ──(方針撤回)──► archive
                      │                          ▲
                      └──(方針変更)──► amend ────┘
                                       (accepted のまま)
```

| 状態 | 意味 | 実装の根拠になる？ |
| --- | --- | --- |
| `wip` | 作成中・レビュー待ち | ❌ |
| `accepted` | 承認済み | ✅ |
| `archive` | 廃止・過去の記録 | ❌（参考のみ）|

`scripts/validate-docs.sh` で frontmatter を機械的に検証できる。`accepted な spec に未解決事項が残っている` は **警告として運用**（致命傷ではないが意識する）。

## 5. AI コラボのパターン

このリポジトリで AI（Claude Code）と効率的に回すコツ。

### Plan mode を使うべきタイミング

- 既存ファイルの構造を変える時
- 新しい spec を起票する時
- 3 ファイル以上に手を入れる時

`/plan` で入り、調査→質問→計画→承認、の流れを踏むと、実装フェーズで迷走しにくい。

### AskUserQuestion で迷いを早く解消

AI が「進められるが選択肢がある」状況では、**勝手に決めずに聞く**。

例：今回のセッションで聞いた質問：

- observability backend は Phoenix / Langfuse / SigNoz どれにするか？
- supervisor のトリガーは file+inotify / HTTP / UDS どれにするか？
- Workspace 生成方式は git worktree / bare repo + clone / mktemp どれにするか？

これらは ADR を書く前に確定させると、後の手戻りが激減する。

### validate-docs を「儀式」にする

各フェーズの区切りで実行：

```bash
bash scripts/validate-docs.sh
```

- accepted に昇格させた直後
- archive に降格させた直後
- セッション末（commit 前）

エラーが 0 になっていることを確認してから次に進む。

## 6. 受け入れ基準を「契約」として扱う

spec の受け入れ基準は **実装側と仕様側の契約**。

| 状態 | 意味 |
| --- | --- |
| `- [ ]` | 未達 |
| `- [x]` | 達成 |
| `- [ ] **未達**：（理由と詳細）` | 達成不能だが理由が明確、上流に投げる |

実装が終わった時、**全項目を `- [x]` にする** か、**未達理由を spec の未解決事項に書く**、のどちらかが取れていれば spec を accepted に保てる。

> 例：spec 0004 の最後の項目 `Phoenix UI に span が現れる` は CLI 制限で未達だったが、未解決事項に「CLI emit 観測不可」を明記して accepted を維持した。後に archive 化する判断材料にもなった。

## 7. ループの「終わり」を判断する

1 イテレーションが「終わった」とは：

1. ✅ 関連 spec の受け入れ基準が全て `- [x]` または 未達理由つきで明示
2. ✅ `bash scripts/validate-docs.sh` がエラー 0
3. ✅ 動作確認が再現可能（README に手順が書かれている）
4. ✅ 次の人 / 次の自分が読んで判断材料を辿れる

これが揃ったら commit して次のループへ。揃ってないなら ADR か spec のどこかが甘い。

## 8. アンチパターン（今回避けたいもの）

| アンチパターン | なぜ駄目 | 代わりにすべきこと |
| --- | --- | --- |
| `wip` のまま実装に着手 | 方針が固まっていないので手戻り必発 | accepted に昇格させてから |
| 受け入れ基準を曖昧にする | 「終わった」の判定ができない | 機械的に検証可能な記述にする |
| 失敗を消す（コミット履歴から削除）| なぜそうなったかが追えなくなる | amend or archive で履歴を残す |
| ADR を実装中に書き始める | 決定が後付けで歪む | 実装前に書き、揺れたら amend |
| 「全部やってから commit」 | レビュー困難・rollback 困難 | 1 ループごとに commit |
| AI に「いい感じに」と丸投げ | スコープが発散する | AskUserQuestion で選択肢を出してもらう |
| `accepted` のまま放置して中身が陳腐化 | 古い決定で新規実装が始まる | 定期的に見直し、必要なら amend |

## 9. このリポジトリでの典型ループ（実例）

今回のセッションで実際に回したループの一例：

```text
1. ユーザ: 「Docker でエージェントを隔離したい」
   ↓
2. research/0003 (Docker 隔離の手法調査) を wip で起票
   ↓ AI が WebFetch / WebSearch で 8 一次資料を収集
3. research/0003 → accepted（候補と根拠が整理された）
   ↓
4. ADR 0003 (Docker Compose で隔離する) を wip → accepted
   ↓
5. spec 0002 (agent-sandbox 最小実装) を wip
   ↓ 受け入れテスト 5 種を定義
6. 実装: compose.yml / Dockerfile.agent / squid.conf
   ↓ 実行: docker compose run agent
7. テスト中に squid の dns_v4_first が obsolete と判明
   ↓ squid.conf を修正（小さい差分）
8. 5/5 テスト通過 → spec 0002 を accepted
   ↓
9. commit、次のループ（ADR 0004 へ）
```

これを何回も回す。amend が出ても焦らない、archive になっても残す、というのが本ガイドの要旨。

## 10. 関連ドキュメント

- [workflows.md](./workflows.md) — フロー全体像（理想形）
- [document-lifecycle.md](./document-lifecycle.md) — wip/accepted/archive の規約
- [research-type-guide.md](./research-type-guide.md) — research_type の選び方
- [review-guidelines.md](./review-guidelines.md) — レビュー指摘の蓄積
- [release-checklist.md](./release-checklist.md) — リリース時のチェック
- [feedback-loop-setup.md](./feedback-loop-setup.md) — Hooks + CI の組み方
