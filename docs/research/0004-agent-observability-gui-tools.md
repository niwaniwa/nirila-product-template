---
id: "0004"
title: "Claude Code / Agent SDK プロジェクト向け 可視化 GUI・ローカル Observability ツール調査"
status: wip
created: 2026-06-21
updated: 2026-06-21
research_type: tech-evaluation
---

# Claude Code / Agent SDK プロジェクト向け 可視化 GUI・ローカル Observability ツール調査

## 目的

複数のエージェント（Claude Code / Codex / Agent SDK など）を同時に走らせるプロジェクトにおいて、

1. **並列セッションのオーケストレーション（どの agent が何の task をやっているか）**
2. **サブエージェント・タスクグラフの記録と可視化**
3. **トークン消費・コスト・ツール呼び出しの実行時メトリクス**

を可視化・記録するために使える **GUI ツール／ローカル Web サービス／observability バックエンド** を網羅的に調査する。

加えて、本リポジトリの方針である [0003 Docker 隔離テンプレート](./0003-docker-isolation-for-agents.md) と **どう併用できるか** を示す。

---

## 方法

- Anthropic 公式ドキュメント（`code.claude.com/docs/en/agent-sdk/observability` および `/monitoring-usage`）の精読
- 主要 LLM observability スタック（Langfuse / Phoenix-Arize / Helicone / Braintrust / Datadog / SigNoz / Lunary）の self-host / 統合方式を一次資料で確認
- Claude Code 向け GUI オーケストレータ（Crystal/Nimbalyst, Conductor, Claudia/opcode, Shipyard）の調査
- 計 20+ クエリ / 12 一次資料を取得し、クロスバリデーション

---

## 1. ツール landscape の 2 大分類

調査の結果、「複数 agent の可視化」と一口に言ってもツールは大きく 2 つの層に分かれる。

| 層 | 主目的 | 代表ツール | データ取得方式 |
| --- | --- | --- | --- |
| **A. Orchestration GUI（実行制御層）** | 並列セッションの起動・worktree 管理・diff レビュー・チェックポイント | Nimbalyst（旧 Crystal）、Conductor、Claudia/opcode、Shipyard | プロセス管理・ファイル監視・git worktree |
| **B. Observability Backend（記録解析層）** | 後追いで「誰が何を呼んで何トークン使ったか」をクエリ可能にする | Langfuse、Phoenix/Arize、SigNoz、Helicone、Braintrust、Datadog | **OpenTelemetry / OpenInference スパン** |

両者は競合しない。GUI で起動・操作し、その背後で OTel が tracing をバックエンドに流す **二段スタック** が現状のベストプラクティス。0003 の Docker 隔離方針と併用する際もこの 2 層を意識して設計する。

---

## 2. Anthropic 公式が提供する観測ポイント

Claude Code CLI（および Agent SDK が spawn する CLI）は **OpenTelemetry 計装が内蔵** されている <a href="https://code.claude.com/docs/en/agent-sdk/observability" target="_blank">(Observability with OpenTelemetry, Anthropic)</a>。「外側のツール」を選ぶ前に、**何を取り出せるか** を整理しておく：

### 2-1. 3 つの独立シグナル

| シグナル | 中身 | 有効化 |
| --- | --- | --- |
| **Metrics** | token, cost, session, lines of code, tool decision の各カウンタ | `OTEL_METRICS_EXPORTER` |
| **Logs (events)** | prompt / API request / API error / tool result の構造化レコード | `OTEL_LOGS_EXPORTER` |
| **Traces (beta)** | 後述の 4 種スパン | `OTEL_TRACES_EXPORTER` + `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` |

### 2-2. 出力されるスパン階層

トレースを有効にすると、エージェントのループが以下の階層で span 化される：

```
claude_code.interaction              (1 ターン)
├─ claude_code.llm_request           (Claude API 呼び出し, model / token / latency)
├─ claude_code.tool                  (ツール呼び出し)
│  ├─ claude_code.tool.blocked_on_user
│  └─ claude_code.tool.execution
└─ claude_code.hook                  (hook 実行, 詳細 beta)
```

