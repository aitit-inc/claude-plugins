---
name: strategy
description: "This skill should be used when the user asks to \"戦略を策定して\", \"営業方針を作って\", \"ビジネス情報をまとめて\", \"SALES_STRATEGY.mdを生成して\", or wants to create/update sales and marketing strategy. 事業情報を対話的に収集し、BUSINESS.mdとSALES_STRATEGY.mdを自動生成する。"
argument-hint: "<project-directory-name>"
allowed-tools:
  - Bash
  - Read
  - Write
  - WebSearch
  - WebFetch
  - AskUserQuestion
---

# Strategy - 営業・マーケ戦略策定

事業・サービス情報をユーザーから収集し、営業戦略ドキュメントを自動生成するスキル。

## 実行手順

### 1. プロジェクト確認

- プロジェクトディレクトリ名: `$0`（必須）

`$0` ディレクトリが存在することを確認する。存在しない場合は `/setup` の実行を案内する。

### 2. 既存ファイル確認

`$0/BUSINESS.md` と `$0/SALES_STRATEGY.md` の存在を確認する。既にある場合は内容を読み込み、更新モードで動作する。

### 3. 情報収集

AskUserQuestionを使い、以下の情報を対話的に収集する。ユーザーには雑に・箇条書きで入力してもらって構わない旨を伝える。一度に全部聞かず、まず最も重要な項目を聞く:

**最初に聞く項目:**
- 事業・サービス・製品の概要（何をしている組織か、何を売りたいか）
- ターゲット顧客（誰に売りたいか）

**追加で聞く項目（必要に応じて）:**
- サービスの特徴・セールスポイント・差別化ポイント
- 競合情報
- 価格帯
- 現在の課題や悩み

**後段の処理で必須の情報（必ず聞く）:**
- 組織の電話番号（問い合わせフォーム入力時に必要になることがある）
- 送信者名（メールの差出人名）
- 送信元メールアドレス（営業メールを送るアカウント）
- 署名情報（組織名・氏名・役職・電話番号・URL等）
- 日程調整リンク（Timerex等のURL。なければ「なし」と記録）
- 反応の定義: 何を「反応あり」とみなすか（直接返信、日程調整完了通知、フォーム経由の返信 等）
- 使用中の日程調整サービス名（Timerex / Calendly / TimeRex 等。通知元メールアドレスがわかれば併記）
- daily-cycle完了時の通知先メールアドレス（不要なら「なし」）

これらはoutbound/check-results/daily-cycleで必須なので、ユーザーが「お任せ」と言った場合でも確認する。

ユーザーが「それで十分」「あとはお任せ」等と言った場合は、上記必須項目以外は得られた情報で進める。

### 4. Web調査（補足）

ユーザーから得た情報を補完するため、必要に応じてWebSearchで市場・競合情報を調査する。

### 5. BUSINESS.md 生成

`references/business-template.md` のテンプレートに従って `$0/BUSINESS.md` を生成する。

### 6. SALES_STRATEGY.md 生成

`references/strategy-template.md` のテンプレートに従って `$0/SALES_STRATEGY.md` を生成する。

### 7. 完了報告

生成した2ファイルの概要を報告し、次のステップとして `/build-list` の実行を案内する。
