# 複数エージェント並列運用 Playbook

> 複数の Claude Code セッション（または他 CLI agent）を **同時に走らせる** ための実践ガイド。
> 1 イテレーションを順次回す話は [development-loop-playbook.md](./development-loop-playbook.md) を参照。

## 1. なぜ複数 agent を回すか

| 目的 | 例 |
| --- | --- |
| **調査の fan-out** | research 0003 / 0004 を別 agent に並行調査させる |
| **機能の並列実装** | spec 0003 (supervisor) と spec 0005 (Nimbalyst) を別 agent で同時実装 |
| **多角レビュー** | 同じ PR を 3 つの観点（バグ / セキュリティ / 性能）で並列レビュー |
| **A/B 検証** | 同じ prompt に対する複数モデル / 設定の比較 |
| **長時間タスクと並走** | 「巨大 refactor を背景で回しつつ、本人は別 spec を書く」 |

順次でも済む場合は無理に並列しない。並列は **コンテキスト切替の認知コスト** と **ホスト資源（CPU / メモリ / 課金）** を消費するため、目的を明確にする。

## 2. 並列パターン 4 種

このリポジトリでは 4 つの並列方式が選べる。隔離強度と autonomy が異なる。

### A. 複数ターミナル（ホスト直接）

```bash
# 別ターミナルそれぞれで
cd ~/projects/<repo>
claude          # ホスト権限で実行
```

| 項目 | 評価 |
| --- | --- |
| 隔離 | ❌ 全 session が同じホスト権限・同じ workspace |
| 起動コスト | ◎ ゼロ |
| autonomy | 各セッションは独立 |
| 競合リスク | 高（同じファイルを同時編集しうる）|
| 適性 | 信頼できる単一開発者、調査メイン、書き込みが少ない作業 |

### B. 複数 worktree + agent-sandbox

```bash
# worktree を切る
git worktree add ../work-A -b feat/A
git worktree add ../work-B -b feat/B

# それぞれを別ターミナルで
WORKSPACE=/abs/path/to/work-A docker compose -f tools/agent-sandbox/compose.yml run --rm agent
WORKSPACE=/abs/path/to/work-B docker compose -f tools/agent-sandbox/compose.yml run --rm agent
```

| 項目 | 評価 |
| --- | --- |
| 隔離 | ◎ [ADR 0003](../adr/0003-agent-execution-docker-isolation.md) の最小権限プロファイル + worktree 分離 |
| 起動コスト | ○ 起動 5〜10 秒 |
| autonomy | 各 agent は自分の worktree 内で完結 |
| 競合リスク | 低（worktree が物理的に分離） |
| 適性 | **デフォルト推奨**。機能並列実装・調査・レビュー全般 |

### C. supervisor 経由のサブエージェント自動起動

```bash
# supervisor を常駐
WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml up -d supervisor egress-proxy

# 親 agent から request を書く（autonomous spawn）
echo '{"task_id":"t-1","prompt":"do X"}' > tools/agent-sandbox/shared/requests/t-1.json
# → supervisor が検知して子 agent を別コンテナで起動
# → 完了したら shared/results/t-1.json に書き戻し
```

| 項目 | 評価 |
| --- | --- |
| 隔離 | ◎ [ADR 0004](../adr/0004-subagent-execution-pattern.md) の supervisor pattern |
| 起動コスト | △ 1 リクエスト 30〜60 秒 |
| autonomy | **親が自律的に子を起こす**（人間の操作不要）|
| 競合リスク | 極低（git worktree で物理分離 + git ロック） |
| 適性 | 親 agent が「これをサブに任せたい」と判断したケース。バッチ調査・並列タスク分解 |

詳細は [tools/agent-sandbox/supervisor/README.md](../../tools/agent-sandbox/supervisor/README.md) を参照。

### D. GUI オーケストレーション（Nimbalyst）

```bash
# Nimbalyst の launch-cmd に wrapper を指定
chmod +x tools/agent-sandbox/scripts/run-via-nimbalyst.sh
# Nimbalyst Settings → /abs/path/.../run-via-nimbalyst.sh {{worktree}}
```