> 重要：**サブエージェント（Task ツール / `.claude/agents/*.md` 経由）は、親の `claude_code.tool` 配下にネストされる**。delegation チェーン全体が 1 つのトレースとして読める <a href="https://code.claude.com/docs/en/agent-sdk/observability" target="_blank">(Anthropic)</a>。これが本調査の核心：**OTel を有効化するだけで「親 → サブ → ツール」のグラフが取れる**。

### 2-3. プライバシ既定

- 既定では prompt 本文・ツール入出力は **送信されない**（duration / model / tool name など structural のみ）。
- 必要時のみ `OTEL_LOG_USER_PROMPTS=1` / `OTEL_LOG_TOOL_DETAILS=1` / `OTEL_LOG_TOOL_CONTENT=1` / `OTEL_LOG_RAW_API_BODIES=1` で段階的に opt-in。

### 2-4. 親アプリのトレース文脈を継承

`query()` を呼ぶ時点で OTel span がアクティブなら、SDK は子 CLI に `TRACEPARENT` を注入し、`claude_code.interaction` が親アプリ span の子になる。これにより **「親アプリ → Claude SDK → CLI → Bash 経由の外部スクリプト」までを 1 つの trace に綴じ込み可能**。

---

## 3. ツール比較表

### 3-1. Orchestration GUI 層

| ツール | 形態 | 主機能 | 並列 worktree | Claude Code 対応 | ライセンス | 備考 |
| --- | --- | --- | --- | --- | --- | --- |
| **Nimbalyst**（旧 Crystal）| Electron デスクトップ（mac/Win/Linux）| 複数 Claude Code / Codex セッションを並列起動、diff・mock・Excalidraw 統合 | ✅ | ✅ | OSS | Crystal は 2026-02 で deprecated、Nimbalyst が後継 <a href="https://github.com/stravu/crystal" target="_blank">(stravu/crystal GitHub)</a> |
| **Conductor**（Melty Labs）| macOS app | parallel worktree、checkpoint、multi-model 比較（Claude vs Codex 同一 prompt）| ✅ | ✅ | 無料（API 課金はユーザ）| GitHub レポ指定 → workspace 作成 → 観察 <a href="https://madewithlove.com/blog/conductor-running-multiple-ai-coding-agents-in-parallel/" target="_blank">(madewithlove)</a> |
| **Claudia / opcode**（旧 Asterisk）| Tauri 2 + React 18 + Rust デスクトップ | プロジェクトブラウザ、custom agent、checkpoint タイムライン、コスト分析 | ⚠️ session 単位 | ✅ | OSS | OS レベル sandbox（seccomp / Seatbelt）、**完全ローカル・外部送信なし** <a href="https://github.com/getAsterisk/claudia" target="_blank">(getAsterisk/claudia)</a> |
| **Shipyard** | Web SaaS | 多 agent orchestration、CI 連動 | ✅ | ✅ | 商用 | ローカル要件には合致しない |

### 3-2. Observability Backend 層

