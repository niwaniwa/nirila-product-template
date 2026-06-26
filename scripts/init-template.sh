#!/usr/bin/env bash
#
# init-template.sh — テンプレート複製後のクリーンアップ
#
# 本リポジトリをテンプレートとして複製した直後に1回だけ実行する。
# このテンプレートを構築する過程で蓄積した固有の ADR/spec/research を削除し、
# 削除に伴って宙に浮く参照を保持ファイルから除去する。
#
# 根拠: docs/adr/0009-template-clone-cleanup.md（accepted, 軸2-B）
#
# 使い方:
#   bash scripts/init-template.sh         # 対象を表示して y/N 確認
#   bash scripts/init-template.sh --yes   # 確認を省略
#
# 冪等: 既に削除/編集済みでも失敗しない。最後にスクリプト自身を削除する。

set -euo pipefail

# --- 実行前準備 -------------------------------------------------------------

# スクリプト自身の絶対パスを cd 前に確定（末尾の自己削除に使う）
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

# リポジトリルートへ移動（どこから実行しても同じ挙動にする）
if ! ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "エラー: git リポジトリ内で実行してください（変更内容を git diff で確認できるように）。" >&2
  exit 1
fi
cd "$ROOT"

ASSUME_YES=0
[ "${1:-}" = "--yes" ] && ASSUME_YES=1

# --- 削除対象（固有履歴）----------------------------------------------------

DELETE_FILES=(
  "docs/adr/0002-template-extension-policy.md"
  "docs/adr/0007-github-operations-model.md"
  "docs/adr/0008-github-scaffolding-iteration.md"
  "docs/spec/0006-github-workflow.md"
  "docs/research/0001-ai-document-driven-development.md"
  "docs/research/0002-template-gap-analysis.md"
)

# 削除対象を参照している保持ファイル（編集して参照を除去する）
EDIT_FILES=(
  "CLAUDE.md"
  "scripts/hooks/impl-gate.py"
  "docs/guides/human-in-the-loop.md"
  ".github/labels.yml"
  ".github/ISSUE_TEMPLATE/task.md"
  ".github/pull_request_template.md"
  ".github/workflows/ci.yml"
  ".github/CODEOWNERS"
  "docs/adr/0009-template-clone-cleanup.md"
)

# --- 確認プロンプト ---------------------------------------------------------

echo "テンプレート複製クリーンアップ（docs/adr/0009 に準拠）"
echo
echo "削除する固有 doc:"
for f in "${DELETE_FILES[@]}"; do
  [ -f "$f" ] && echo "  - $f" || echo "  - $f (既に無し)"
done
echo
echo "参照を除去する保持ファイル:"
for f in "${EDIT_FILES[@]}"; do
  echo "  - $f"
done
echo
echo "保持: tools/agent-sandbox/, sandbox系 ADR/spec/research, 全 guides, _template/0001-example, .github/, hooks ほか"
echo

if [ "$ASSUME_YES" -ne 1 ]; then
  read -r -p "実行しますか？ [y/N] " ans
  case "$ans" in
    [yY] | [yY][eE][sS]) ;;
    *) echo "中止しました。"; exit 0 ;;
  esac
fi

# --- 削除 -------------------------------------------------------------------

echo
echo "==> 固有 doc を削除"
for f in "${DELETE_FILES[@]}"; do
  if [ -f "$f" ]; then
    rm -f "$f"
    echo "  削除: $f"
  fi
done

# --- 参照除去（冪等な literal 置換）----------------------------------------
# perl: \Q...\E で literal マッチ。マッチしなければ no-op（再実行しても安全）。

echo "==> 削除に伴う参照を除去"

edit() { # edit <file> <perl-expr>
  local file="$1" expr="$2"
  [ -f "$file" ] || return 0
  perl -0777 -i -pe "$expr" "$file"
  echo "  編集: $file"
}

