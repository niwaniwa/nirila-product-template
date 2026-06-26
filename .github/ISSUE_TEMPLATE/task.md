---
name: Task（実装タスク）
about: 実装・リファクタ・ドキュメント等の作業単位。1PRで閉じられる小さい粒度で。
title: ""
labels: ["type:feature"]
assignees: []
---

<!--
このテンプレは docs/spec/0006-github-workflow.md（accepted）に準拠。
原則: 1 Issue = 1 PR で閉じられる小さい単位。大きい機能は親Issue + サブIssueに分割する。
AI Agent に任せる場合は agent:local ラベルを付け、受け入れ条件を「テストで判定できる」形にする。
-->

## 目的

<!-- 何を達成するか・なぜ必要かを1〜2文で -->

## 対応spec

<!-- 実装の契約となる accepted な spec を必ずリンクする。なければ needs-spec ラベルを付ける -->
spec: `docs/spec/NNNN-*.md`

## 受け入れ条件

<!-- spec の受け入れ基準から該当分を転記。機械検証可能（テストで判定できる）が望ましい -->
- [ ] 
- [ ] 既存の振る舞いを壊さない

## 実装方針

<!-- 必要最小限で。シンプルな設計を優先 -->

## テスト方針

- [ ] unit test
- [ ] integration test（必要な場合）

## 触ってよい範囲 / 触ってはいけない範囲

<!-- AI Agent の安全境界。変更してよいパス・変更禁止のパス/設定を明示する -->
- 触ってよい: 
- 触ってはいけない: 