| 項目 | 評価 |
| --- | --- |
| 隔離 | ◎ B と同じ隔離プロファイル |
| 起動コスト | ○ Nimbalyst が worktree を切ってくれる |
| autonomy | 人間が GUI で起動 / 監視 |
| 競合リスク | 低（Nimbalyst が worktree 単位で分離） |
| 適性 | **複数 session を視覚的に監視・切替**したい時。レビュー・比較作業 |

詳細は [ADR 0006](../adr/0006-orchestration-gui-nimbalyst.md) と [tools/agent-sandbox/README.md](../../tools/agent-sandbox/README.md) の「GUI 連携（Nimbalyst）」節を参照。

## 3. パターンの選び方

```text
信頼できないコードを触る？
  Yes → B / C / D (隔離必須)
  No  → A も可

親 agent が自律的に「子を呼ぶか」判断する必要がある？
  Yes → C (supervisor)
  No  → 続く

GUI で並列セッションを視覚的に管理したい？
  Yes → D (Nimbalyst)
  No  → 続く

ホスト権限でいい、軽さ最優先？
  Yes → A (terminal)
  No  → B (worktree + sandbox)
```

迷ったら **B** が無難。隔離は維持しつつコストも小さい。

## 4. 競合回避の鉄則

複数 agent を並列に走らせると、**同じファイルを編集して衝突する**のが最大の事故。

### 4-1. workspace の物理分離（必須）

- ❌ 同じ worktree を 2 つの agent にマウントしない
- ✅ `git worktree add` で別ディレクトリを切る
- ✅ supervisor pattern は task_id ごとに worktree を自動生成

### 4-2. branch の分離

- ❌ 同じ branch を 2 つの worktree でチェックアウト（git が拒否する）
- ✅ feature branch を agent ごとに分ける（`feat/A`, `feat/B`）

### 4-3. 共有リソース

| 共有されるもの | 競合する？ | 対処 |
| --- | --- | --- |
| 名前付き volume `claude-config` | △ 同時書込で OAuth セッションが壊れうる | 初回ログイン後は読み取り中心になるので実害は稀 |
| `shared/audit/*.jsonl` | ✅ 競合 | supervisor が append-only で書く設計、複数 supervisor は同時起動しない |
| `shared/requests/` / `shared/results/` | ❌ task_id 一意 | task_id を UUID にする運用 |
| ホストの git index | ✅ 競合 | 並列 commit を避ける、または worktree ごとに完結させる |
| API rate limit | ✅ 競合 | 後述 |

### 4-4. supervisor の同時起動数

`MAX_CONCURRENT_SUBAGENTS`（既定 4）で物理的に上限を設けている。これを超える request は queue されて順次処理。CPU / メモリ / API rate に応じて調整。

```bash
MAX_CONCURRENT_SUBAGENTS=2 \
  WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml up -d supervisor
```

## 5. リソース・コストの管理

### 5-1. ホスト資源

| 資源 | 1 agent あたりの目安 | 8 並列の時 |
| --- | --- | --- |
| メモリ | 1 GiB | 8 GiB + α |
| CPU | 1 core でも回る | 4〜8 core 推奨 |
| ディスク | worktree のサイズに比例 | 大規模 repo だと爆発する |

8 worktree × 巨大 repo はディスクを潰しがち。**bare repo + clone** に切り替える運用も検討（[ADR 0004](../adr/0004-subagent-execution-pattern.md) 参照）。

### 5-2. API コスト / rate limit

並列 agent は **トークン消費がリニアに増える**。Pro / Max サブスクでも rate limit に当たる。

- **OAuth (subscription)** 利用時：rate limit は契約に依存。並列度を 2〜4 に抑えるのが現実的
- **API key** 利用時：Anthropic console で組織のレート / 残額を監視
- Anthropic の文書では「parallel subagent fanout は rate limit に当たりうる、batch を小さく」と明記されている

### 5-3. autonomous spawn の暴走対策

親 agent が prompt injection 等で「サブを 100 個起こせ」と判断する事故を防ぐ：

- supervisor の `policy.yml` の `allowed_request_fields` で枠を絞る
- `MAX_CONCURRENT_SUBAGENTS` で並列を絞る
- `SUPERVISOR_REQUIRE_APPROVAL=1` で human-in-the-loop モードに切替

## 6. 実運用パターン集

### パターン 1: research fan-out

「3 つの観点から調査して」のとき、parent agent が 3 つの request を `shared/requests/` に書く → supervisor が並列に走らせる → results を読んで synthesis。

