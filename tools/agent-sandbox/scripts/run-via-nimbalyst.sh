#!/usr/bin/env bash
# Nimbalyst の launch-cmd に絶対パスでこの script を貼る前提。
# Nimbalyst が worktree のパスを第 1 引数で渡してくる仕様に従う。
#
# 使い方 (Nimbalyst の Settings → launch-cmd, 例):
#   /absolute/path/to/tools/agent-sandbox/scripts/run-via-nimbalyst.sh {{worktree}}
#
# 追加の override compose ファイルを重ねたい場合は EXTRA_COMPOSE_FILES に
# "-f /path/to/extra.yml" を入れて呼び出す。
#
# 根拠: ADR 0003 / ADR 0004 / ADR 0006 / spec 0005

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

# 追加 override -f を環境変数経由で受け取る (任意)。
# 例: EXTRA_COMPOSE_FILES="-f /abs/path/to/some-override.yml"
EXTRA_COMPOSE_FILES="${EXTRA_COMPOSE_FILES:-}"
# shellcheck disable=SC2086  # EXTRA_COMPOSE_FILES は意図的に複数引数に分割させる
exec env WORKSPACE="$WORKTREE" \
  docker compose -f "$COMPOSE_FILE" $EXTRA_COMPOSE_FILES \
  run --rm agent "$@"
