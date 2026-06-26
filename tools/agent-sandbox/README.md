# agent-sandbox

Claude Code CLI を **ホストから隔離された Docker コンテナ** で実行するための最小 Compose セット。

- 根拠: [ADR 0003](../../docs/adr/0003-agent-execution-docker-isolation.md) / [spec 0002](../../docs/spec/0002-agent-sandbox-compose.md)
- サブエージェント: [ADR 0004](../../docs/adr/0004-subagent-execution-pattern.md) / [spec 0003](../../docs/spec/0003-subagent-supervisor.md)
- 関連: [research 0003](../../docs/research/0003-docker-isolation-for-agents.md)

## なにを隔離するか

| 隔離軸 | 実装 |
| --- | --- |
| ファイルシステム | `read_only: true` + `tmpfs` + `WORKSPACE` のみマウント |
| ネットワーク | `internal: true` の隔離ネットに閉じ込め、Squid 経由でのみ外部到達 |
| 実行権限 | UID 1000 / `cap_drop: ALL` / `no-new-privileges` / `pids_limit` |
| シークレット | ホスト `~/.claude` を **触らない**。`~/.claude` は名前付き volume で永続化 |

## 前提

- Docker Engine 24+ または Docker Desktop（Compose v2 を含むもの）
- `ANTHROPIC_API_KEY` を環境変数で持っている、または初回サインインを実施する
- マウントするワークスペースは **絶対パス** で指定する（相対パスは不可）

## 使い方

### 1. 初回ビルド（任意。`run` 時に自動ビルドされる）

```bash
docker compose -f tools/agent-sandbox/compose.yml build agent
```

### 2. egress-proxy を起動（常駐）

```bash
docker compose -f tools/agent-sandbox/compose.yml up -d egress-proxy
```

### 3. agent をエフェメラル実行

```bash
WORKSPACE="$(git rev-parse --show-toplevel)" \
  docker compose -f tools/agent-sandbox/compose.yml \
  run --rm agent -p "list the files in this directory"
```

引数（`-p "..."`）はそのまま `claude` CLI に渡る。インタラクティブに使う場合は引数なしで `run --rm agent` を実行する。

### 4. 個別カスタマイズ

```bash
cp tools/agent-sandbox/compose.override.example.yml tools/agent-sandbox/compose.override.yml
# 編集
WORKSPACE="$(git rev-parse --show-toplevel)" \
  docker compose -f tools/agent-sandbox/compose.yml \
                 -f tools/agent-sandbox/compose.override.yml \
                 run --rm agent
```

`compose.override.yml` は `.gitignore` 対象。

## 初回ログイン

Claude Code の認証は **コンテナ内で 1 回だけ OAuth サインイン** を実施するのが既定。credentials は `claude-config` という名前付き volume に保存され、以降の `run --rm` でも、サブエージェント（[ADR 0004](../../docs/adr/0004-subagent-execution-pattern.md)）の子コンテナでも、同じ subscription が透過的に再利用される。

### 手順

```bash
# 1. egress-proxy を先に起動しておく
WORKSPACE="$(git rev-parse --show-toplevel)" \
  docker compose -f tools/agent-sandbox/compose.yml up -d egress-proxy

# 2. interactive モードで agent を起動 (引数なし)
WORKSPACE="$(git rev-parse --show-toplevel)" \
  docker compose -f tools/agent-sandbox/compose.yml run --rm agent

# 3. プロンプトで "/login" を実行
# 4. 表示された URL をホストのブラウザで開く
# 5. Anthropic アカウントで承認 → ブラウザに表示されるコードを取得
# 6. コードをコンテナのプロンプトに貼り付け
# 7. /exit で抜ける
```

以降、`run --rm agent ...` するだけで認証済みの状態で起動する。

### 認証経路の比較

| 経路 | 課金 | 設定 | 用途 |
| --- | --- | --- | --- |
| **`/login` (OAuth)** ✅ 既定 | **subscription** (Pro / Max / Team の枠を消費) | コンテナ内 1 回。`claude-config` volume に永続 | 個人開発・チーム開発（推奨） |
| `ANTHROPIC_API_KEY` env | **従量課金** (API 単価) | `.env` で渡す or shell から export | API 課金にしたい / 組織キーがある場合のみ |
| `claude setup-token` / `CLAUDE_CODE_OAUTH_TOKEN` | **従量課金** (subscription にならない) | env で渡す | ⚠️ 本テンプレートでは **使わない** ことを推奨 |

`CLAUDE_CODE_OAUTH_TOKEN` 経路は実体が API 課金になるため、subscription を活かしたい場合は OAuth (`/login`) を選ぶ。compose.yml は `CLAUDE_CODE_OAUTH_TOKEN` を env に通していないので、ホスト側に export してあっても agent コンテナには届かない（誤設定保護）。

### credentials の保護