```bash
for topic in A B C; do
  cat > tools/agent-sandbox/shared/requests/research-$topic.json <<EOF
  {"task_id":"research-$topic","prompt":"investigate $topic and write a 500 word summary"}
EOF
done
# 並列に 3 つ走る (MAX_CONCURRENT_SUBAGENTS が 3 以上なら同時)
```

### パターン 2: 機能の並列実装

機能 A と機能 B を別 worktree + 別 agent で同時実装：

```bash
git worktree add ../work-A -b feat/A
git worktree add ../work-B -b feat/B

# Nimbalyst で同時に 2 sessions
# または terminal 2 つで run-via-nimbalyst.sh /abs/path/work-A
```

それぞれの worktree で commit → 後で main に merge。

### パターン 3: 多角レビュー

同じ PR を 3 観点（バグ / セキュリティ / 性能）で並列レビュー：

```bash
# 3 つの request、各 prompt を変える
for view in bug security perf; do
  cat > tools/agent-sandbox/shared/requests/review-$view.json <<EOF
  {"task_id":"review-$view","prompt":"review PR #123 from $view perspective"}
EOF
done
```

それぞれの results を集めて最終所見を作る。

### パターン 4: 長時間タスクと並走

巨大 refactor を background で回しつつ、本人は別 spec を書く：

```bash
# Refactor を supervisor 経由で投入
echo '{"task_id":"big-refactor","prompt":"refactor module X per spec 0010"}' \
  > tools/agent-sandbox/shared/requests/big-refactor.json

# 自分は別 worktree で別 spec を編集
git worktree add ../work-spec0011 -b spec/0011
cd ../work-spec0011
$EDITOR docs/spec/0011-new-feature.md
```

## 7. アンチパターン

| アンチパターン | なぜ駄目 | 代わりにすべきこと |
| --- | --- | --- |
| 同じ worktree に 2 agent | ファイル競合・git index 破損 | worktree を分ける |
| 並列度を青天井 | API rate limit / OOM | `MAX_CONCURRENT_SUBAGENTS` で上限 |
| supervisor 複数起動 | audit が壊れる、worktree 名衝突 | 1 ホスト 1 supervisor |
| docker.sock を agent にマウントして子起動 | 隔離崩壊（[ADR 0004](../adr/0004-subagent-execution-pattern.md) で禁止） | supervisor pattern を使う |
| 子から親に同期戻し | デッドロックを生む | 完了は results ファイル + audit log で非同期 |
| token / cost を測らず並列度を上げる | 課金で事故る | 並列前に 1 タスクのコストを計測 |
| Nimbalyst の launch-cmd を生 claude に | 隔離が掛からない | `scripts/run-via-nimbalyst.sh` 経由にする |

## 8. ループとの組み合わせ

[development-loop-playbook.md](./development-loop-playbook.md) の 1 イテレーションループ × 並列化＝：

```text
              ┌─ research-A
1 イテレーション ─┼─ research-B  ← 並列 fan-out
              └─ research-C
                    │
                    ▼ synthesis
                  ADR (順次)
                    │
                    ▼
                  spec (順次)
                    │
              ┌── 実装-A
              ├── 実装-B  ← 並列
              └── 実装-C
                    │
                    ▼
                  受け入れテスト
                  (順次・全体)
```

**fan-out するのは research と実装のフェーズ**。ADR と spec の確定は順次が原則（決定は 1 つに収束させる）。

## 9. 関連ドキュメント

- [development-loop-playbook.md](./development-loop-playbook.md) — 1 イテレーションの回し方
- [workflows.md](./workflows.md) — フェーズ全体の理想形
- [tools/agent-sandbox/README.md](../../tools/agent-sandbox/README.md) — agent コンテナ運用
- [tools/agent-sandbox/supervisor/README.md](../../tools/agent-sandbox/supervisor/README.md) — supervisor 詳細
- [ADR 0003](../adr/0003-agent-execution-docker-isolation.md) — 隔離方針
- [ADR 0004](../adr/0004-subagent-execution-pattern.md) — subagent supervisor
- [ADR 0006](../adr/0006-orchestration-gui-nimbalyst.md) — GUI 採用方針
- [research 0004](../research/0004-agent-observability-gui-tools.md) — GUI / observability の比較調査
