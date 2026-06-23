# GitLab / GitHub / アジャイル / スクラム / XP / AI Agent 開発まとめ

# 結論

GitLabもGitHubも、それ自体がアジャイルやスクラムというわけではない。  
どちらも、アジャイル開発・スクラム・カンバン・XPなどを支援できる開発プラットフォームである。

ただし傾向としては、GitLabはアジャイル管理機能が標準でまとまっており、GitHubはIssue / Pull Request / Projects / Actionsを組み合わせて柔軟に運用する。

AI Agentを前提にするなら、スクラムよりもXP的なプラクティス、つまり「小さく作る」「テストで守る」「CIで検証する」「小さいPRでレビューする」といった運用がかなり重要になる。

---

# GitLabとGitHubの対応関係

| GitLab | GitHubでの対応 | 備考 |
|---|---|---|
| Issue | Issue | バグ、タスク、要望、調査などを管理 |
| Weight | Projects の Number field | `Estimate`, `Points`, `Weight` などの数値カスタムフィールドで再現 |
| Milestone | Milestone | リリース、期限、まとまった達成単位 |
| Epic | 親Issue + Sub-issues / Projects / Roadmap | GitLab Epicの完全同等ではないが、階層化は可能 |
| Label | Label | 種別、優先度、領域など |
| Board | Projects の Board view | カンバン的に使える |
| Roadmap | Projects の Roadmap layout | 期間軸で大きめの作業を表示 |
| Sprint | Projects の Iteration field | 1週間・2週間などの反復期間として設定可能 |

---

# GitLabはアジャイルか

GitLab自体がアジャイルなのではなく、アジャイル開発を支援する機能を持つツールである。

GitLabは以下のような機能が揃っているため、アジャイル運用、特にスクラム運用に寄せやすい。

- Issue
- Epic
- Milestone
- Iteration
- Weight
- Issue Board
- Roadmap
- CI/CD
- Release

言い方としては、

> GitLabはアジャイルではないが、アジャイル開発を支援する機能が強い

が正確。

---

# GitHubはアジャイルか

GitHubもアジャイル開発に使える。

ただしGitLabのように、最初からアジャイル管理用語が強く揃っているというより、Issue / Pull Request / Projects / Actionsを組み合わせて、自分たちで運用を設計する色が強い。

GitHubでアジャイル運用する場合は、以下を組み合わせる。

- GitHub Issues
- GitHub Projects
- Milestone
- Label
- Iteration field
- Pull Request
- GitHub Actions
- Roadmap view

---

# アジャイルとスクラムの違い

アジャイルとスクラムは同じではない。

アジャイルは、開発における考え方・価値観・原則である。  
スクラムは、そのアジャイルを実践するための具体的なフレームワークの一つである。

```text
アジャイル
 ├─ スクラム
 ├─ カンバン
 ├─ XP
 └─ その他の手法
```

つまり、

> スクラムはアジャイルの一種だが、アジャイル = スクラム ではない

---

# スクラムとは

スクラムは、アジャイル開発をチームで回すためのフレームワークである。

代表的な要素は以下。

| 要素 | 内容 |
|---|---|
| スプリント | 1〜4週間程度の固定期間 |
| プロダクトバックログ | 作るべきものの一覧 |
| スプリントバックログ | 今回のスプリントで取り組むもの |
| プロダクトオーナー | 何を作るか、優先順位を決める役割 |
| スクラムマスター | スクラムがうまく回るよう支援する役割 |
| 開発者 | 実際に開発する人たち |
| デイリースクラム | 日次の同期 |
| スプリントレビュー | 成果物の確認 |
| レトロスペクティブ | 振り返り |
| インクリメント | スプリントごとの成果物 |

---

# GitLabはスクラムか

GitLab自体はスクラムではない。  
スクラムを運用しやすい機能を持つツールである。

GitLabでスクラムを表現すると以下のようになる。

| スクラムの概念 | GitLabでの対応 |
|---|---|
| Product Backlog | Issue一覧 / Board |
| Sprint Backlog | Iterationに入れたIssue |
| Sprint | Iteration |
| User Story / Task | Issue |
| Story Point | Weight |
| Epic | Epic |
| Product Goal / 大きな機能 | Epic / Roadmap |
| Sprint Board | Issue Board |
| Release | Milestone / Release |