| ツール | 形態 | Self-host | OTel 直結 | Claude Code 固有統合 | コスト/トークン | サブ agent span | エージェントグラフ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Langfuse** | OSS + Cloud | ✅ Docker compose 配布（MIT） | ✅ | OpenInference instrumentor が公式 <a href="https://langfuse.com/integrations/frameworks/claude-agent-sdk" target="_blank">(Langfuse)</a> | ✅ | ✅ | △（trace ツリー）|
| **Arize Phoenix** | OSS（Apache 2.0）| ✅ Docker | ✅ OpenInference | **公式 Coding Harness Tracing（16 hook 計装）** <a href="https://arize.com/docs/ax/integrations/platforms/claude-code/claude-code-tracing" target="_blank">(Arize)</a> | ✅ | ✅ `SubagentStart`/`Stop` フック | ✅ Agent Graph & Path Visualization |
| **SigNoz** | OSS + Cloud | ✅ Docker compose | ✅ OTLP | ⚠️ 一般 OTel として受信 <a href="https://signoz.io/blog/claude-code-monitoring-with-opentelemetry/" target="_blank">(SigNoz)</a> | ✅ | △（generic span）| ⚠️ Service map |
| **Helicone** | OSS Gateway + Cloud | ✅ Gateway self-host | ✅ OTLP（v3）| Anthropic SDK proxy として動作 | ✅ | ⚠️ | ⚠️ |
| **Braintrust** | Cloud（hybrid データプレーン）| ⚠️ | ✅ | MCP server 経由（Cursor/Claude Code/VS Code）<a href="https://www.augmentcode.com/tools/best-ai-agent-observability-tools" target="_blank">(Augment Code)</a> | ✅ | ✅ | △ |
| **Datadog LLM Obs** | Cloud のみ | ❌ | ✅ | Native MCP client tracing | ✅ | ✅ | ✅（APM 統合）|
| **LangSmith** | Cloud（self-host は Enterprise）| ⚠️ | ✅ | LangChain 系前提 | ✅ | ✅ | ✅ |

### 3-3. プラグイン / Skill 系の補助

- **Arize Coding Harness Tracing**：16 個の Claude Code hook（`SessionStart` / `UserPromptSubmit` / `PreToolUse` / `PostToolUse` / `SubagentStart` / `SubagentStop` …）を計装し OpenInference span を吐く。**Phoenix self-host 構成で動かせばクラウドに一切出ない** <a href="https://arize.com/docs/ax/integrations/platforms/claude-code/claude-code-tracing" target="_blank">(Arize)</a>。
- **nexus-labs / agent-observability**：Claude Code プラグイン形式（`/plugin install agent-observability@caleb-davis-plugins`）。Langfuse / LangSmith / Datadog 等への送信ガイダンスを含むが **計装テンプレ提供であり、自身は backend ではない** <a href="https://github.com/nexus-labs-automation/agent-observability" target="_blank">(nexus-labs)</a>。

---

## 4. 0003（Docker 隔離）との併用パターン

### 4-1. 結論サマリ

| 層 | 推奨配置 | 0003 への影響 |
| --- | --- | --- |
| **A. Orchestration GUI** | **ホスト側**で動かす | GUI は agent コンテナの「外側オーケストレータ」を兼ねる。0003 §5-2 のパターン D と一致 |
| **B. Observability Backend** | **同一 compose stack 内に sidecar として追加**（Langfuse / Phoenix を Docker で）| egress proxy の allowlist から「collector ホスト」を **除外**してよい（同一 internal network なので proxy を通らない）|

### 4-2. GUI 層を 0003 と組み合わせる

0003 が示した「親 agent は docker と話さない、外側 supervisor が子コンテナを起動する」モデルでは、**GUI ツール（Nimbalyst / Conductor / Claudia）こそが supervisor の UI 実装**になりうる：

```
┌──── ホスト ─────────────────────────────────────────────┐
│                                                        │
│  GUI (Nimbalyst / Conductor / Claudia)                 │
│      │                                                 │
│      ├── git worktree A → docker compose run agent ──┐ │
│      ├── git worktree B → docker compose run agent ──┼─┼─→ 各々が
│      └── git worktree C → docker compose run agent ──┘ │   isolated network +
│                                                        │   cap_drop な agent
└────────────────────────────────────────────────────────┘
```

- **Nimbalyst / Conductor**：worktree を切る部分はそのまま使えるが、**「該当 worktree を agent コンテナにマウントしてから起動」する起動コマンドの差し替え**が必要。両者とも内部の "agent 起動コマンド" を bash 1 行に置き換えられる作りなので、`docker compose run --rm -v <worktree>:/workspace agent` に置換するだけで Compose 経路に通せる（要：両ツールの hooks/launch-cmd 設定確認、issue 化推奨）。
- **Claudia / opcode**：すでに OS レベル sandbox（seccomp / Seatbelt）を持ち、**完全ローカル**で外部送信しない設計 <a href="https://github.com/getAsterisk/claudia" target="_blank">(getAsterisk/claudia)</a>。0003 の Docker 隔離とは **二重サンドボックス**になりオーバヘッドが大きいので、**「Docker 隔離 or Claudia の OS sandbox」のどちらかを採用**するのが現実的。コンテナ統一の方針なら Claudia は採用しない、ローカル限定でセットアップを軽くしたいなら Claudia を採用、と運用で分岐する。

