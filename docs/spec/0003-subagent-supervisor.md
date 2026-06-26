---
id: "0003"
title: "subagent-supervisor: 親 agent からサブエージェントを安全に起動する"
status: accepted
phase: mvp
created: 2026-06-22
updated: 2026-06-22
related_adr: ["0003", "0004"]
---

# subagent-supervisor: 親 agent からサブエージェントを安全に起動する

## 概要

親 agent コンテナの隔離（ADR 0003）を一切緩めずに、親が autonomous にサブエージェントを起こせる経路を `tools/agent-sandbox/supervisor/` に実装する。トリガーは共有 volume 上のファイル + inotify、supervisor は Python、ワークスペースは git worktree、承認モードは env 切替。

## 背景・ADR参照

- [ADR 0003: エージェント実行は Docker Compose で隔離する](../adr/0003-agent-execution-docker-isolation.md)（accepted）
- [ADR 0004: サブエージェントは外側 supervisor 経由で兄弟コンテナ起動する](../adr/0004-subagent-execution-pattern.md)（accepted）

ADR 0004 §「設計図」の ER 図 / 状態遷移図 / シーケンス図を「実装の唯一の真実」とする。親コンテナは docker daemon に **絶対に到達できない** という不変条件を維持する。

## 要件

### 機能要件

- **MUST**:
  - 親コンテナが `/shared/requests/<task_id>.json` を書くと、ホスト supervisor がそれを検知して子 agent コンテナを起動する
  - 子コンテナは ADR 0003 と同じ隔離プロファイル（UID 1000 / `cap_drop: ALL` / `read_only` / `internal` ネット）で起動する
  - supervisor は内部に固定された起動テンプレを持ち、親から渡せるフィールドは `task_id` / `prompt` / `workspace_ref` のみ。他のフィールドは drop
  - `policy.yml` で `allowed_image` / `forbidden_volume_patterns` / `forbidden_env` / `max_prompt_length` を強制
  - SPAWN_REQUEST の status を `pending → spawned → done | rejected` の状態機械で管理し、結果を `/shared/results/<task_id>.json` に書く
  - 全イベント（issued / validated / spawned / completed / rejected）を `/shared/audit/YYYY-MM-DD.jsonl` に append-only で記録
  - 同時起動数を `MAX_CONCURRENT_SUBAGENTS`（既定 4）でセマフォ制御
  - 親コンテナは `docker.sock` および supervisor の docker 経路にいかなる手段でも到達できない
- **SHOULD**:
  - `SUPERVISOR_REQUIRE_APPROVAL=1` で承認モード（CLI で y/n を待つ）を有効化可能
  - 承認待ちタイムアウト（既定 60 秒）を `SUPERVISOR_APPROVAL_TIMEOUT_SEC` で設定可能
  - inotify が WSL2 等で動作しない場合の fallback として poll 動作（`SUPERVISOR_POLL_MS` で切替）を提供
  - git worktree の cleanup は **成功時のみ**、失敗時は保持してデバッグ可能に
- **COULD**:
  - 承認モード時に Slack / Webhook 通知を送る（後続 ADR で扱う）

### 非機能要件

- **パフォーマンス**：request 書き込みから子コンテナ起動までの遅延が 3 秒以内（正常系）。
- **セキュリティ**：
  - supervisor 自身は `docker.sock` を持つため、コード変更はレビュー必須（README で明文化）
  - `policy.yml` は allowlist 方式（明示的許可のみ）を強制
  - 親コンテナのプロファイルは spec 0002 から **一切変更しない**

## スコープ

### このフェーズで対応するもの

- `tools/agent-sandbox/Dockerfile.supervisor`：`python:3.12-slim` + `inotify_simple` + `PyYAML` + `docker` CLI
- `tools/agent-sandbox/supervisor/supervisor.py`：inotify ループ + policy 検証 + docker compose 起動 + audit 書き込み
- `tools/agent-sandbox/supervisor/policy.yml`：許可テンプレと禁止フラグ
- `tools/agent-sandbox/supervisor/README.md`：構成とセキュリティ注意事項
- `tools/agent-sandbox/compose.yml` の更新：`supervisor` サービスと `./shared:/shared` volume を `agent` にも追加
- `tools/agent-sandbox/README.md` の「サブエージェント呼び出し」セクション追記
- `.gitignore` に `tools/agent-sandbox/shared/` を追加
- 受け入れテスト 8 種

