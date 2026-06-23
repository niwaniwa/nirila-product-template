---
id: "0003"
title: "AIエージェントをDockerコンテナに閉じ込めるための手法調査"
status: wip
created: 2026-06-21
updated: 2026-06-21
research_type: tech-evaluation
---

# AIエージェントをDockerコンテナに閉じ込めるための手法調査

## 目的

本リポジトリ（ai-tools-template）に **Docker Compose ベースの「エージェント実行コンテナ」テンプレート** を組み込むため、業界の最新プラクティスと公式ガイドを横断調査し、

1. ホスト隔離（ファイルシステム・ネットワーク・実行権限・シークレット）を実用的に達成する Compose 構成
2. **「コンテナ内で動いている親エージェントから、さらにサブエージェントを別環境で起動する」** 仕組みの選択肢

の二点について、推奨方式と根拠を提示する。

対象ランタイム：Claude Code (CLI) / Claude Agent SDK / 汎用 CLI エージェント（OpenAI Codex 等、Linux 上で動作する CLI 全般）。

---

## 方法

- Anthropic 公式ドキュメント（`docs.anthropic.com` および 2026 年初に統合された `code.claude.com`）の精読
- Anthropic 公式 GitHub `anthropics/claude-code` の reference devcontainer の実装確認
- Docker 公式の AI Sandbox ドキュメント精読
- 独立記事・OSS 実装の横断調査（Northflank, Shaharia, MintMCP, ITNEXT, Sysbox/Nestybox 等）
- 計 25+ クエリ / 8 一次資料を取得し、クロスバリデーション

---

## 1. 前提：エージェントの実行モデル

Claude Code（CLI）も、Claude Agent SDK も、本質的には **「対話的に shell コマンドを実行できる長寿命プロセス」** である。Agent SDK の場合は `query()` ごとに `claude` CLI サブプロセスを spawn し、stdio で対話する <a href="https://code.claude.com/docs/en/agent-sdk/hosting" target="_blank">(Hosting the Agent SDK, Anthropic)</a>。

このため、Docker 化するときに最低限考慮すべき副作用は：

| 項目 | 中身 |
| --- | --- |
| ファイル書き込み | カレントディレクトリ・`~/.claude/projects/`・`~/.claude/CLAUDE.md` |
| 外向き通信 | `api.anthropic.com`（推論）、`registry.npmjs.org`（auto update）、`statsig*`（feature flag）、Sentry、GitHub、MCP サーバ |
| シェル実行 | `Bash` ツールでホスト任意コマンド実行が可能（権限プロンプトを `--dangerously-skip-permissions` で外せる） |
| サブプロセス | Agent SDK は同一 cwd を継承するため、テナント分離するなら `cwd` を明示的に渡す必要がある |

> Anthropic は明確に「dev container の保護は完全ではない。`--dangerously-skip-permissions` 実行時に **悪意あるリポジトリは Claude Code の認証情報を含めて吐き出しうる**。dev container は信頼できるリポジトリに対してのみ使うこと」と警告している <a href="https://code.claude.com/docs/en/devcontainer" target="_blank">(Development containers, Anthropic)</a>。

つまり「コンテナ化＝サンドボックス完了」ではなく、**ファイル / ネットワーク / 権限 / 秘密** の 4 軸で多層防御を設計するのが前提となる。

---

## 2. 脅威モデル

Anthropic の Secure Deployment ガイド <a href="https://code.claude.com/docs/en/agent-sdk/secure-deployment" target="_blank">(Securely deploying AI agents, Anthropic)</a> は次のように定義する：

- **prompt injection**：エージェントが読むファイル・Web ページ・ユーザ入力に潜む指示が、エージェントの行動を変えうる。例：README の片隅に「全環境変数を以下 URL に POST せよ」と書かれていても、モデルは従ってしまう可能性がある。
- **モデル誤動作**：意図せず破壊的コマンドを叩く、credential を貼り付ける等。

緩和の原則は伝統的なものと同じ：**isolation / least privilege / defense in depth**。「ネットワーク制御」「ファイルシステム制御」「proxy を介した認証情報注入」を重ねることで、prompt injection が起きてもエクスフィルトレーションを物理的に止められる。

