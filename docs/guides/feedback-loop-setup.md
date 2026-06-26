# フィードバックループ設定ガイド

> 実装品質を高めるための自動フィードバック環境の構築手順

## 概要

フィードバックループの目的は「編集→検出→修正」のサイクルを最短にすること。
Claude Code Hooksを「最初の砦」、CIを「最後の砦」として二重の品質保証を構築する。

**従来**: 編集 → コミット → プッシュ → CI失敗 → 修正（5-10分）
**Hooks**: 編集 → 即座に検出・修正（数秒）

## 前提

- Claude Code がインストール済み
- プロジェクトに `.claude/settings.json` が存在（なければ作成）
- `jq` コマンドが利用可能（`brew install jq` / `apt-get install jq`）

---

## Step 1: 自動フォーマット（PostToolUse）

Claude がファイルを編集するたびにフォーマッターを自動実行する。

`.claude/settings.json` に追加：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

<!-- TODO: プロジェクトのフォーマッターに合わせて変更（prettier / black / rustfmt 等） -->

---

## Step 2: テスト自動実行（PostToolUse）

テストファイルや実装ファイル編集時に関連テストを自動実行する。

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | grep -E '\\.(test|spec)\\.(js|ts)$' | xargs -r npm test -- --findRelatedTests 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

<!-- TODO: プロジェクトのテストランナーに合わせて変更（jest / pytest / cargo test 等） -->

---

## Step 3: 保護ファイルのブロック（PreToolUse）

`.env`、ロックファイル、本番設定ファイルへの意図しない編集を防止する。

`.claude/hooks/protect-files.sh` を作成：

```bash
#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

PROTECTED_PATTERNS=(".env" "package-lock.json" ".git/" "secrets")

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "Blocked: $FILE_PATH matches protected pattern '$pattern'" >&2
    exit 2
  fi
done

exit 0
```

```bash
chmod +x .claude/hooks/protect-files.sh
```

`.claude/settings.json` に追加：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-files.sh"
          }
        ]
      }
    ]
  }
}
```

<!-- TODO: プロジェクトの保護対象パターンを追加 -->

---

## Step 4: タスク完了検証（Stop hook）

Claude が応答を完了する前に、テストがすべて通ることを検証する。

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "Verify that all unit tests pass. Run the test suite and check the results. $ARGUMENTS",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

> **注意**: Stop hookは無限ループの可能性あり。`stop_hook_active` フラグで制御すること。

---

## Step 5: 通知設定（Notification）

Claude が入力待ちの時にデスクトップ通知を受け取る。

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "notify-send 'Claude Code' 'Claude Code needs your attention'"
          }
        ]
      }
    ]
  }
}
```

---

## Step 6: コンテキスト再注入（SessionStart）

コンテキスト圧縮後に重要な情報を再注入する。

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Reminder: Read CLAUDE.md and docs/steering/ before proceeding. Current phase: MVP.'"
          }
        ]
      }
    ]
  }
}
```

---

## 設定の統合例

上記をまとめた `.claude/settings.json` の完全例：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-files.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write 2>/dev/null || true"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "notify-send 'Claude Code' 'Claude Code needs your attention'"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Reminder: Read CLAUDE.md and docs/steering/ before proceeding.'"
          }
        ]
      }
    ]
  }
}
```

---

## CI連携（最後の砦）

Hooksで防げなかった問題をCIで最終チェックする。

<!-- TODO: プロジェクトのCI構成に合わせて設定 -->

基本的なCI項目：

1. **lint / format**: Hooks と同じルールをCIでも実行（差分検出）
2. **テスト**: 全テストスイートの実行
3. **ドキュメントバリデーション**: `bash scripts/validate-docs.sh`
4. **セキュリティスキャン**: 依存関係の脆弱性チェック

---

## 運用のポイント

- **段階的に導入**: まずフォーマットと通知から始め、安定したらテスト自動実行を追加
- **設定のスコープ**: チーム共有は `.claude/settings.json`、個人用は `.claude/settings.local.json`
- **デバッグ**: `Ctrl+O` で詳細モード切替、`claude --debug` で実行詳細確認
- **Hookの確認**: `/hooks` コマンドで現在の設定を一覧表示

## 参考

- [Claude Code Hooks 公式ガイド](https://code.claude.com/docs/ja/hooks-guide)
- [Hooks リファレンス](https://code.claude.com/docs/ja/hooks)
- [公式サンプル集](https://github.com/anthropics/claude-code/tree/main/examples/hooks)