### 対応しないもの（後続フェーズ）

- Observability sidecar（ADR 0005 / 別 spec）
- GUI ツール（Nimbalyst）との launch-cmd 連携（ADR 0006 / 別 spec）
- Sysbox / rootless supervisor への移行（ADR 0004 の将来オプション）
- Slack/Webhook 等の承認通知

## 技術設計

### ディレクトリ構成

```text
tools/agent-sandbox/
├── compose.yml                      # 更新
├── Dockerfile.supervisor            # 新規
├── supervisor/                      # 新規
│   ├── supervisor.py
│   ├── policy.yml
│   └── README.md
└── (gitignored) shared/
    ├── requests/
    ├── results/
    ├── audit/
    └── worktrees/
```

### supervisor サービスの compose 設計

- `network_mode: host` ではなく **独立 bridge** に置く。`isolated` には**入れない**（agent から到達不可にするため）
- `volumes`:
  - `/var/run/docker.sock:/var/run/docker.sock:rw` ← supervisor 専用
  - `./shared:/shared:rw`
  - `../../:/work:ro`（git worktree 操作のためのプロジェクトルート参照）
  - `./supervisor/policy.yml:/etc/supervisor/policy.yml:ro`
- `user: root`（docker CLI と git worktree 操作のため）。ただし worktree path / shared/ への書き込み権限を agent UID 1000 と整合させる
- `restart: unless-stopped`
- 環境変数：`MAX_CONCURRENT_SUBAGENTS=4`、`SUPERVISOR_REQUIRE_APPROVAL=0`、`SUPERVISOR_POLL_MS=0`、`SUPERVISOR_APPROVAL_TIMEOUT_SEC=60`

### SPAWN_REQUEST スキーマ

```json
{
  "task_id": "string (UUID 推奨、必須)",
  "prompt": "string (最大 max_prompt_length、必須)",
  "workspace_ref": "string (HEAD でも branch でも可、省略時は HEAD)"
}
```

他のフィールドは無視。

### RESULT スキーマ

```json
{
  "task_id": "string",
  "status": "done | rejected",
  "exit_code": 0,
  "rejected_reason": "string (rejected 時のみ)",
  "worktree_path": "string (spawned 時のみ)",
  "started_at": "ISO8601",
  "finished_at": "ISO8601"
}
```

### AUDIT_LOG スキーマ

`/shared/audit/YYYY-MM-DD.jsonl` に 1 イベント 1 行：

```json
{"seq": 1, "task_id": "t1", "event": "issued", "at": "...", "payload": {...}}
```

`event ∈ {issued, validated, spawned, completed, rejected}`、`seq` はファイル内連番。

### policy.yml の構造

```yaml
allowed_image: "agent-sandbox/claude:*"
fixed_compose_file: "/work/tools/agent-sandbox/compose.yml"
fixed_service: "agent"
forbidden_env:
  - DOCKER_HOST
  - ANTHROPIC_BASE_URL_OVERRIDE
forbidden_volume_patterns:
  - "/var/run/docker.sock"
  - "/proc"
  - "/sys"
  - "$HOME/.ssh"
  - "$HOME/.aws"
max_prompt_length: 8192
allowed_request_fields: ["task_id", "prompt", "workspace_ref"]
```

### supervisor.py アルゴリズム

1. 起動時に `policy.yml` ロード、`/shared/{requests,results,audit,worktrees}` を `mkdir -p`
2. `inotify_simple.INotify` で `/shared/requests/` を `IN_CLOSE_WRITE` 監視。`SUPERVISOR_POLL_MS > 0` なら poll fallback
3. ファイル検知 → JSON ロード → `allowed_request_fields` で whitelisting → policy 検証
4. 不合格なら `_write_result(rejected, reason)` + audit
5. 承認モード有効なら stdin 待ち（timeout 後 reject）
6. セマフォ取得（`threading.BoundedSemaphore(MAX_CONCURRENT_SUBAGENTS)`）
7. git worktree add：`git -C /work worktree add /shared/worktrees/<task_id> <workspace_ref>`
8. `docker compose -f <fixed_compose_file> run --rm -v /shared/worktrees/<task_id>:/workspace agent -p <prompt>` を subprocess で実行
9. exit code を待ち `_write_result(done | rejected, exit_code)` + audit
10. 成功時のみ `git worktree remove --force`