- **`docker compose down -v` は禁止**（運用時）。`-v` は名前付き volume を消すため、`claude-config` ごと credentials が失われる。普段は `docker compose down` のみを使う。
- 受け入れテストや完全リセット時のみ `-v` を付ける。再ログインが必要になる。
- ホストの `~/.claude` は **マウントしない**（[ADR 0003](../../docs/adr/0003-agent-execution-docker-isolation.md) の方針）。コンテナ内 volume の credentials はホストとは独立に管理される。

### サブエージェントへの伝播

[supervisor](./supervisor/README.md) が `docker compose run --rm agent ...` で子コンテナを起こす際、同じ `claude-config` volume を mount するので、**親で 1 度ログインすれば子も同じ subscription で動く**。子のために追加ログインは不要。

## 受け入れテスト

すべて成功すれば隔離が機能している：

```bash
# 1. 非 allowlist ドメインへの到達失敗（fail-closed 確認）
WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml \
  run --rm --entrypoint sh agent -c \
  "curl -sS -o /dev/null -w '%{http_code}\n' --max-time 5 https://example.com" \
  ; echo "↑ 接続失敗または非 2xx ならOK"

# 2. Anthropic API への接続成立（403 等でも到達はしている）
WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml \
  run --rm --entrypoint sh agent -c \
  "curl -sS -o /dev/null -w '%{http_code}\n' --max-time 5 https://api.anthropic.com/v1/models" \
  ; echo "↑ 4xx 系であれば OK（401/403 等）"

# 3. UID 確認
WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml \
  run --rm --entrypoint sh agent -c "id"
# uid=1000(agent) gid=1000(agent) であること

# 4. cap が空
WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml \
  run --rm --entrypoint sh agent -c "capsh --print | head -3"
# "Current: =" または空 cap であること

# 5. root FS への書き込み失敗
WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml \
  run --rm --entrypoint sh agent -c "touch /sbin/x 2>&1"
# "Read-only file system" であること
```

## セキュリティ前提（重要）

### マウント禁止リスト

以下のホストパスは **絶対にマウントしないこと**。`compose.override.yml` でも同様：

| ホストパス | 含むもの |
| --- | --- |
| `~/.ssh` | SSH 秘密鍵 |
| `~/.aws` | AWS クレデンシャル |
| `~/.gnupg` | GPG 秘密鍵 |
| `~/.docker/config.json` | Docker レジストリトークン |
| `~/.kube/config` | Kubernetes クラスタ認証 |
| `~/.config/gcloud` | Google Cloud ADC |
| `~/.azure` | Azure CLI |
| `.env`, `.env.local` を含むディレクトリ | API キー |

### `--dangerously-skip-permissions` について

`claude --dangerously-skip-permissions` を使う場合でも、**信頼できないリポジトリでは使わないこと**。Anthropic 公式が明示している通り、隔離されたコンテナ内でも `~/.claude` の認証情報は盗難可能。

### 禁止事項（このリポジトリの方針）

- `--privileged` の付与
- `docker.sock` のマウント
- `cap_drop` の解除
- `read_only` の無効化

これらが必要な場合は ADR を更新してから行う。

## サブエージェント呼び出し

親 agent コンテナの中から、別コンテナで動くサブエージェントを **autonomous に** 起動する経路。詳細仕様は [supervisor/README.md](./supervisor/README.md) を参照。

### 経路概要

```
親 agent (container, cap_drop ALL)
  │
  │  /shared/requests/<task_id>.json を書く
  ▼
共有 volume
  │  inotify
  ▼
supervisor (host 側 container, docker.sock 保有)
  │
  │  policy 検証 → git worktree add → docker compose run
  ▼
子 agent (container, 親と同じ隔離プロファイル)
```

親は **docker と話さない**。supervisor だけが docker daemon と話す。

### 使い方

```bash
# 1. supervisor を起動 (常駐)
WORKSPACE="$(git rev-parse --show-toplevel)" \
  docker compose -f tools/agent-sandbox/compose.yml \
  up -d supervisor egress-proxy

# 2. 親 agent から SPAWN_REQUEST を書く
WORKSPACE="$(git rev-parse --show-toplevel)" \
  docker compose -f tools/agent-sandbox/compose.yml \
  run --rm --entrypoint sh agent -c \
  'echo "{\"task_id\":\"t-1\",\"prompt\":\"echo hello from subagent\"}" \
     > /shared/requests/t-1.json; \
   for i in 1 2 3 4 5 6 7 8 9 10; do \
     test -f /shared/results/t-1.json && break; sleep 1; \
   done; \
   cat /shared/results/t-1.json'
```

### policy

許可 image / 許可フィールド / 禁止 env / 禁止 volume は [supervisor/policy.yml](./supervisor/policy.yml) に集約。編集時は **隔離を弱める方向の変更** に注意。

### approval mode の有効化

high-stakes な操作だけ人間ゲートにしたい場合：

```bash
WORKSPACE="$(git rev-parse --show-toplevel)" \
  SUPERVISOR_REQUIRE_APPROVAL=1 \
  docker compose -f tools/agent-sandbox/compose.yml up -d supervisor
docker compose -f tools/agent-sandbox/compose.yml attach supervisor
# request が来ると "[supervisor] approve task 'xxx'? (y/n)" が出るので入力
```

