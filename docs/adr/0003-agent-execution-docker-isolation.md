---
id: "0003"
title: "エージェント実行は Docker Compose で隔離する"
status: accepted
created: 2026-06-21
updated: 2026-06-22
decision_owner: "プロジェクトリーダー"
---

# エージェント実行は Docker Compose で隔離する

## コンテキスト

本テンプレートを使うプロジェクトでは Claude Code（CLI）や Claude Agent SDK を介して **対話的に shell コマンドを実行する長寿命プロセス** が走る。`Bash` ツール経由でホストの任意ファイル・任意コマンドにアクセスでき、`--dangerously-skip-permissions` を併用すれば権限プロンプトも外せる。

[research/0003](../research/0003-docker-isolation-for-agents.md) で確認した通り、Anthropic 自身が「dev container の保護は完全ではない。悪意あるリポジトリは認証情報を含めて吐き出しうる」と明示しており、エージェントを **ホストから物理的に隔離** する仕組みをテンプレートで提供する必要がある。

要件：

- ファイルシステム / ネットワーク / 実行権限 / シークレットの 4 軸で多層防御
- 個人開発者でも追加インストール最小で導入可能
- 将来 untrusted コードを扱う段階で **強い隔離（gVisor / microVM）へ差し替え可能** な構造

## 検討した選択肢

### 選択肢 A: Docker Compose + egress proxy（標準 runc）

- 利点:
  - 個人開発者の標準環境（Docker Desktop / Docker Engine）でそのまま動く
  - Anthropic 公式 reference devcontainer / Docker Sandboxes / 各種 OSS 実装と整合
  - egress proxy + `internal: true` ネットワークで fail-closed のネットワーク隔離が可能
  - `cap_drop: ALL` / `read_only: true` / non-root を維持可能
- 欠点:
  - カーネル共有のため、untrusted コードへの kernel exploit には弱い
  - 設定項目が多く、初学者には学習コストあり

### 選択肢 B: Sandbox runtime（bubblewrap / sandbox-exec）

- 利点:
  - OS プリミティブのみで Docker 不要、起動が速い
  - Anthropic 公式の `@anthropic-ai/sandbox-runtime` が利用可能
- 欠点:
  - macOS / Linux で挙動差が大きく、テンプレート化しづらい
  - 「サブエージェントを別環境で起動」が compose のような宣言的記述に乗せにくい
  - チーム間で再現性を担保しづらい

### 選択肢 C: gVisor / Firecracker microVM をデフォルト採用

- 利点:
  - カーネル隔離まで含む最強の隔離
  - untrusted コードでも安全に動かせる
- 欠点:
  - ランタイム導入コストが高い（gVisor は専用 runc、Firecracker は専用 hypervisor）
  - 多くの開発環境（特に macOS Docker Desktop）で動作制約あり
  - 個人開発者の "デフォルト" としては過剰

## 決定

**選択肢 A: Docker Compose + egress proxy（標準 runc）** を採用する。

### 構成方針

- **二層ネットワーク**：agent コンテナは `internal: true` のネットワークのみ接続。egress proxy（Squid / Envoy）を `internal` + bridge 両方に置き、allowlist を強制する fail-closed 構造。
- **最小権限プロファイル**：
  ```
  user: 1000:1000
  read_only: true
  cap_drop: [ALL]
  security_opt:
    - no-new-privileges:true
  tmpfs: [/tmp, /home/agent/tmp]
  pids_limit: 200
  mem_limit: 4g
  ```
- **マウント原則**：プロジェクトの workspace のみ。**ホストの `~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.config`, `~/.docker/config.json`, `~/.kube/config` は決してマウントしない**。`~/.claude` は名前付き volume で永続化。
- **シークレット注入**：env から開始可能、将来的に credential-injecting proxy（`ANTHROPIC_BASE_URL` を proxy に向ける）に差し替えられる構造をデフォルトとする。
- **ランタイム非依存**：将来 `runtime: runsc`（gVisor）や Docker Sandboxes（microVM）に切替可能な記述に保つ。差し替え時は本 ADR を上書きせず、別 ADR で改定する。

### 提供物（[spec で詳細化予定]）

```
tools/agent-sandbox/
├── compose.yml
├── compose.override.example.yml
├── Dockerfile.agent
├── proxy/squid.conf            # allowlist 初期セット
└── README.md
```

## 影響

- 正：個人開発者・チームのいずれでも、追加のランタイム導入なしに「ホスト隔離された agent 実行環境」が `docker compose run agent ...` だけで使えるようになる。
- 正：Anthropic 内蔵 OTel と組み合わせ可能（[ADR 0005](./0005-observability-stack-langfuse.md) で観測スタックを別途決定）。
- 正：将来の隔離強化（gVisor / microVM）は **同じ compose 構造のまま runtime 差し替え** で対応可能。
- 負：個人開発者が直に `claude` を叩く構成と比較して、CPU・メモリオーバヘッドと起動時間が増える。
- 負：MCP サーバを追加するたびに allowlist 更新が必要。
- リスク：untrusted リポジトリを `--dangerously-skip-permissions` で扱う場合、コンテナ内の `~/.claude` 認証情報は依然として盗難可能。README で明示し、untrusted コード対応時は別 ADR で強い隔離（gVisor / microVM）へ移行する。

## 参考

- [research/0003: AIエージェントをDockerコンテナに閉じ込めるための手法調査](../research/0003-docker-isolation-for-agents.md)
- [ADR 0004: サブエージェント起動方式](./0004-subagent-execution-pattern.md)
- [ADR 0005: Observability 既定スタック](./0005-observability-stack-langfuse.md)
- [Anthropic Securely deploying AI agents](https://code.claude.com/docs/en/agent-sdk/secure-deployment)
- [Anthropic Development containers](https://code.claude.com/docs/en/devcontainer)