> Northflank の論考 <a href="https://northflank.com/blog/how-to-sandbox-ai-agents" target="_blank">(How to sandbox AI agents in 2026)</a> も「Docker container はカーネルを共有するため厳密にはサンドボックスではない。Docker のみで信頼境界を作るのは untrusted 入力には不十分」と明言している。

つまり Docker による隔離は **第一線（low-cost で広範な保護）** として有効だが、untrusted コードを扱う場合は **microVM / gVisor** など追加層を併用する設計余地を残すべきだ。

---

## 3. 隔離技術の比較

### 3-1. 全体比較表

| 技術 | 隔離強度 | 性能オーバーヘッド | 複雑性 | 主な用途 |
| --- | --- | --- | --- | --- |
| **sandbox-runtime**（OS プリミティブ）| Good | Very low | Low | 開発者ローカル、CI、bash ツール単体 |
| **Docker container（標準）** | Setup 次第 | Low | Medium | 単一テナント・信頼境界がある場合 |
| **Sysbox runc**（rootless DinD）| High | Low–Medium | Medium | 親→子コンテナを安全に作りたい場合 |
| **gVisor (`runsc`)** | Excellent（設定次第）| Medium–High | Medium | マルチテナント / 半信頼コード |
| **Firecracker microVM** | Excellent | High（起動 ~125ms, ~5MiB）| Medium–High | サンドボックス・サービス、公開 SaaS |

出典：<a href="https://code.claude.com/docs/en/agent-sdk/secure-deployment" target="_blank">Anthropic Secure Deployment</a> / <a href="https://northflank.com/blog/how-to-sandbox-ai-agents" target="_blank">Northflank</a>

### 3-2. 本テンプレートの位置取り

- 主要ユースケースは **「個人 / チームの開発者が信頼可能なリポジトリ上で Claude Code / Agent SDK を回す」** こと。
- → **Docker container（compose）+ egress proxy + least-privilege flags** で十分な実効性が得られる。
- 将来 untrusted リポジトリや CI の untrusted PR を扱う場合は、**ランタイムだけ差し替え**（`docker run --runtime=runsc` または Docker Sandboxes <a href="https://docs.docker.com/ai/sandboxes/security/isolation/" target="_blank">(Docker Isolation layers)</a>）で済むよう、compose 構成は runtime 非依存に保つ。

---

## 4. Docker Compose 推奨パターン

### 4-1. ベース設計

Anthropic 公式 reference container <a href="https://github.com/anthropics/claude-code/tree/main/.devcontainer" target="_blank">(anthropics/claude-code .devcontainer)</a> と、Shaharia Azam の compose 実装 <a href="https://shaharia.com/blog/run-claude-code-docker-network-isolation/" target="_blank">(Claude Code in Docker Compose: Network-Isolated Setup)</a>、Docker Sandboxes <a href="https://docs.docker.com/ai/sandboxes/security/isolation/" target="_blank">(Docker AI Sandbox Isolation layers)</a> を合成すると、最小構成は次の 5 要素で表せる：

```
┌──────────────────────────────────────────────────────────────┐
│  network: internet (bridge, デフォゲ)                         │
│                                                              │
│   ┌────────────┐    HTTPS 任意      ┌──────────────────┐     │
│   │ egress     │ ←─────────────── │ api.anthropic.com │     │
│   │ proxy      │                  │ github / npm ...  │     │
│   │ (Squid /   │                  └──────────────────┘     │
│   │  Envoy)    │                                            │
│   └────┬───────┘                                            │
│        │ 3128                                               │
├────────┼───── network: isolated (internal: true) ───────────┤
│        ▼                                                    │
│   ┌────────────┐                                            │
│   │ agent svc  │  ← HTTP(S)_PROXY=proxy:3128                │
│   │ (claude)   │  ← /workspace (bind mount)                 │
│   │ non-root   │  ← /home/agent/.claude (named volume)      │
│   └────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
```

