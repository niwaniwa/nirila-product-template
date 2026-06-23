---
id: "0005"
title: "nimbalyst-integration: GUI から agent-sandbox をワンクリック起動する"
status: accepted
phase: mvp
created: 2026-06-22
updated: 2026-06-22
related_adr: ["0003", "0004", "0006"]
---

# nimbalyst-integration: GUI から agent-sandbox をワンクリック起動する

## 概要

[Nimbalyst](https://github.com/stravu/crystal)（旧 Crystal）の **launch-cmd 設定値として貼り付け可能な wrapper script** を `tools/agent-sandbox/scripts/run-via-nimbalyst.sh` に提供し、GUI からの起動経路を ADR 0003 / 0004 の Docker 隔離経路に確実に通す。Nimbalyst 自体のインストールはユーザ手動。

## 背景・ADR参照

- [ADR 0003: エージェント実行は Docker Compose で隔離する](../adr/0003-agent-execution-docker-isolation.md)（accepted）
- [ADR 0004: サブエージェントは外側 supervisor 経由で兄弟コンテナ起動する](../adr/0004-subagent-execution-pattern.md)（accepted）
- [ADR 0006: オーケストレーション GUI は Nimbalyst を一次推奨とする](../adr/0006-orchestration-gui-nimbalyst.md)（accepted）

Nimbalyst は worktree 単位で agent を並列起動する GUI。`launch-cmd` に任意コマンドを設定でき、worktree のパスを引数で渡してくる。これを **wrapper 経由で `docker compose run --rm agent`** に差し替えれば、GUI から起動しても agent は隔離コンテナで走る。

## 要件

### 機能要件

- **MUST**:
  - `tools/agent-sandbox/scripts/run-via-nimbalyst.sh` は引数 `<worktree-path>` を受け、その path をホスト絶対パスに正規化した上で `WORKSPACE=$path docker compose -f tools/agent-sandbox/compose.yml run --rm agent "$@"` を実行する
  - スクリプトは実行可能（`+x`）
  - 失敗時は exit code 非ゼロを返し、Nimbalyst 側でエラー表示できる
  - 引数なし / 不正な path の場合は明示エラーで終了
- **SHOULD**:
  - observability mode（`compose.observability.yml`）を併用したい場合の手順を README に記載
  - sub-agent supervisor を起動済みでも干渉しない（compose の profile 仕様に依存）
  - shellcheck 相当の構文チェックを通る
- **COULD**:
  - Conductor / Claudia 等の代替 GUI 用 wrapper も同じ scripts/ 配下に追加可能な構造にする（本 spec ではスコープ外）

### 非機能要件

- **パフォーマンス**：起動オーバーヘッドは `docker compose run` 単独実行と同等（wrapper 分の overhead 100ms 以内）
- **セキュリティ**：
  - wrapper は **追加権限を要求しない**（Nimbalyst を実行しているユーザの権限内）
  - `--privileged` / `docker.sock` マウントを **追加しない**（ADR 0003 / 0004 の方針）
  - GUI から渡される path 以外の引数（prompt 等）は agent CLI にそのまま透過させるが、隔離プロファイル（cap_drop / read_only / non-root）は compose 側で固定なので緩まない

## スコープ

### このフェーズで対応するもの

- `tools/agent-sandbox/scripts/run-via-nimbalyst.sh`：launch-cmd 用 wrapper
- `tools/agent-sandbox/README.md` 更新：「GUI 連携（Nimbalyst）」セクション。Nimbalyst インストール手順への公式リンク、launch-cmd 設定値、observability 併用パターン、トラブルシュート
- 構文チェック（`bash -n`）

### 対応しないもの（後続フェーズ）

- Nimbalyst 自体のインストール自動化（OS 依存が大きく、テンプレ範囲外）
- Conductor / Claudia 等の代替 GUI ラッパー
- Nimbalyst の CI 化された smoke test（GUI ツールなので headless 実行はサポートされない）
- Nimbalyst の設定ファイル（preferences.json 等）の自動生成

## 技術設計

### wrapper の構造

```bash
#!/usr/bin/env bash
# Nimbalyst の launch-cmd に絶対パスでこの script を貼る前提。
# Nimbalyst が worktree のパスを第 1 引数で渡してくる仕様に従う。
#
# 使い方 (Nimbalyst の Settings → launch-cmd):
#   /absolute/path/to/tools/agent-sandbox/scripts/run-via-nimbalyst.sh {{worktree}}

set -euo pipefail

WORKTREE="${1:?usage: $0 <worktree-path> [extra args for claude]}"
shift || true

if [ ! -d "$WORKTREE" ]; then
  echo "ERROR: worktree path not found: $WORKTREE" >&2
  exit 2
fi

# worktree を含む git リポジトリのルートを compose ファイルの場所として使う。
PROJECT_ROOT="$(git -C "$WORKTREE" rev-parse --show-toplevel)"
COMPOSE_FILE="${PROJECT_ROOT}/tools/agent-sandbox/compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: compose file not found at $COMPOSE_FILE" >&2
  exit 3
fi

exec env WORKSPACE="$WORKTREE" \
  docker compose -f "$COMPOSE_FILE" \
  run --rm agent "$@"
```

要点：

- `set -euo pipefail` で異常系を確実に拾う
- worktree が git 内であることを前提に、リポジトリルートを動的に解決
- `exec` で wrapper を docker compose プロセスに置き換え、終了コードと TTY を透過
- 隔離プロファイル（cap_drop / read_only / non-root / isolated ネット）は compose.yml 側で固定されているため、wrapper は **isolation を一切緩めない**

### README に書くこと

- Nimbalyst インストール（公式リポジトリリンク、自前ビルド手順）
- launch-cmd 設定値（絶対パス指定例、`{{worktree}}` 等の Nimbalyst プレースホルダ）
- observability 併用時の launch-cmd 例（`-f compose.observability.yml` を追加した wrapper のバリエーション）
- sub-agent supervisor と並走させるパターン
- トラブルシュート（path 引数の渡し方差、`/var/run/docker.sock` への到達性、Linux/macOS の Docker Desktop 設定）

### 拒否設定

- `--privileged` / `docker.sock` マウントを **追加しない**
- Nimbalyst 側から compose ファイル path / image / volume を上書きされる API は **提供しない**（wrapper は固定 path を解決する）

## 受け入れ基準

- [x] `bash -n tools/agent-sandbox/scripts/run-via-nimbalyst.sh` が構文 OK
- [x] script が `+x` で実行可能（`ls -l` で `-rwxr-xr-x` 確認）
- [x] 引数なし実行で `usage:` メッセージを出し exit `1`
- [x] 不正な path（`/nonexistent`）を渡すと `ERROR: worktree path not found:` を出し exit `2`
- [x] 正常な worktree path を渡すと、`bash -x` トレースで `exec env WORKSPACE=<path> docker compose -f <project-root>/tools/agent-sandbox/compose.yml run --rm agent` が組み立てられる
- [x] `tools/agent-sandbox/README.md` に「GUI 連携（Nimbalyst）」セクション、インストール手順リンク、launch-cmd 設定例、`EXTRA_COMPOSE_FILES` で observability 併用、トラブルシュートが記載
- [x] `bash scripts/validate-docs.sh` がエラー 0
- [ ] **手動**：実 Nimbalyst から wrapper を呼び agent が立ち上がること（GUI ツールのため CI 化はしない。ユーザ環境で動作確認）

## 未解決事項

実 MVP の wrapper 動作確認で解決済み：

- ~~wrapper の構文と exit code の網羅~~ → smoke test で `1` / `2` / docker compose 透過を確認
- ~~git 配下でない path への対応~~ → `git -C "$WORKTREE" rev-parse --show-toplevel` が失敗するため自然に non-zero exit

後続で扱うもの：

- Nimbalyst の `{{worktree}}` プレースホルダ仕様は本家ドキュメントで最終確認の上で README に補足（**ユーザ側で確認**）
- Nimbalyst が prompt をどう渡してくるかの 3 パターン（stdin / 引数 / なし）の検証 → ユーザ手動セットアップ後に必要であれば README にバリエーション追加
- Conductor / Claudia 等の代替 GUI 向け wrapper（同じ scripts/ 配下に追加可能）