### 4-3. Observability 層を 0003 の compose に追加する

Langfuse / Phoenix / SigNoz いずれも **Docker compose で self-host** が公式パターンで、本テンプレートの `tools/agent-sandbox/compose.yml` に **3 つ目の internal service** として乗せられる：

```yaml
# tools/agent-sandbox/compose.yml に追加（イメージ）

services:
  egress-proxy:
    # 4-3 既存
  agent:
    # 4-4 既存（cap_drop, read_only, non-root）
    environment:
      CLAUDE_CODE_ENABLE_TELEMETRY: "1"
      CLAUDE_CODE_ENHANCED_TELEMETRY_BETA: "1"     # traces
      OTEL_METRICS_EXPORTER: "otlp"
      OTEL_LOGS_EXPORTER: "otlp"
      OTEL_TRACES_EXPORTER: "otlp"
      OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf"
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-backend:4318"
      OTEL_SERVICE_NAME: "claude-${WORKSPACE_NAME}"
      # 既定では prompt 本文は送らない。必要時のみ opt-in：
      # OTEL_LOG_USER_PROMPTS: "1"
    networks: [isolated]

  otel-backend:
    image: langfuse/langfuse:latest         # または arizephoenix/phoenix:latest
    networks: [isolated, ui]                 # UI 用ネットワークだけ host にも露出
    ports: ["3000:3000"]                    # 開発者ブラウザ用
    volumes: [langfuse-data:/data]

networks:
  isolated: { internal: true }
  internet: { driver: bridge }
  ui: { driver: bridge }                    # localhost からだけ届く UI 用
```

ポイント：

- agent コンテナと collector は **`isolated` ネットワーク内で完結** → egress proxy の allowlist に collector を入れる必要なし（fail-closed のまま）。
- collector の管理 UI のみ別ネットワーク `ui` で localhost に publish。**外部に出さない**。
- `OTEL_SERVICE_NAME` をワークスペース名で動的に振ると、GUI 層で複数 worktree を並列に走らせても backend 側でフィルタ可能。
- prompt 本文の送出は既定 off。0003 のシークレット原則（agent が credential を見ない）と整合する。

### 4-4. 推奨スタック 2 種

#### スタック α：**最小・即動可（Anthropic 純正経路）**

- **GUI**：Nimbalyst（または terminal 直叩き）
- **Backend**：**Langfuse self-hosted**（Docker compose、MIT）
- **計装**：Anthropic 内蔵 OTel エクスポータ + `openinference-instrumentation-claude-agent-sdk` <a href="https://langfuse.com/integrations/frameworks/claude-agent-sdk" target="_blank">(Langfuse)</a>
- **強み**：セットアップが軽い、prompt 管理・eval ライブラリ同梱、MIT で再配布制限が緩い。
- **弱み**：subagent の "node-graph" 視覚化は弱め（trace tree で見る）。

#### スタック β：**サブエージェント可視化重視（Phoenix 経路）**

- **GUI**：Nimbalyst or Conductor
- **Backend**：**Arize Phoenix self-hosted**（Docker、Apache 2.0）
- **計装**：**Arize Coding Harness Tracing**（`SubagentStart` / `SubagentStop` 含む 16 hook）<a href="https://arize.com/docs/ax/integrations/platforms/claude-code/claude-code-tracing" target="_blank">(Arize)</a>
- **強み**：**Agent Graph & Path Visualization** で「親 → サブ → ツール」をノードグラフで一望、Anthropic 標準スパン + hook 由来スパンの両方を取れる。
- **弱み**：Phoenix と Arize AX の差分・OpenInference の更新追随が必要。

両者 OTLP 互換なので、**始めは α、サブ agent ネスト解析が辛くなったら β に切替**、という段階移行が無理なく組める。