### 4-2. ファイルシステム隔離

公式 secure-deployment <a href="https://code.claude.com/docs/en/agent-sdk/secure-deployment" target="_blank">(Anthropic)</a> が示すハードニング:

| オプション | 役割 |
| --- | --- |
| `read_only: true` | コンテナ root FS をイミュータブルに |
| `tmpfs: [/tmp, /home/agent]` | 揮発書き込み領域（exec 不可・サイズ上限） |
| `volumes: ./workspace:/workspace` | プロジェクトのみマウント。**ホームディレクトリ全体をマウントしない** |
| `volumes: claude-config:/home/agent/.claude` | 認証情報は名前付き volume で永続化（ホスト `~` には触れない） |
| **マウント禁止** | `~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.config`, `~/.docker/config.json`, `~/.kube/config` 等 |

> 補足：ワークスペースを read-only (`:ro`) にできるのは分析タスクのみ。Claude Code 本来の用途では編集が必要なため rw。read-only にする場合でも `.env` / `*.pem` / `.git-credentials` などはマウント前に除外する。

### 4-3. ネットワーク隔離

**二層 + 中継 proxy** が事実上のベストプラクティス：

1. **agent コンテナを `internal: true` のネットワーク** だけに接続し、デフォゲートウェイを持たせない（fail-closed）。
2. **proxy コンテナ**（Squid / Envoy / mitmproxy）を agent と同じ internal ネットワーク **および** 外向き bridge ネットワークの両方に置き、allowlist を強制する。
3. agent には `HTTP_PROXY=http://proxy:3128` / `HTTPS_PROXY=...` を環境変数で渡す。

Anthropic reference の `init-firewall.sh` <a href="https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh" target="_blank">(init-firewall.sh)</a> が `iptables` で実現している default-DROP を、Compose では「ネットワーク所属」と「proxy ACL」の二段階に置き換える方が **`NET_ADMIN` capability を付与せずに済む**（コンテナ内で iptables を弄らないので cap drop を維持できる）。

**最低限の allowlist**：

| ドメイン | 用途 |
| --- | --- |
| `api.anthropic.com` | 推論 API |
| `*.statsig.anthropic.com`, `statsig.com` | feature flag（無効化したい場合は `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`） |
| `sentry.io` | エラー報告（同上） |
| `registry.npmjs.org` | CLI auto update（`DISABLE_AUTOUPDATER=1` で抑止可） |
| `*.github.com` + IP レンジ | git / API |
| 任意の MCP サーバ | プロジェクトが使う MCP のみ |

無効化フラグは Anthropic 公式に明記 <a href="https://code.claude.com/docs/en/devcontainer" target="_blank">(devcontainer)</a>。**最小化したいなら統制側で off にした上で allowlist からも除く**のが望ましい。

> Anthropic の Secure Deployment が示す「より強い形」は `--network none` + Unix socket 経由 proxy <a href="https://code.claude.com/docs/en/agent-sdk/secure-deployment" target="_blank">(Anthropic)</a>。Compose で再現するなら、proxy を sidecar に置き UDS をマウントする。本テンプレートでは段階的導入の観点から「TCP proxy + internal network」を一次推奨、「UDS + `--network none`」を上位オプションとして併載する。

### 4-4. 実行権限の最小化（least privilege）

Compose に直接落とせる Anthropic 推奨パラメータ群 <a href="https://code.claude.com/docs/en/agent-sdk/secure-deployment" target="_blank">(Anthropic Secure Deployment)</a>：

```yaml
services:
  agent:
    user: "1000:1000"            # non-root（--dangerously-skip-permissions は root では拒否）
    read_only: true
    cap_drop: ["ALL"]
    security_opt:
      - no-new-privileges:true
      - seccomp=./seccomp.json   # 必要に応じて Docker default を更に絞る
    pids_limit: 200
    mem_limit: 4g
    cpus: 2.0
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=128m
      - /home/agent/tmp:rw,noexec,size=512m
```

