# supervisor

親 agent コンテナが書いた `SPAWN_REQUEST` を検知して、サブエージェントを **固定テンプレで** 起動するホスト側プロセス。

- 根拠: [ADR 0004](../../../docs/adr/0004-subagent-execution-pattern.md) / [spec 0003](../../../docs/spec/0003-subagent-supervisor.md)

## なぜ supervisor が要るか

ADR 0003 で agent コンテナを `cap_drop: ALL` / 非 root / `internal` ネットに閉じ込めた。一方でサブエージェントを別コンテナで起こしたい場合、**親が docker と話せたら隔離設計が崩れる**（`docker.sock` マウントは実質 root 取得、privileged DinD も cap drop と矛盾）。

そこで「親はファイルを書くだけ、ホストの supervisor が docker compose run を代行する」モデルを採る。`policy.yml` で親から渡せる入力を **whitelisting** することで、親が prompt injection で乗っ取られても許可外の起動は物理的に作れない。

## ファイル

| ファイル | 役割 |
| --- | --- |
| `supervisor.py` | inotify ループ + 検証 + docker compose 起動 + AUDIT_LOG |
| `policy.yml` | 許可 image / 許可フィールド / 禁止 env / 禁止 volume / 上限 |
| `README.md` | 本ファイル |

## 親 → supervisor インターフェイス

親 agent コンテナは `/shared/requests/<task_id>.json` を書くだけ：

```json
{
  "task_id": "t-2026-06-22-1",
  "prompt": "list the files in this branch",
  "workspace_ref": "HEAD"
}
```

`task_id` / `prompt` / `workspace_ref` 以外のフィールドは **drop** される（== reject）。

## supervisor → 親 インターフェイス

`/shared/results/<task_id>.json` に書かれる：

```json
{
  "task_id": "t-2026-06-22-1",
  "status": "done",
  "exit_code": 0,
  "worktree_path": null,
  "rejected_reason": null,
  "started_at": "2026-06-22T05:30:00Z",
  "finished_at": "2026-06-22T05:30:42Z"
}
```

監査ログは `/shared/audit/YYYY-MM-DD.jsonl` に append-only：

```json
{"seq": 1, "task_id": "t-...", "event": "issued", "at": "...", "payload": {...}}
{"seq": 2, "task_id": "t-...", "event": "validated", "at": "...", "payload": {}}
{"seq": 3, "task_id": "t-...", "event": "spawned", "at": "...", "payload": {"worktree": "..."}}
{"seq": 4, "task_id": "t-...", "event": "completed", "at": "...", "payload": {"exit_code": 0}}
```

## 設定 (環境変数)

| Env | 既定 | 役割 |
| --- | --- | --- |
| `MAX_CONCURRENT_SUBAGENTS` | 4 | 同時起動上限 |
| `SUPERVISOR_REQUIRE_APPROVAL` | 0 | 1 で承認モード ON（stdin で y/n 待ち） |
| `SUPERVISOR_APPROVAL_TIMEOUT_SEC` | 60 | 承認待ちタイムアウト（reject） |
| `SUPERVISOR_POLL_MS` | 0 | inotify が動かない場合の poll 間隔 (ms)。0 で inotify |
| `SUPERVISOR_LOG_LEVEL` | INFO | python logging のレベル |

## policy.yml の編集

新しい MCP やイメージを許可する場合は `policy.yml` を編集して supervisor を再起動：

```bash
docker compose -f tools/agent-sandbox/compose.yml restart supervisor
```

**注意**：`allowed_image` を緩める、`allowed_request_fields` を追加する、`forbidden_*` を削る、いずれも **隔離設計を弱める** 変更。レビュー必須（ADR 0003 / 0004 の方針を再確認すること）。

## supervisor 自身のセキュリティ

supervisor は **`docker.sock` をマウントしている** ため、乗っ取られればホスト root と同等の権限を取られる。緩和策：

1. supervisor のコード変更は必ずレビュー
2. policy.yml は allowlist 方式（明示許可のみ）
3. 親コンテナから supervisor のネットワーク / FS にいかなる経路でも到達できない設計を維持
4. 将来 Sysbox 経由の rootless supervisor に差し替え可能な構造を保つ

## トラブルシュート

| 症状 | 原因 / 対策 |
| --- | --- |
| request を書いても reactions しない | inotify が動いていない可能性。`SUPERVISOR_POLL_MS=1000` で fallback 起動 |
| `worktree already exists` | 既存 task_id と衝突。`tools/agent-sandbox/shared/worktrees/<task_id>/` を手動削除＋`git worktree prune` |
| 子コンテナが build 未済 | `docker compose -f tools/agent-sandbox/compose.yml build agent` を先に実施 |
| `permission denied` for /shared/... | supervisor の chown が効いていない。コンテナを `--user root` で再起動 |
