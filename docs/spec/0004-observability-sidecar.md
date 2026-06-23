---
id: "0004"
title: "observability-sidecar: OTel Collector を Docker 隔離に同梱する"
status: archive
phase: mvp
created: 2026-06-22
updated: 2026-06-22
related_adr: ["0003", "0005"]
---

# observability-sidecar: OTel Collector を Docker 隔離に同梱する

> **本 spec は archive 済み**。実装の根拠としては使用しない。実装ファイル（`compose.observability.yml` / `otel/`）は削除済み。再導入時は新規 spec を起票すること。

> **改訂履歴**:
>
> - 2026-06-22: 当初は Arize Phoenix を sidecar に置く設計。
> - 2026-06-22: ADR 0005 amend 2 で **OpenTelemetry Collector (contrib)** に切り替え、本 spec も全面改訂。
> - 2026-06-22: archive 化。MVP から observability スタックを全削除（[ADR 0005](../adr/0005-observability-stack-langfuse.md) amend 3 の決定に追随）。実装ファイルも削除。受け入れ基準セクション以降は履歴として残置。

## 概要

ADR 0005 が定めた「OTel Collector + Anthropic 内蔵 OTel」を、ADR 0003 / spec 0002 の compose stack に **opt-in の override file** として同梱する。`compose.observability.yml` を `-f` で重ねれば observability、付けなければ off。CLI が emit しているかどうかを `docker logs` で即座に判定でき、JSONL で永続化される。

## 背景・ADR参照

- [ADR 0003: エージェント実行は Docker Compose で隔離する](../adr/0003-agent-execution-docker-isolation.md)（accepted）
- [ADR 0005: Observability 既定スタックは OpenTelemetry Collector + Anthropic 内蔵 OTel](../adr/0005-observability-stack-langfuse.md)（accepted、amend 2）

## 要件

### 機能要件

- **MUST**:
  - `tools/agent-sandbox/compose.observability.yml` を `-f` で重ねると、`otel-collector` サービスが起動し、agent サービスに OTel env が override される
  - Collector は **`isolated` ネットワーク内** に配置され、agent → collector の通信は egress proxy を経由しない（allowlist 変更不要、fail-closed 維持）
  - Collector は **`/v1/traces` / `/v1/metrics` / `/v1/logs` の全 3 シグナルを受信** し、`debug` exporter で stdout に、`file` exporter で `shared/otel/*.jsonl` に出力する
  - prompt 本文・tool 入出力は **既定で送出しない**
  - `console` exporter は使用しない（SDK の stdio チャネルを壊すため）
  - **localhost に publish するポートはゼロ**（Collector は内部ネットでのみアクセス）
- **SHOULD**:
  - `tools/agent-sandbox/otel/env.example` を提供し、prompt opt-in フラグはコメントアウトで例示
  - `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_SERVICE_NAME` は env で override 可能
  - Collector の `image` バージョンは README で pin 推奨を明示
- **COULD**:
  - 将来 Phoenix / Tempo / Jaeger / Grafana 等を後段 exporter として追加可能な構造を保つ（OTLP 互換）

### 非機能要件

- **パフォーマンス**：otel-collector サービスは 512 MiB RAM 以内で起動し、初期化 10 秒以内に OTLP 受信開始
- **セキュリティ**：
  - Collector への外部公開なし
  - prompt opt-in フラグは env テンプレで明示 off、README で警告
  - Collector を agent から到達可能にするのは `isolated` 内部 DNS のみ

## スコープ

### このフェーズで対応するもの

- `tools/agent-sandbox/compose.observability.yml`：`otel-collector` サービス + agent OTel env override
- `tools/agent-sandbox/otel/collector-config.yaml`：receivers / processors / exporters
- `tools/agent-sandbox/otel/env.example`：CLAUDE_CODE_* / OTEL_* の最小セットと prompt opt-in 例
- `tools/agent-sandbox/README.md` 更新：「観測」セクション（Collector 版）
- `.gitignore`：`tools/agent-sandbox/otel/env`（個人設定）は除外済
- 受け入れテスト 6 種

### 対応しないもの（後続フェーズ）

- UI 系 backend（Phoenix / Tempo / Jaeger / Grafana 等）の追加
- Collector 後段への Cloud Logging / Datadog / Prometheus 等のフォワード
- supervisor / subagent への OTel 伝播の自動検証
- JSONL の自動 rotate / 削除

## 技術設計

### ディレクトリ構成

```text
tools/agent-sandbox/
├── compose.yml                       # 既存（変更なし）
├── compose.observability.yml         # 改訂（otel-collector）
├── otel/
│   ├── env.example                   # 更新
│   └── collector-config.yaml         # ★ 新規
├── README.md                         # 「観測」セクション差し替え
└── (gitignored) shared/
    └── otel/                         # ★ JSONL 出力先
```

### otel-collector サービスの compose 設計

- `image: otel/opentelemetry-collector-contrib:latest`（README で pin 推奨）
- `networks: [isolated]`
- `volumes: ./otel/collector-config.yaml:/etc/otelcol-contrib/config.yaml:ro` と `./shared/otel:/var/log/otel:rw`
- `command: ["--config=/etc/otelcol-contrib/config.yaml"]`
- `restart: unless-stopped`
- localhost への publish なし

