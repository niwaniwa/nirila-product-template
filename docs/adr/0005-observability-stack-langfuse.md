---
id: "0005"
title: "Observability 既定スタックは OpenTelemetry Collector + Anthropic 内蔵 OTel"
status: archive
created: 2026-06-21
updated: 2026-06-22
decision_owner: "プロジェクトリーダー"
---

# Observability 既定スタックは OpenTelemetry Collector + Anthropic 内蔵 OTel

> **本 ADR は archive 済み**。実装の根拠としては使用しない。再導入時は新規 ADR を起票して本 ADR を「過去の検討」として参照すること。

> **Amend 履歴**:
>
> - 2026-06-22（初稿）: Langfuse self-hosted を推奨に。
> - 2026-06-22（amend 1）: Langfuse v3 self-host が 6 コンテナ必要なため **Arize Phoenix（単一コンテナ）** に変更。
> - 2026-06-22（amend 2）: 実機検証で **Claude Code CLI v2.1.185 が `-p` / 対話モードどちらでも OTel emit を実装観測できなかった** ことに加え、Phoenix は traces 専用 backend で metrics/logs は silent に 404 になる構造的問題が判明。診断容易性を優先し **OpenTelemetry Collector (contrib) + debug/file exporter** に変更。
> - 2026-06-22（amend 3 / **archive**）: MVP から observability スタックを **全削除**。CLI emit が未到達のため受け手を抱える意義が薄いと判断。実装ファイル（`compose.observability.yml` / `otel/`）も同時に削除。[spec 0004](../spec/0004-observability-sidecar.md) も archive 化。

## コンテキスト

本テンプレートを使うプロジェクトでは、複数の Claude Code / Agent SDK セッションが並列に走る。「どの agent が何のツールを呼び、何トークン使い、サブエージェントをどう delegate したか」を後追いで可視化する **observability バックエンド** をテンプレートに同梱する必要がある。

[research/0004](../research/0004-agent-observability-gui-tools.md) で確認した通り：

- Anthropic 公式の Claude Code CLI には **OpenTelemetry エクスポータが内蔵** されており、`claude_code.interaction` / `llm_request` / `tool` / `hook` のスパン階層と、**サブエージェントを親 `tool` 配下に自動ネスト** するセマンティクスを提供する。
- したがって外側ツールの選定は **OTLP 互換性** で割り切ってよい。
- [ADR 0003](./0003-agent-execution-docker-isolation.md) の Docker 隔離方針と整合させるには、collector を **同一 compose stack の `isolated` ネットワーク内に sidecar として配置** するのが自然。

### 実機検証で判明したこと（amend 2 の根拠）

1. Claude Code CLI v2.1.185 で `CLAUDE_CODE_ENABLE_TELEMETRY=1` / `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` / OTLP 関連 env を全て正しく設定したが、`-p` モードでも対話モードでも Phoenix の `/v1/traces` に POST が来なかった。
2. <a href="https://techblog.zozo.com/entry/claudecode-otel" target="_blank">ZOZO の事例</a> は **traces を使わず metrics + logs のみ** を OTel Collector 経由で取っている。traces は beta で実装が成熟していない可能性が高い。
3. **Phoenix は traces 専用** backend で、metrics / logs を投げると `/v1/metrics` / `/v1/logs` で 404 silent になる。つまり「emit されているのに UI に映らない」のか「emit されていない」のかが切り分けられない。
4. UI が必要なくても、**「何がいつ届いたか」を `docker logs` で目視できる**経路があれば診断・運用上は十分。

## 検討した選択肢

### 選択肢 A: OpenTelemetry Collector (contrib) + debug/file exporter ✅ 採用

- 利点:
  - **単一コンテナ**で self-host 可能（`otel/opentelemetry-collector-contrib`）
  - **3 シグナル全て受信**（traces / metrics / logs）。silent 404 が起きない
  - **debug exporter で stdout に全フレームを生で出す** → `docker logs agent-sandbox-otel-collector` で即座に確認可能。CLI 側の emit 状況が一目瞭然
  - **file exporter で JSONL 永続化** → `grep` / `jq` で後追い可能、CI でアサート可能
  - UI が必要になった時は exporter を 1 行追加するだけで Tempo / Jaeger / Phoenix 等を後段に挿せる
  - **localhost に publish するポートが 0 個**になり、ローカル隔離がさらに強化される
- 欠点:
  - GUI で trace ツリーを俯瞰したい用途には向かない（JSONL を `jq` で読む or 別 UI を追加する）
  - JSONL ファイルは無限に膨らむため rotate を運用で管理する必要

### 選択肢 B: Arize Phoenix self-hosted

- 利点: Agent Graph 視覚化、単一コンテナ、Apache 2.0
- 欠点: traces 専用、metrics/logs は silent 404。実機で claude CLI からの POST が来ているか確認できない（**今回の amend 2 の直接の引き金**）

### 選択肢 C: Langfuse self-hosted

- 利点: MIT、prompt 管理 / eval ライブラリ同梱
- 欠点: v3 self-host が **6 コンテナ必要**で MVP に重い、v2 軽量モードは EOL