edit "CLAUDE.md" \
  's{\Q- 根拠: [docs/adr/0008](docs/adr/0008-github-scaffolding-iteration.md) / [docs/guides/human-in-the-loop.md](docs/guides/human-in-the-loop.md)\E}{- 根拠: [docs/guides/human-in-the-loop.md](docs/guides/human-in-the-loop.md)}'

edit "scripts/hooks/impl-gate.py" \
  's{\Q根拠: docs/adr/0008-github-scaffolding-iteration.md（軸3）/ docs/guides/human-in-the-loop.md\E}{根拠: docs/guides/human-in-the-loop.md}'

edit "docs/guides/human-in-the-loop.md" \
  's{\Q、GitHub運用の根拠は [ADR 0007](../adr/0007-github-operations-model.md) / [spec 0006](../spec/0006-github-workflow.md) を参照。\E}{を参照。};
   s{\Q[spec 0006](../spec/0006-github-workflow.md) の supervisor 連携契約では\E}{supervisor 連携契約では};
   s{\Q / [ADR 0007](../adr/0007-github-operations-model.md) の境界）\E}{ の境界）};
   s{\Q- [ADR 0007](../adr/0007-github-operations-model.md) — GitHub運用モデル（人間ゲートの根拠）\E\n\Q- [spec 0006](../spec/0006-github-workflow.md) — Issue/PR/CI と supervisor連携の契約\E\n}{}'

edit ".github/labels.yml" \
  's{\Q — docs/spec/0006-github-workflow.md（accepted）に準拠。\E}{。}'

edit ".github/ISSUE_TEMPLATE/task.md" \
  's{\Qこのテンプレは docs/spec/0006-github-workflow.md（accepted）に準拠。\E\n}{}'

edit ".github/pull_request_template.md" \
  's{\Qdocs/spec/0006-github-workflow.md（accepted）に準拠。\E\n}{}'

edit ".github/workflows/ci.yml" \
  's{\Q# docs/spec/0006-github-workflow.md / docs/adr/0008-github-scaffolding-iteration.md（accepted）に準拠。\E}{# 言語非依存CIテンプレート。}'

edit ".github/CODEOWNERS" \
  's{\Q — docs/spec/0006-github-workflow.md / docs/adr/0008（accepted）に準拠。\E}{。}'

edit "docs/adr/0009-template-clone-cleanup.md" \
  's{\Q- [ADR 0002: 不足要素補完方針](./0002-template-extension-policy.md)（削除対象）\E}{- ADR 0002: 不足要素補完方針（このクリーンアップで削除済み）};
   s{\Q- [ADR 0008: GitHub scaffolding iteration](./0008-github-scaffolding-iteration.md)（着手ゲートの根拠・削除対象）\E}{- ADR 0008: GitHub scaffolding iteration（着手ゲートの根拠・このクリーンアップで削除済み）}'

# --- 検証 -------------------------------------------------------------------

echo "==> doc frontmatter を検証"
bash scripts/validate-docs.sh >/dev/null && echo "  validate-docs: OK"

echo "==> 削除対象への参照が残っていないか確認"
SLUGS='0002-template-extension-policy|0007-github-operations-model|0008-github-scaffolding-iteration|0006-github-workflow|0001-ai-document-driven-development|0002-template-gap-analysis'
if leftover="$(git grep -nE "$SLUGS" -- . ':!scripts/init-template.sh' 2>/dev/null)"; then
  echo "  警告: 削除対象への参照が残っています。手動で確認してください:" >&2
  echo "$leftover" >&2
else
  echo "  残存参照なし"
fi

# --- 自己削除 ---------------------------------------------------------------

echo "==> クリーンアップ完了。スクリプト自身を削除します。"
echo
echo "次の手順:"
echo "  1. git diff で変更内容を確認"
echo "  2. docs/steering/*, README.md を新プロジェクト向けに記入"
echo "  3. 変更をコミット"
rm -f "$SCRIPT_PATH"