### agent サービスへの OTel env override

`compose.observability.yml` で agent の `environment:` に以下を追加：

```yaml
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "0"   # base の 1 を上書き
CLAUDE_CODE_ENABLE_TELEMETRY: "1"
CLAUDE_CODE_ENHANCED_TELEMETRY_BETA: "1"
OTEL_METRICS_EXPORTER: otlp
OTEL_LOGS_EXPORTER: otlp
OTEL_TRACES_EXPORTER: otlp
OTEL_EXPORTER_OTLP_PROTOCOL: http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT: ${OTEL_EXPORTER_OTLP_ENDPOINT:-http://otel-collector:4318}
OTEL_SERVICE_NAME: ${OTEL_SERVICE_NAME:-claude-agent-sandbox}
OTEL_TRACES_EXPORT_INTERVAL: "1000"
OTEL_METRIC_EXPORT_INTERVAL: "1000"
OTEL_LOGS_EXPORT_INTERVAL: "1000"
```

### collector-config.yaml の構造

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s

exporters:
  debug:
    verbosity: detailed
  file/traces:
    path: /var/log/otel/traces.jsonl
  file/metrics:
    path: /var/log/otel/metrics.jsonl
  file/logs:
    path: /var/log/otel/logs.jsonl

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, file/traces]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, file/metrics]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, file/logs]
```

### otel/env.example の構造

```bash
# CLAUDE_CODE_* (Anthropic OTel)
CLAUDE_CODE_ENABLE_TELEMETRY=1
CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1

# OTLP exporter (Collector の内部 DNS 名)
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_SERVICE_NAME=claude-${WORKSPACE_NAME:-default}

# ---- prompt opt-in (既定 OFF。有効化すると prompt 本文が collector に流れる) ----
# OTEL_LOG_USER_PROMPTS=1
# OTEL_LOG_TOOL_DETAILS=1
# OTEL_LOG_TOOL_CONTENT=1
# OTEL_LOG_RAW_API_BODIES=1
```

### 拒否設定

- `OTEL_*_EXPORTER=console` は **書かない**
- Collector の port を localhost に publish しない（内部ネットのみ）

## 受け入れ基準

- [ ] `WORKSPACE="$(pwd)" docker compose -f tools/agent-sandbox/compose.yml -f tools/agent-sandbox/compose.observability.yml config --quiet` が成功する
- [ ] `up -d otel-collector egress-proxy` 後、`otel-collector` が `running` 状態
- [ ] **agent → Collector の 3 シグナル疎通**：agent コンテナ内から `POST http://otel-collector:4318/v1/traces` / `/v1/metrics` / `/v1/logs` のいずれも `200` または `400` 系応答（404 ではない）
- [ ] **env 反映**：agent コンテナ内で `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=0` / `CLAUDE_CODE_ENABLE_TELEMETRY=1` / `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318` が反映されている
- [ ] squid のアクセスログに Collector 宛のエントリがない
- [ ] agent コンテナ内で `printenv | grep OTEL_LOG_USER_PROMPTS` が空（既定 off）
- [ ] **`docker logs agent-sandbox-otel-collector`** に debug exporter のフレームが現れる（手動 POST テスト or 実 agent からの emit いずれかで）
- [ ] `tools/agent-sandbox/shared/otel/` 配下に `traces.jsonl` / `metrics.jsonl` / `logs.jsonl` のいずれかが作成される（emit があれば）
- [ ] `bash scripts/validate-docs.sh` がエラー 0
- [ ] README に「観測」セクション、起動コマンド、`docker logs` での確認方法、JSONL の見方、prompt opt-in 警告、image pin 推奨、JSONL rotate 注意が記載
- [ ] **Claude Code CLI からの emit が観測される** — **据え置き未達**。CLI v2.1.185 で emit が確認できない既知問題（spec 0004 旧版 / ADR 0005 amend 2 経緯）は本 spec のスコープ外。受け手側が診断容易な形に改善されたことで、CLI が emit し始めた瞬間に即検知できる構造になった。

## 未解決事項

amend 2 の動作確認で解決済み：

- ~~Phoenix が traces 専用で metrics/logs を silent 404~~ → Collector に切替して 3 シグナル全受信に対応
- ~~CLI emit の有無を診断できない~~ → debug exporter で stdout 即時確認可能になった
- ~~UI / port 露出によるローカル隔離の弱化~~ → Collector に切替えて localhost publish ゼロ

後続で扱うもの：

- **CLI v2.1.185 で OTel emit が観測されない原因調査**（最優先・**スコープ外**）：
  - 新しい CLI リリースで改善するか
  - Claude Agent SDK 経由（`query()`）であれば emit するか
  - 必要なら Anthropic 公式 issue tracker への報告
- supervisor 経由のサブエージェントにも OTel が透過する確認
- JSONL の自動 rotate（logrotate or Collector の rotation 設定）
- 後段 UI / backend の追加（Phoenix / Tempo / Jaeger / Grafana / Cloud 系）