### 選択肢 D: SigNoz self-hosted

- 利点: OSS、APM 統合
- 欠点: Claude Code 固有の計装なし、サブエージェントのネスト解析は弱い

### 選択肢 E: Helicone / Braintrust / Datadog 等 SaaS

- 利点: セットアップが軽い
- 欠点: ローカル要件と矛盾、ADR 0003 のシークレット非開示原則と整合させづらい

## 決定

**選択肢 A: OpenTelemetry Collector (contrib) + Anthropic 内蔵 OTel** を既定スタックとして採用する。

UI による視覚化が必要になった段階で、**Phoenix / Langfuse / Jaeger / Tempo / Grafana** などを collector の後段 exporter として追加する（migration path は OTLP 互換性で担保）。

### 構成方針

- **Collector を compose stack の sidecar として配置**：[ADR 0003](./0003-agent-execution-docker-isolation.md) の `isolated` ネットワーク内に置き、agent → collector の送信は egress proxy を経由しない。
- **`debug` exporter（stdout）と `file` exporter（JSONL）の二系統で受け取り**：
  - `debug` は CLI emit 状況の即時診断
  - `file` は `shared/otel/*.jsonl` に永続化、後追い解析・CI アサート用
- **localhost への publish なし**：collector は内部ネットでのみ動作、UI / port 露出ゼロ。
- **既定の有効化フラグ**：

  ```text
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=0   # 観測時は base の 1 を明示的に上書き
  CLAUDE_CODE_ENABLE_TELEMETRY=1
  CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1
  OTEL_METRICS_EXPORTER=otlp
  OTEL_LOGS_EXPORTER=otlp
  OTEL_TRACES_EXPORTER=otlp
  OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
  OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
  OTEL_SERVICE_NAME=claude-${WORKSPACE_NAME}
  ```

- **prompt 本文の送出は既定 off**：`OTEL_LOG_USER_PROMPTS` / `OTEL_LOG_TOOL_DETAILS` / `OTEL_LOG_TOOL_CONTENT` / `OTEL_LOG_RAW_API_BODIES` は env テンプレでコメントアウト、明示的に opt-in する運用。
- **flush 設定**：短命プロセスでの span 落ちを抑えるため `OTEL_*_EXPORT_INTERVAL=1000` 既定。
- **`console` exporter は禁止**：Agent SDK は stdout を message channel として使うため。
- **opt-in 配信**：`compose.observability.yml` を別ファイル化し、`-f` で重ねる時のみ有効。

### 提供物（[spec 0004 で詳細化]）

```text
tools/agent-sandbox/
├── compose.observability.yml         # OTel Collector sidecar
├── otel/
│   ├── env.example                   # CLAUDE_CODE_* / OTEL_* の最小セット
│   └── collector-config.yaml         # debug + file/jsonl の 2 系統 exporter
└── shared/otel/                      # JSONL 出力先 (.gitignore 済み)
```

## 影響

- 正：CLI が emit すれば直ちに `docker logs agent-sandbox-otel-collector` に生フレームが現れる。診断時間が劇的に短縮される。
- 正：3 シグナル全て受信可能で silent 失敗がない。
- 正：localhost にポートを publish しないため、ローカル隔離がさらに強化される。
- 正：UI / 別 backend が必要になった時は exporter を 1 行追加するだけ。Phoenix / Langfuse / Jaeger / Tempo / Grafana へ自由に伸ばせる。
- 正：JSONL なので `jq` / `grep` / CI アサートが容易。
- 負：trace ツリーをグラフィカルに俯瞰したい場合は後段に UI 追加が必要。
- 負：JSONL は rotate を運用で管理する必要（手動削除 or logrotate）。
- リスク：CLI emit 未達は本 ADR では解決しない（受け手側の話）。emit 側の問題は spec 0004 の未解決事項として上流調査タスクに残置。

## 参考

- [research/0004: Claude Code / Agent SDK プロジェクト向け 可視化 GUI・ローカル Observability ツール調査](../research/0004-agent-observability-gui-tools.md)
- [ADR 0003: エージェント実行は Docker Compose で隔離する](./0003-agent-execution-docker-isolation.md)
- [ADR 0006: オーケストレーション GUI](./0006-orchestration-gui-nimbalyst.md)
- [spec 0004: observability sidecar](../spec/0004-observability-sidecar.md)
- [Anthropic Observability with OpenTelemetry](https://code.claude.com/docs/en/agent-sdk/observability)
- [OpenTelemetry Collector (contrib)](https://github.com/open-telemetry/opentelemetry-collector-contrib)
- [ZOZO Tech Blog: Claude Code × OpenTelemetry](https://techblog.zozo.com/entry/claudecode-otel)（amend 2 の根拠）
- [Arize Phoenix Self-Hosting](https://arize.com/docs/phoenix/self-hosting)（後段に追加する場合の選択肢）
- [Langfuse Claude Agent SDK Integration](https://langfuse.com/integrations/frameworks/claude-agent-sdk)（後段に追加する場合の選択肢）
