#!/usr/bin/env python3
"""着手ゲート (implementation gate) — Claude Code PreToolUse hook.

実装/設定ファイル（.md 以外、docs/ と .claude/ を除く）への Write/Edit 着手時に、
着手ゲートの確認をリマインドする。feedback-loop の「最初の砦」（docs/guides/feedback-loop-setup.md）
を実体化し、accepted spec/ADR と人間の明示承認を経ずに実装へ走る事故を抑止する。

非ブロック（exit 0）。additionalContext を返してエージェントの文脈に注意喚起を差し込むだけ。
根拠: docs/adr/0008-github-scaffolding-iteration.md（軸3）/ docs/guides/human-in-the-loop.md
"""
import sys
import os
import json

REMINDER = (
    "着手ゲート: これは実装/設定ファイルへの着手です。続行前に確認 — "
    "(1) 対応する accepted な spec/ADR があるか、"
    "(2) 人間の明示的な着手承認を得たか。"
    "AskUserQuestion の方向選択は着手承認ではありません。"
    "未確認なら手を止めて確認を取ること。"
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # 解析できなければ黙って通す（fail-open: 通常作業を妨げない）

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    cwd = data.get("cwd") or os.getcwd()
    try:
        rel = os.path.relpath(file_path, cwd)
    except Exception:
        rel = file_path
    rel = rel.replace(os.sep, "/")

    # 設計ゲート内の成果物は対象外: docs配下 / .claude配下 / すべての .md（ドキュメント）
    if rel.startswith("docs/") or rel.startswith(".claude/") or rel.endswith(".md"):
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": REMINDER,
        }
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