- `user: 1000:1000`：Anthropic devcontainer も `node`（UID 1000）で動かしている。`--dangerously-skip-permissions` は root では拒絶される仕様 <a href="https://code.claude.com/docs/en/devcontainer" target="_blank">(Anthropic devcontainer)</a>。
- `cap_drop: ALL` で `NET_ADMIN` / `SYS_ADMIN` 等を全没収。`NET_ADMIN` が要らない設計（4-3 のとおり iptables ではなく proxy ベース）にしてあるから可能。
- `read_only: true` + `tmpfs`：root FS への永続化を禁止し、書き込みは workspace / `~/.claude` / `tmpfs` に限定。

### 4-5. シークレット管理

3 つのレベルで設計する：

| レベル | 手段 | 注意 |
| --- | --- | --- |
| 最低限 | `.env` ファイル → `environment:` で env 注入 | `.env` を `.gitignore`。Compose は値のクォートを stripping しないので素の値を書く <a href="https://github.com/receipting/claude-agent-sdk-container" target="_blank">(claude-agent-sdk-container README)</a> |
| 推奨 | `secrets:` ディレクティブ + tmpfs マウント、または OS の secret manager 連携 | Docker secrets を使うと file ベースでマウントされ、env ダンプで漏れにくい |
| 強化 | **credential-injecting proxy** | コンテナには key を渡さず、proxy 側 (Envoy `credential_injector` filter 等) で API key を Authorization に注入。`ANTHROPIC_BASE_URL=http://proxy:8080` で誘導 |

Anthropic は最も強い形として後者を推奨：「the agent never sees the credential itself」 <a href="https://code.claude.com/docs/en/agent-sdk/secure-deployment" target="_blank">(Anthropic Secure Deployment)</a>。本テンプレートは **「env で始められるが、proxy 注入に差し替えられる構造」** をデフォルトとする。

`CLAUDE_CODE_OAUTH_TOKEN`（`claude setup-token` で発行する長寿命トークン）も同じ枠で扱う <a href="https://code.claude.com/docs/en/devcontainer" target="_blank">(Anthropic devcontainer)</a>。

---

## 5. サブエージェント実行方式の比較

ユーザの第二の関心：**「親 agent コンテナの中から、さらに別環境で子 agent を起動したい」**。
代表的な 5 つの方式を比較する。

### 5-1. 比較表

| 方式 | 仕組み | 隔離強度 | 親への要求 | 主な欠点 | 主な利点 |
| --- | --- | --- | --- | --- | --- |
| **A. Docker-in-Docker (privileged)** | コンテナ内で docker daemon を起動 | 中（共有カーネル）| `--privileged` 必須 | privileged は cap drop と矛盾、ストレージドライバ問題 <a href="https://jpetazzo.github.io/2015/09/03/do-not-use-docker-in-docker-for-ci/" target="_blank">(Petazzoni)</a> | 子も独自 daemon を持ち分離 |
| **B. Docker socket mount (DooD)** | ホストの `docker.sock` をマウントし兄弟コンテナを起動 | **極低**（実質ホスト root と同等）| socket マウント | ホスト乗っ取りに直結、`:ro` も無意味 <a href="https://amf3.github.io/articles/virtualization/docker_socket/" target="_blank">(Docker Socket Myths)</a> <a href="https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html" target="_blank">(OWASP)</a> | 軽量 |
| **C. Sysbox-runc + DinD** | カスタム runc で rootless DinD を許可 | 高（user namespace 隔離） | Sysbox runtime インストール | runtime インストール作業 / 環境依存 | privileged 不要で本物の DinD <a href="https://github.com/nestybox/sysbox" target="_blank">(Sysbox)</a> |
| **D. Compose profiles + 兄弟コンテナ起動** | 親はコマンドオーケストレーションのみ。子はホスト側 docker から `docker compose run --profile sub agent` で別 PID/ネットワーク名前空間に起動 | 高（Sysbox 並、daemon は分けない）| 親コンテナは Docker と話さない。**外側のオーケストレータが起動**する | 親が直接 spawn できない → 親⇄子は ファイル / メッセージで通信 | Compose の自然な流儀、cap drop 維持可、Anthropic の parallel Claudes と整合 |
| **E. ホスト Docker Sandboxes (microVM)** | `sbx run` で microVM を都度起動 | 最強 | Docker Desktop / Docker Engine（ホスト） | Docker Desktop / 専用 Engine 依存 | Hypervisor + 専用 Engine + workspace + credential proxy の 5 層 <a href="https://docs.docker.com/ai/sandboxes/security/isolation/" target="_blank">(Docker)</a> |

