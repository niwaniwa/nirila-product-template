---
id: "0002"
title: "agent-sandbox: Docker Compose による隔離実行環境"
status: accepted
phase: mvp
created: 2026-06-22
updated: 2026-06-22
related_adr: ["0003"]
---

# agent-sandbox: Docker Compose による隔離実行環境

## 概要

Claude Code CLI（および将来的に Codex などの汎用エージェント CLI）を **ホストから物理的に隔離** された Docker コンテナで実行するための Compose ベース最小実装。本リポジトリの `tools/agent-sandbox/` に配置し、`docker compose run` の 1 コマンドで起動可能とする。

## 背景・ADR参照

- [ADR 0003: エージェント実行は Docker Compose で隔離する](../adr/0003-agent-execution-docker-isolation.md)（accepted）

ADR 0003 が定めた「標準 runc + egress proxy + 二層ネットワーク + 最小権限プロファイル」の方針を、実ファイルに落とす。

サブエージェント起動方式（ADR 0004）、observability sidecar（ADR 0005）、GUI 連携（ADR 0006）は **本 spec のスコープ外** とし、後続 spec で扱う。これは「最初の最小骨格」を確実に動かしてから増築する戦略。

## 要件

### 機能要件

- **MUST**:
  - 単一コマンド `docker compose -f tools/agent-sandbox/compose.yml run --rm agent ...` で Claude Code CLI が起動する
  - agent コンテナは `internal: true` ネットワークにのみ接続され、Squid 経由でしか外部通信できない
  - allowlist は `proxy/squid.conf` に集約され、編集すれば反映される
  - workspace は環境変数 `WORKSPACE` で指定したホストディレクトリのみがマウントされる
  - `~/.claude` は名前付き volume で永続化され、ホスト `~/.claude` には触れない
  - agent コンテナは non-root（UID 1000）、`cap_drop: ALL`、`read_only: true`、`no-new-privileges` で起動する
- **SHOULD**:
  - `compose.override.example.yml` を同梱し、個人カスタマイズ用の出発点を提示する
  - Claude Code CLI のバージョンを `CLAUDE_CODE_VERSION` build arg で pin 可能とする
  - 個人開発者向けに `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` および `DISABLE_AUTOUPDATER=1` を既定 ON とする
- **COULD**:
  - Squid のアクセスログを stdout に出し、`docker compose logs egress-proxy` で監査可能とする

### 非機能要件

- **パフォーマンス**：エフェメラル起動（`run --rm`）が 5 秒以内に CLI プロンプトに到達する。
- **セキュリティ**：
  - ホストの `~/.ssh` / `~/.aws` / `~/.gnupg` / `~/.docker` / `~/.kube` などのシークレット格納先は **マウント禁止**を README で明示。
  - `--privileged` / `docker.sock` マウントは禁止（ADR 0003/0004 と整合）。
  - 失敗時は fail-closed（allowlist 外通信は黙って通さない）。

## スコープ

### このフェーズで対応するもの

- `compose.yml`：egress-proxy + agent の 2 サービス、二層ネットワーク
- `Dockerfile.agent`：node:22-slim ベース、claude CLI 同梱、UID 1000 ユーザ
- `proxy/squid.conf`：最小 allowlist（Anthropic API / GitHub / npm registry）
- `compose.override.example.yml`：個人カスタマイズ雛形
- `README.md`：使い方、セキュリティ前提、allowlist 拡張手順
- `.gitignore` の更新：`compose.override.yml` を除外
- 受け入れテスト手順の手動実行

### 対応しないもの（後続フェーズ）

- サブエージェント supervisor（ADR 0004 の実装 = 後続 spec）
- Observability sidecar（ADR 0005 の実装 = 後続 spec）
- GUI ツール（Nimbalyst）の launch-cmd 連携（ADR 0006 の実装 = 後続 spec）
- credential-injecting proxy（env 注入から始める。proxy 化は後続 ADR / spec で）
- gVisor / microVM ランタイム差し替え（untrusted コード対応時の別 ADR）
- macOS Docker Desktop 固有の互換性追補

## 技術設計

### ディレクトリ構成

```
tools/agent-sandbox/
├── compose.yml
├── compose.override.example.yml
├── Dockerfile.agent
├── proxy/
│   └── squid.conf
└── README.md
```

### サービス構成