---

## 5. 推奨：本テンプレートへの組込み

### 5-1. 提供物

`tools/agent-sandbox/`（0003 の予定構造）に observability セクションを追加：

```
tools/agent-sandbox/
├── compose.yml
├── compose.observability.yml      # 追加。Langfuse(or Phoenix) を sidecar 化
├── compose.gui-bridge.yml         # 追加。GUI から起動するためのプロファイル
├── otel/
│   └── env.example                # CLAUDE_CODE_* / OTEL_* の最小セット
└── README.md                      # 「GUI 層」「Observability 層」の選択表
```

`docker compose --profile run -f compose.yml -f compose.observability.yml up` のように **observability は profile + ファイル分離** で opt-in に。

### 5-2. ADR への接続

本研究を根拠に：

- **ADR 0005**：エージェント observability 既定スタックを **Langfuse self-hosted + Anthropic 内蔵 OTel** とする。
- **ADR 0006**：オーケストレーション GUI は **Nimbalyst を一次推奨**、Claudia は「コンテナ隔離を採らないローカル限定モード」用にオプション。

の 2 本を起票するのが妥当。

### 5-3. 併用手順（ユーザ向け抜粋）

```bash
# 1. observability sidecar を起動（permanent）
docker compose -f tools/agent-sandbox/compose.yml \
               -f tools/agent-sandbox/compose.observability.yml \
               up -d otel-backend egress-proxy
# → http://localhost:3000 で Langfuse UI

# 2. agent を ephemeral で投入
docker compose -f tools/agent-sandbox/compose.yml \
               -f tools/agent-sandbox/compose.observability.yml \
               --profile run \
               run --rm \
               -v "$(git -C $WORKTREE rev-parse --show-toplevel):/workspace" \
               -e OTEL_SERVICE_NAME="claude-${WORKTREE##*/}" \
               agent -p "$PROMPT"

# 3. Nimbalyst からは、上記コマンドを launch-cmd に登録するだけ
```

---

## 6. 既知の制約・注意点

- **`console` exporter は禁止**：Anthropic SDK は stdout を message channel として使うため、`OTEL_*_EXPORTER=console` を設定すると壊れる <a href="https://code.claude.com/docs/en/agent-sdk/observability" target="_blank">(Anthropic)</a>。OTLP 一択。
- **flush タイミング**：CLI はバッチ書き出し。短命プロセスで span が落ちる可能性があるため `OTEL_TRACES_EXPORT_INTERVAL=1000` 等で短縮する。
- **prompt 本文の送出**：`OTEL_LOG_USER_PROMPTS=1` 等を有効にすると prompt / tool input / API body が backend に流れる。**0003 のシークレット非開示原則と矛盾しうる**ので、Langfuse / Phoenix が self-host であることが前提。送出可否は ADR で明文化すべき。
- **Helicone**：post-acquisition で maintenance mode との情報あり <a href="https://www.augmentcode.com/tools/best-ai-agent-observability-tools" target="_blank">(Augment Code)</a>。新規採用は慎重に。
- **GUI ツールの Docker 統合**：Nimbalyst / Conductor は **元々ホスト直接実行を想定**しており、agent をコンテナ経由で起動するためには起動コマンドのカスタマイズが必要。0003 の方針を採るなら、**「起動コマンドが差し替え可能か」を採用条件**とする。Claudia は OS sandbox を内蔵しているため二重隔離コスト要評価。
- **Conductor は macOS 限定**：Linux / Windows のチーム共有では Nimbalyst のほうが汎用。
- **Anthropic OTel は traces が beta**：span 名や属性の breaking change がありうる <a href="https://code.claude.com/docs/en/agent-sdk/observability" target="_blank">(Anthropic)</a>。pin したいなら CLI バージョンを固定し、変更ログを CI でウォッチ。

---

## 7. 結論