---

# GitHubでスクラムするなら

GitHubでスクラムをやる場合は、GitHub Projectsを中心に組む。

| スクラムの概念 | GitHubでの対応 |
|---|---|
| Product Backlog | GitHub ProjectsのBacklog view |
| Sprint Backlog | `Iteration:@current` のProject view |
| Sprint | Iteration field |
| Story Point | Number field: `Points` |
| Epic | 親Issue / Sub-issues / Roadmap item |
| Task | Issue / Sub-issue |
| Done | Project Status = Done / Issue Close |

GitHub Projectsに作るとよいフィールドは以下。

| Field | 型 | 用途 |
|---|---|---|
| Status | Single select | Todo / In Progress / Review / Done |
| Priority | Single select | P0 / P1 / P2 / P3 |
| Points | Number | GitLab Weight相当 |
| Iteration | Iteration | Sprint相当 |
| Target | Date | 目標日 |
| Area | Single select or Label | frontend / backend / infra など |

---

# XPとは

XPは Extreme Programming の略。  
アジャイル開発手法の一つ。

スクラムがチーム運営・イベント・役割に寄っているのに対して、XPは実装・設計・品質をどう保つかに寄っている。

代表的なプラクティスは以下。

| プラクティス | 内容 |
|---|---|
| TDD | テストを書いてから実装する |
| ペアプログラミング | 2人で1つのコードを書く |
| 継続的インテグレーション | 小さく頻繁に統合する |
| リファクタリング | 振る舞いを変えずに設計を改善する |
| 小さなリリース | 小さい単位で早く出す |
| シンプルな設計 | 今必要な分だけ作る |
| 共同所有 | 特定の人だけが触れるコードを減らす |
| 顧客との密な対話 | 作るものを継続的に確認する |

「Extreme」は、良いとされる開発習慣を極端なレベルまで徹底するという意味。

例:

```text
コードレビューは良い
→ 常時レビューしながら書く
→ ペアプログラミング

テストは良い
→ 実装前にテストを書く
→ TDD

統合は大事
→ 頻繁に統合する
→ CI
```

---

# GitHubでXPするなら

GitHubでXPをやる場合、中心になるのは以下。

- GitHub Issues
- Pull Requests
- GitHub Actions
- Branch protection
- Projects
- Releases

基本フローは以下。

```text
Issue
  ↓
小さいPR
  ↓
GitHub Actionsで自動テスト
  ↓
レビュー
  ↓
mainへマージ
  ↓
必要ならRelease
```

XPのプラクティスとGitHubの対応は以下。

| XPの考え方 | GitHubでの対応 |
|---|---|
| 小さなリリース | 小さいIssue / 小さいPR / Releases |
| TDD | テストコード + GitHub Actions |
| 継続的インテグレーション | GitHub Actions CI |
| ペアプログラミング | Live Share / mob作業 / PR共同作業 |
| コードレビュー | Pull Request review |
| リファクタリング | 小さいPRで継続的に実施 |
| シンプルな設計 | Issueで目的を絞る / PRを小さくする |
| 共同所有 | CODEOWNERSを厳しくしすぎず、誰でも触れる状態にする |
| 顧客との対話 | Issue / Discussions / Projectsで要望管理 |
| 受け入れテスト | IssueのAcceptance Criteria + CI |

---

# GitHubでXPする場合のIssueテンプレート例

```md
## 目的
何を改善するか

## 受け入れ条件
- [ ] xxxの場合にyyyになる
- [ ] 既存のzzzが壊れない

## 実装方針
必要最小限で書く

## テスト
- [ ] unit test
- [ ] integration test
```

---

# GitHub Actionsで最低限回すもの

XPではCIが重要。

最低限、PRごとに以下を回す。

```text
- test
- lint
- typecheck
- build
```

Railsなら例:

```text
- bundle exec rspec
- bundle exec rubocop
- bundle exec brakeman
```

TypeScriptなら例:

```text
- npm run typecheck
- npm run lint
- npm test
- npm run build
```

---

# XPにスプリントは必要か