### 5-2. パターンの解釈

- **A / B はテンプレートのデフォルトには採用しない**。B は OWASP / Datadog / 各種ベストプラクティスで明確に NG <a href="https://docs.datadoghq.com/security/default_rules/j9z-sms-f3m/" target="_blank">(Datadog)</a>。A は cap drop と矛盾し本テンプレートの方針（4-4）を崩す。
- **D（外側オーケストレータが兄弟起動）** が事実上の本命。これは Anthropic 自身の "Building a C compiler with a team of parallel Claudes" でも採用された方式：「bare git repo を作り、各エージェントに別コンテナを起動し、`/upstream` をマウントし、各自 `/workspace` にクローンする」 <a href="https://www.anthropic.com/engineering/building-c-compiler" target="_blank">(Anthropic, Building a C compiler)</a>。
- 親エージェントが「子エージェントを起こせ」と判断したら、**ホスト側オーケストレータ（Make / シェルスクリプト / 軽量 supervisor）に通知**する形を取り、親コンテナ自身は docker daemon と話さない。
- どうしても**親コンテナの中から直接** spawn する必要がある場合のみ **C（Sysbox）** を選ぶ。Sysbox なら privileged も socket マウントも不要で、user namespace 経由の root 隔離を維持できる <a href="https://blog.nestybox.com/2022/01/03/dink.html" target="_blank">(Nestybox)</a>。

### 5-3. ワークスペース共有のパターン

Anthropic の C compiler 事例から得られた知見：

- **bare repo を `/upstream` にマウント**、各 agent はそれを clone した自分の `/workspace` を持つ。
- agent 間の同期は **git push/pull**。タスクのロックは `current_tasks/<taskid>` ファイルを書くだけ。git のマージ衝突がロック競合検知になる。
- これにより「親 → 子 IPC」を 1 経路で実装でき、各 agent が独立コンテナで動いていても回る。
- **Agent SDK 内蔵の subagent（filesystem-based 定義の `.claude/agents/*.md`）は同一プロセス内**で動く別人格であり、コンテナ分離とは別レイヤ <a href="https://code.claude.com/docs/en/agent-sdk/hosting" target="_blank">(Anthropic SDK Hosting)</a>。コンテナ単位で隔離したいなら、5-2 D のように **外で別コンテナを起動**するアプローチを取る。

---

## 6. 推奨：本テンプレートに組み込む Docker Compose 構成

### 6-1. 構成方針

1. **`compose.yml` 1 ファイル + `compose.override.example.yml`** を `tools/agent-sandbox/`（仮）に配置。
2. サービスは 2 つ：
   - `egress-proxy`（Squid）：allowlist 強制、`isolated` と `internet` の両方に接続。
   - `agent`：`isolated` のみ。non-root、read-only root FS、cap drop ALL、tmpfs、`HTTP(S)_PROXY` 注入。
3. **profiles を使い、用途別に起動**：
   - `profiles: [run]` — `docker compose run --rm agent ...` でワンショット起動（ephemeral session）。
   - `profiles: [serve]` — 常駐型（Agent SDK のサーバ運用）。
   - `profiles: [sub]` — サブエージェント用。プロジェクト名 / workspace パスを env で外から渡す。
4. **サブエージェント起動は外側オーケストレータ**：親コンテナ内では `subagent.request` ファイルを書くだけにし、ホスト側 supervisor が `docker compose run --rm -e WORKDIR=... agent` で同等の隔離環境を立てる。
5. **シークレットは env から開始**、proxy 注入への差し替えポイントを `# CREDENTIAL_INJECTION` コメントで予約しておく。
6. **将来 hardening**：`runtime: runsc`（gVisor）や Docker Sandboxes 切替を ADR で意思決定できるよう、runtime に依存しない記述にする。