```
┌──── ホスト ─────────────────────────────────────────┐
│                                                     │
│  $WORKSPACE  ──── bind mount ───┐                   │
│                                 ▼                   │
│  ┌─────────────────────────────────────────────┐    │
│  │ network: isolated (internal: true)          │    │
│  │  ┌─────────────┐       ┌────────────────┐   │    │
│  │  │ agent       │──────▶│ egress-proxy   │   │    │
│  │  │ (claude)    │ HTTP  │ (Squid)        │   │    │
│  │  │ UID 1000    │ PROXY │                │   │    │
│  │  │ cap_drop    │       │                │   │    │
│  │  │ read_only   │       │                │   │    │
│  │  └─────────────┘       └────────┬───────┘   │    │
│  └─────────────────────────────────│───────────┘    │
│                                    │ allowlist      │
│  ┌─────────────────────────────────│───────────┐    │
│  │ network: internet (bridge)      ▼           │    │
│  │                          api.anthropic.com  │    │
│  │                          github.com, npm    │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### Compose プロファイル

- `egress-proxy` はプロファイルなし → `docker compose up -d egress-proxy` で常駐
- `agent` は `profiles: [run]` → 明示起動でのみ立つ（`docker compose run --rm agent ...`）

### 環境変数の役割

| 変数 | 必須 | 役割 |
| --- | --- | --- |
| `WORKSPACE` | はい | ホスト側マウント元（絶対パス推奨） |
| `ANTHROPIC_API_KEY` | はい（OAuth 未使用時）| agent コンテナへ env で注入 |
| `CLAUDE_CODE_VERSION` | いいえ（既定 `latest`）| `Dockerfile.agent` の build arg、CLI 版固定用 |
| `WORKSPACE_NAME` | いいえ | コンテナ名衝突回避 / 将来の observability service.name 用 |

### Squid allowlist（初期セット）

- `api.anthropic.com`（推論）
- `console.anthropic.com`（OAuth）
- `registry.npmjs.org`（CLI auto update を残す場合のみ。既定では `DISABLE_AUTOUPDATER=1`）
- `.github.com`, `.githubusercontent.com`, `codeload.github.com`（git / GitHub API）

MCP サーバを追加する際は README の手順に従い squid.conf の `acl allowed_sites` 行を追加する。

### Dockerfile 設計

- base image：`node:22-slim`（OS パッケージ最小、npm 同梱）
- 追加：`ca-certificates`, `curl`, `git`, `less`, `procps`（最低限）
- npm install で `@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}`
- `node` ユーザ（UID 1000）を `agent` にリネームし、ホームを `/home/agent` に移す
- `ENTRYPOINT ["claude"]`、`WORKDIR /workspace`

### 拒否設定

- `--privileged` 禁止：compose ファイルに記述しない
- `docker.sock` マウント禁止：volumes に絶対書かない（後続 ADR 0004 でも同方針）

## 受け入れ基準

- [ ] `WORKSPACE=$(pwd) docker compose -f tools/agent-sandbox/compose.yml run --rm agent -p "echo hello"` が成功する
- [ ] `docker compose -f tools/agent-sandbox/compose.yml run --rm --entrypoint sh agent -c "curl -sS -o /dev/null -w '%{http_code}\n' https://example.com"` が **接続失敗** を返す（allowlist 外）
- [ ] 同コマンドで `https://api.anthropic.com` は **200/4xx 系の応答** を返す（接続自体は成立）
- [ ] `docker compose ... run --rm --entrypoint sh agent -c "id"` が `uid=1000(agent)` を返す
- [ ] `docker compose ... run --rm --entrypoint sh agent -c "capsh --print | grep 'Current:'"` が `Current: =` または空 cap セットを返す
- [ ] `docker compose ... run --rm --entrypoint sh agent -c "touch /sbin/x"` が EROFS で失敗する
- [ ] `docker compose ... run --rm --entrypoint sh agent -c "ls /etc/shadow"` が読み取り失敗または "Permission denied" を返す
- [ ] `bash scripts/validate-docs.sh` がエラー 0 で通る
- [ ] README に「マウント禁止リスト」「allowlist 拡張手順」「`--dangerously-skip-permissions` 注意事項」が記載されている

## 未解決事項

- Squid のキャッシュを完全 off にして問題ないか（CI 連続実行時のスループット）
- `WORKSPACE` を絶対パス前提とするか、相対パスも許容するか（後者は分かりにくいバグの温床のため絶対パス必須を README で明示する方向）