### 監査ログ

`tools/agent-sandbox/shared/audit/YYYY-MM-DD.jsonl` に append-only。`issued / validated / spawned / completed / rejected` イベントが seq 順に記録される。

```bash
jq -c . tools/agent-sandbox/shared/audit/*.jsonl
```

## GUI 連携（Nimbalyst）

[Nimbalyst](https://github.com/stravu/crystal)（旧 Crystal）の launch-cmd 経路を agent-sandbox の隔離コンテナに通すための wrapper を `scripts/run-via-nimbalyst.sh` に同梱。

- 根拠: [ADR 0006](../../docs/adr/0006-orchestration-gui-nimbalyst.md) / [spec 0005](../../docs/spec/0005-nimbalyst-integration.md)

### セットアップ

1. **Nimbalyst のインストール**：[公式リポジトリ](https://github.com/stravu/crystal) の手順に従う。本テンプレ側ではインストール自動化はしない。
2. **wrapper を実行可能に**（リポジトリ clone 直後にやる）：

   ```bash
   chmod +x tools/agent-sandbox/scripts/run-via-nimbalyst.sh
   ```

3. **Nimbalyst の Settings → Launch Command** に wrapper の絶対パスを設定：

   ```text
   /absolute/path/to/your-repo/tools/agent-sandbox/scripts/run-via-nimbalyst.sh {{worktree}}
   ```

   `{{worktree}}` は Nimbalyst が解決する worktree パスのプレースホルダ。**Nimbalyst の最新リリースでプレースホルダ仕様を確認**すること（バージョンで変わりうる）。

### 追加の compose override を重ねたい場合

`EXTRA_COMPOSE_FILES` 環境変数で `-f` を追加できる：

```text
EXTRA_COMPOSE_FILES="-f /absolute/path/to/some-override.yml" \
  /absolute/path/.../run-via-nimbalyst.sh {{worktree}}
```

### sub-agent supervisor と並走

[supervisor](./supervisor/README.md) を別途常駐させておけば、Nimbalyst から起動された各 agent も `/shared/requests/*.json` を書ける。supervisor 側で固定テンプレで子コンテナを起こすので、隔離設計は崩れない。

### wrapper のふるまい

| 引数 | 結果 | exit code |
| --- | --- | --- |
| なし | `usage: ...` を stderr に出して終了 | 1 |
| 不正な path | `ERROR: worktree path not found: ...` | 2 |
| 正常 worktree | `WORKSPACE=$worktree docker compose -f .../compose.yml run --rm agent "$@"` を `exec` | docker compose の終了コード |

wrapper 自身は **追加権限を要求しない**。`--privileged` / `docker.sock` を新たにマウントすることもない。ADR 0003 / 0004 の隔離プロファイルは compose 側で固定されているため、wrapper 経路でも一切緩まない。

### トラブルシュート

| 症状 | 原因 / 対策 |
| --- | --- |
| `compose file not found at ...` | worktree が agent-sandbox を含むリポジトリの外。`compose.yml` の場所を `EXTRA_COMPOSE_FILES` 等で明示 |
| Nimbalyst からの起動だけ docker 権限エラー | Nimbalyst を起動しているユーザが docker グループに属しているか確認 |
| OAuth がない状態で起動して fail | 一度ターミナルから `docker compose ... run --rm agent` で `/login` を済ませる（[初回ログイン](#初回ログイン)節） |
| Conductor / Claudia でも使いたい | 同じ wrapper を流用可能。各 GUI の launch-cmd 仕様に合わせ引数の渡し方だけ調整 |

## allowlist の拡張

新しい MCP サーバや外部 API を使う場合、`proxy/squid.conf` の Allowlist セクションに `acl allowed_sites dstdomain <domain>` を追記する。

注意：

- `.example.com` と `api.example.com` のように **同じドメイン階層を重ねて書かない**（Squid が起動失敗する既知 quirk）
- 追記後は `docker compose ... restart egress-proxy` で反映

## トラブルシュート

| 症状 | 原因 / 対策 |
| --- | --- |
| `WORKSPACE must be set ...` で起動失敗 | env `WORKSPACE` を絶対パスで設定する |
| `Permission denied: /workspace` | ホスト側 workspace のオーナーが UID 1000 でない。`chown -R 1000:1000` するか、`compose.override.yml` で `user:` を上書き |
| Squid が起動しない | `squid.conf` の dstdomain 重複を確認 |
| `ANTHROPIC_API_KEY` が空で起動 | OAuth サインインを `docker compose ... run --rm agent` のインタラクティブモードで実施するか、env を設定 |
| Docker Desktop on macOS で遅い | bind mount の同期コスト。`:delegated` フラグを override で追加 |

## 既知の制約

- サブエージェント並列起動は [supervisor/](./supervisor/) を参照（ADR 0004 / spec 0003）。
- observability スタックは MVP では同梱しない（ADR 0005 / spec 0004 ともに archive 化済）。再導入は別 ADR で。
- macOS Docker Desktop 環境では `userns-remap` の動作が Linux と異なる可能性。