### 親 agent コンテナの修正

`compose.yml` の `agent` service に：
- `volumes: ./shared:/shared:rw` を追加
- 子用に `profiles: [run, sub]`

agent service 自体は **隔離プロファイル（cap_drop / read_only / 等）を一切変更しない**。

### 拒否設定

- 親コンテナから `docker.sock` への path がいかなる経由でも存在しない
- supervisor は agent と異なる network（`internal: true` ではない）に配置するが、agent から supervisor へは届かない
- `--privileged` 禁止：compose ファイルに記述しない

## 受け入れ基準

実テスト時の判定方針：「プラミング（経路の正しさ）」と「子コンテナ内 claude の成否」を分けて扱う。前者は本 spec のスコープ、後者は ANTHROPIC_API_KEY の有無など runtime 設定の問題。

- [x] `WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml build` が成功する
- [x] `WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml up -d supervisor egress-proxy` が成功し、supervisor が `running` 状態になる
- [x] **プラミング正常系**：親コンテナから `/shared/requests/<task_id>.json` を書くと、AUDIT に `issued → validated → spawned → completed` が seq 順に記録され、`results/<task_id>.json` が現れる（`status: done` まで到達するかは ANTHROPIC_API_KEY の設定に依存）
- [x] **policy 違反**：未許可フィールド（例：`"image": "alpine"`）を含む request は `results/<task_id>.json` に `status: rejected` と理由 `unexpected fields: ['image']` が即座に書かれる
- [x] **子の隔離**：spec 0002 と同じ compose 定義を使用するため、子コンテナの UID 1000 / 空 cap / 読み取り専用 root FS は同等
- [x] **親の隔離**：親コンテナから `ls /var/run/docker.sock` が "No such file or directory"、`agent-sandbox-supervisor` ホスト名解決不可
- [x] **AUDIT**：`shared/audit/YYYY-MM-DD.jsonl` に該当 task_id の `issued / validated / spawned / completed` が seq 順に記録されている
- [x] `bash scripts/validate-docs.sh` がエラー 0
- [x] `tools/agent-sandbox/README.md` に「サブエージェント呼び出し」「policy 編集手順」「approval mode 有効化」が記載
- [ ] **並列**（未実施）：`MAX_CONCURRENT_SUBAGENTS=2` で 3 つ同時 request を書くと、3 つ目は queue され順次処理される — 実装上は `threading.BoundedSemaphore(MAX_CONCURRENT)` で確保。後続で実機検証

## 未解決事項

実 MVP の動作確認で解決済み：

- ~~supervisor の `user: root` と worktree オーナー整合性~~ → `chown_agent` ロジックと git `safe.directory=*` で解決
- ~~inotify の cross-fs 制約（WSL2）~~ → Docker Desktop on WSL2 で動作確認済み。万一動かない環境向けに `SUPERVISOR_POLL_MS` fallback を残置
- ~~重複 task_id の扱い~~ → 既存 results を検知して `rejected: duplicate task_id`
- ~~docker compose を supervisor 内から呼ぶ際の bind-mount path 解決~~ → `${WORKSPACE}:${WORKSPACE}:rw` host-path-matching で解決

後続で扱うもの：

- 並列スループットの実機検証（`MAX_CONCURRENT_SUBAGENTS=2` で 3 同時投入）
- `forbidden_volume_patterns` / `forbidden_env` は現状 request スキーマに反映されないため未到達のコード。将来 request スキーマを拡張する際に発動するよう policy 検証関数を呼ぶ
- supervisor 自身のヘルスチェック（compose の healthcheck を後付け）
- access_log 用 logger sidecar（squid と共通化、別 spec）