- 「Agent を可視化したい」要求は **GUI 層**（並列実行制御）と **Observability 層**（記録・解析）の 2 層に分解できる。両者は補完関係。
- **Anthropic 公式の OTel エクスポータ** が `claude_code.interaction` / `llm_request` / `tool` / `hook` のスパンと「サブエージェントは親 `tool` 配下にネスト」というセマンティクスを既に提供しているので、**外側ツール選びは OTLP 互換性で割り切れる**。
- 0003 の Docker 隔離方針と併用するには、
  - **Backend は同一 compose stack に sidecar 化**（egress proxy を通らずに isolated network 内で送信）。
  - **GUI は 0003 の "外側 supervisor" を兼ねる UI 実装**として位置付ける（Nimbalyst / Conductor）。Claudia は二重サンドボックスの非効率を理解した上で採用判断。
- 既定推奨は **Langfuse self-hosted + Nimbalyst**。サブエージェントのグラフ可視化を強化したい段階で **Phoenix + Arize Coding Harness Tracing** に切替。

次のステップ：ADR 0005 / 0006 を起票し、accept 後に `compose.observability.yml` 雛形と `otel/env.example` を spec 化 → 実装。

---

## Sources

- <a href="https://code.claude.com/docs/en/agent-sdk/observability" target="_blank">Observability with OpenTelemetry — Anthropic Claude Code Docs</a>
- <a href="https://code.claude.com/docs/en/monitoring-usage" target="_blank">Monitoring — Anthropic Claude Code Docs</a>
- <a href="https://langfuse.com/integrations/frameworks/claude-agent-sdk" target="_blank">Observability for Claude Agent SDK with Langfuse — Langfuse</a>
- <a href="https://github.com/doneyli/claude-code-langfuse-template" target="_blank">claude-code-langfuse-template — Self-hosted Langfuse for Claude Code</a>
- <a href="https://arize.com/docs/ax/integrations/platforms/claude-code/claude-code-tracing" target="_blank">Claude Code Tracing — Arize AX Docs</a>
- <a href="https://arize.com/docs/phoenix/integrations/developer-tools/coding-agents" target="_blank">Coding Agents — Phoenix</a>
- <a href="https://github.com/arize-ai/phoenix" target="_blank">Arize-ai/phoenix — AI Observability & Evaluation (OSS)</a>
- <a href="https://signoz.io/blog/claude-code-monitoring-with-opentelemetry/" target="_blank">Bringing Observability to Claude Code: OpenTelemetry in Action — SigNoz</a>
- <a href="https://github.com/nexus-labs-automation/agent-observability" target="_blank">nexus-labs-automation/agent-observability — Claude Code plugin</a>
- <a href="https://github.com/stravu/crystal" target="_blank">stravu/crystal — (Now Nimbalyst) Parallel Claude Code / Codex sessions</a>
- <a href="https://nimbalyst.com/blog/best-multi-agent-coding-tools-2026/" target="_blank">Best Multi-Agent Coding Tools for Claude Code and Codex Users (2026) — Nimbalyst</a>
- <a href="https://madewithlove.com/blog/conductor-running-multiple-ai-coding-agents-in-parallel/" target="_blank">Conductor: running multiple AI coding agents in parallel — madewithlove</a>
- <a href="https://www.augmentcode.com/tools/intent-vs-conductor-macos-agent-orchestrators" target="_blank">Conductor vs Intent (2026) — Augment Code</a>
- <a href="https://github.com/getAsterisk/claudia" target="_blank">getAsterisk/claudia (opcode) — GUI Toolkit for Claude Code</a>
- <a href="https://claudia.so/" target="_blank">Claudia GUI Official Site</a>
- <a href="https://www.augmentcode.com/tools/best-ai-agent-observability-tools" target="_blank">7 Best AI Agent Observability Tools for Coding Teams (2026) — Augment Code</a>
- <a href="https://shipyard.build/blog/claude-code-multi-agent/" target="_blank">Multi-agent orchestration for Claude Code in 2026 — Shipyard</a>
- <a href="https://www.anthropic.com/engineering/building-c-compiler" target="_blank">Building a C compiler with a team of parallel Claudes — Anthropic Engineering</a>