### 6-2. テンプレートが提供するもの（ドラフト）

```
tools/agent-sandbox/
├── compose.yml                 # 上記 2 サービス
├── compose.override.example.yml # 開発者ローカル用の追加マウント例
├── Dockerfile.agent            # node:22-slim ベース、claude CLI 同梱、non-root
├── proxy/squid.conf            # allowlist
├── scripts/
│   ├── run-agent.sh            # ワンショット起動ラッパ
│   └── spawn-subagent.sh       # 親コンテナがホストへ「子起動」を依頼する shim
└── README.md                   # 使い方・制約・ホスト側前提
```

ADR としては：

- **ADR 0003**：エージェントランタイムは Docker Compose で隔離する。デフォルトは標準 runc + egress proxy。
- **ADR 0004**：サブエージェントは外側オーケストレータ経由の兄弟コンテナ起動方式を採用する。docker socket マウント / privileged DinD は禁止。

の 2 本を切るのが妥当（本研究結果から接続）。

---

## 7. 検証方法（end-to-end）

実装に進む際の受け入れテスト案：

| 観点 | 検証 |
| --- | --- |
| ネットワーク allowlist | コンテナ内から `curl https://example.com`（**失敗**期待）と `curl https://api.anthropic.com`（**成功**期待）を実行 |
| 権限 | `id` が UID 1000、`capsh --print` で cap が空、`touch /sbin/x` が EROFS で失敗すること |
| FS 範囲 | `/workspace` 配下のみ書込可。`ls /etc/shadow` が読めないこと |
| シークレット | `printenv | grep -i anthropic` がコンテナ内には現れる（env 段階）。proxy 注入に切替後は **現れない**こと |
| サブエージェント | `scripts/spawn-subagent.sh` を親コンテナ内で実行 → ホスト supervisor が別コンテナを起動 → 独立 PID 名前空間で `claude` が走ることを `docker ps` で確認 |
| 統合 | 1 つの bare repo を `/upstream` にマウントし、2 つの sub agent が同じタスクを取り合った時に片方だけが成功する（git ロック）こと |

加えて、`scripts/validate-docs.sh` 相当の「compose lint」を CI に追加して、`cap_drop`, `read_only`, `user`, `tmpfs` の指定漏れを静的に検出するのが望ましい（gap-analysis 0002 の "リリースチェックリスト" 項目と接続）。

---

## 8. 補足・既知の制約

- **dev container 警告**：`--dangerously-skip-permissions` 下で **untrusted リポジトリ** を扱うと、コンテナ内に置いた認証情報がそのまま盗まれうる <a href="https://code.claude.com/docs/en/devcontainer" target="_blank">(Anthropic)</a>。テンプレート README には明示する。
- **Auto memory のリーク**：マルチテナント想定なら `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` と `CLAUDE_CONFIG_DIR` のテナント別指定が必要 <a href="https://code.claude.com/docs/en/agent-sdk/hosting" target="_blank">(Hosting the Agent SDK)</a>。本テンプレートの主想定（単一開発者）では off で良いが、将来分岐できるよう env を露出しておく。
- **Squid ACL の制約**：`.anthropic.com` と `api.anthropic.com` を重ねて書くと起動失敗する既知 quirk <a href="https://shaharia.com/blog/run-claude-code-docker-network-isolation/" target="_blank">(Shaharia)</a>。allowlist は重複しないよう注意。
- **macOS / WSL 差**：Docker Desktop と Linux の `userns-remap` 挙動差。Linux ホスト前提でドキュメント化し、Desktop 利用時の差分を `troubleshooting.md` で補足。
- **MCP サーバ**：MCP を使う場合、その外向きドメインを allowlist に追記する必要がある。`.mcp.json` を git 管理し、allowlist 生成スクリプトと連動できる構造が望ましい。
- **代替経路**：信頼境界がさらに厳しい場合は **`sbx run`（Docker Sandboxes）** または **microVM プロバイダ**（Modal Sandbox / Cloudflare Sandboxes / E2B / Fly Machines）への切替が Anthropic 公式の選択肢 <a href="https://code.claude.com/docs/en/agent-sdk/hosting" target="_blank">(Anthropic SDK Hosting)</a>。