XPでは、スプリントは必須ではない。

スクラム的な2週間スプリントよりも、XPでは以下が重要。

```text
小さいIssueを切る
小さいPRを出す
CIを必ず通す
毎日mainに近づける
頻繁にリリースする
```

ただし、週単位で区切りたい場合はGitHub ProjectsのIteration fieldを使えばよい。

---

# AI AgentとXPの相性

AI Agent前提の開発は、スクラムよりXP的なプラクティスと相性がよい。

理由は、AI Agentが以下のようなタスクに強いから。

- 小さく明確なIssue
- 完了条件がはっきりした作業
- 既存パターンに沿った実装
- テスト追加
- 小さいリファクタ
- ドキュメント更新
- lint / 型修正
- 小さいバグ修正

これはXPの以下の思想と一致する。

| XPの要素 | AI Agentとの相性 |
|---|---|
| 小さなリリース | Agentに小さいIssueを渡しやすい |
| TDD | Agentの出力をテストで検証できる |
| CI | Agentの変更を自動で落とせる |
| リファクタリング | 低〜中難度の改善をAgentに任せやすい |
| 継続的統合 | AgentのPRを早めにmainへ近づけられる |
| 共同所有 | Agentがコードベース全体を横断しやすい |
| ペアプロ | 人間 + Agent の対話型実装に近い |

---

# AI Agent時代の潮流

現在の潮流は、スクラムからXPへ全面移行というより、以下のような分担に近い。

```text
企画・優先順位・ロードマップ
= Scrum / Kanban / Product Management

実装・品質・統合
= XP / CI / TDD / 小さいPR

AI Agent運用
= Issue駆動 + PR駆動 + CI検証 + Human Review
```

つまり、スクラムは「何を作るか」を決めるために残る。  
XPは「どう安全に速く作るか」の部分でより重要になる。  
AI Agentは「小さい実装単位を高速に処理する存在」として入る。

---

# AI Agent開発の基本フロー

GitHubでAI Agent + XPをやるなら、以下の流れがよい。

```text
1. 人間がIssueを書く
   - 背景
   - 目的
   - Done条件
   - 触ってよい範囲
   - 触ってはいけない範囲
   - テスト方針

2. AgentにIssueを割り当てる

3. Agentがブランチ/PRを作る

4. CIで test / lint / typecheck / build を実行

5. 人間がレビューする

6. 修正指示をPRコメントで出す

7. Agentまたは人間が修正

8. merge
```

---

# AI Agentに向いている作業・向いていない作業

## 向いている

```text
- テスト追加
- ドキュメント更新
- 小さいリファクタ
- 型修正
- lint対応
- 小さいバグ修正
- UIの軽微な調整
- 既存パターンに沿った実装
```

## 向きにくい

```text
- 仕様が曖昧な新機能
- アーキテクチャ変更
- セキュリティ境界の変更
- DB設計変更
- 複雑な非機能要件
- プロダクト判断を含む実装
```

---

# 最終まとめ

GitLab / GitHub / Scrum / XP / AI Agentの関係は、以下のように整理できる。

```text
GitLab
= アジャイル管理機能が標準で強い統合DevOpsプラットフォーム

GitHub
= Issue / PR / Projects / Actionsを組み合わせる柔軟な開発プラットフォーム

アジャイル
= 変化に対応しながら小さく価値を届ける考え方

スクラム
= アジャイルをチーム運営・計画・振り返りで回すフレームワーク

XP
= アジャイルを実装・品質・CI・テストで支える技術プラクティス

AI Agent開発
= XP的な小さいIssue、小さいPR、CI、テスト、人間レビューと相性がよい
```

AI Agent時代に重要なのは、スプリントを細かく管理することよりも、以下を整えること。

```text
- Issueを小さく切る
- Acceptance Criteriaを書く
- テストを書く
- CIを必須にする
- PRを小さくする
- 人間レビューを必須にする
- Agent向け開発ルールを書く
- mainを常に壊さない
```

一言でまとめると、

> AI Agent時代の開発は、上流はScrum/Kanban、実装はXP、実行単位はIssue/PR、品質保証はCIとレビューで支える形になりやすい。