---

## 9. 結論

- **デフォルトは Docker Compose + egress proxy（Squid）+ 標準 runc** で十分に実用的な多層防御を達成できる。Anthropic 公式 devcontainer と Shaharia 実装、Docker Sandboxes の知見を統合した構成が、本テンプレートの目的に最適。
- **サブエージェントは「外側オーケストレータが兄弟コンテナを起動」する D 方式** を採用する。これは Anthropic 自身の parallel Claudes 事例と整合し、cap drop / non-root を維持できる。privileged DinD と docker socket マウントは **禁止**。
- **将来の untrusted コード対応** は、ランタイム差し替え（gVisor / microVM）または Docker Sandboxes 移行で段階的に強化できる構造を維持する。

次のステップ：本研究を根拠に **ADR 0003（エージェント隔離方針）** と **ADR 0004（サブエージェント起動方式）** を起票し、accept 後に `tools/agent-sandbox/` の spec → 実装へ進む。

---

## Sources

- <a href="https://code.claude.com/docs/en/devcontainer" target="_blank">Development containers — Anthropic Claude Code Docs</a>
- <a href="https://code.claude.com/docs/en/agent-sdk/hosting" target="_blank">Hosting the Agent SDK — Anthropic Claude Code Docs</a>
- <a href="https://code.claude.com/docs/en/agent-sdk/secure-deployment" target="_blank">Securely deploying AI agents — Anthropic Claude Code Docs</a>
- <a href="https://github.com/anthropics/claude-code/tree/main/.devcontainer" target="_blank">anthropics/claude-code — reference .devcontainer</a>
- <a href="https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh" target="_blank">anthropics/claude-code — init-firewall.sh</a>
- <a href="https://www.anthropic.com/engineering/building-c-compiler" target="_blank">Building a C compiler with a team of parallel Claudes — Anthropic Engineering</a>
- <a href="https://docs.docker.com/ai/sandboxes/security/isolation/" target="_blank">Isolation layers — Docker AI Sandboxes Docs</a>
- <a href="https://docs.docker.com/ai/sandboxes/agents/claude-code/" target="_blank">Claude Code — Docker AI Sandboxes Docs</a>
- <a href="https://shaharia.com/blog/run-claude-code-docker-network-isolation/" target="_blank">Claude Code in Docker Compose: Network-Isolated Setup (2026) — Shaharia Azam</a>
- <a href="https://northflank.com/blog/how-to-sandbox-ai-agents" target="_blank">How to sandbox AI agents in 2026 — Northflank</a>
- <a href="https://github.com/nestybox/sysbox" target="_blank">nestybox/sysbox — Next-gen runc for rootless containers</a>
- <a href="https://blog.nestybox.com/2022/01/03/dink.html" target="_blank">Secure Docker-in-Kubernetes — Nestybox Blog</a>
- <a href="https://jpetazzo.github.io/2015/09/03/do-not-use-docker-in-docker-for-ci/" target="_blank">Using Docker-in-Docker for your CI? Think twice. — Jérôme Petazzoni</a>
- <a href="https://amf3.github.io/articles/virtualization/docker_socket/" target="_blank">Docker Socket Myths — Adam Faris</a>
- <a href="https://docs.datadoghq.com/security/default_rules/j9z-sms-f3m/" target="_blank">Containers should not mount the Docker socket — Datadog Default Rules</a>
- <a href="https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html" target="_blank">Docker Security Cheat Sheet — OWASP</a>
- <a href="https://github.com/receipting/claude-agent-sdk-container" target="_blank">receipting/claude-agent-sdk-container — Reference Container</a>
- <a href="https://news.ycombinator.com/item?id=44956002" target="_blank">Docker container for running Claude Code in dangerously-skip-permissions mode — HN discussion</a>
