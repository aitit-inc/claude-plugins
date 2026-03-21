---
name: outbound
description: "This skill should be used when the user asks to \"メールを送って\", \"営業をかけて\", \"アプローチして\", \"営業先に連絡して\", \"アウトバウンドを実行して\", or wants to execute outbound sales. 営業リストの営業先に対してメール送付・フォーム入力・SNS DMを自動で行う。件数指定も可能。"
argument-hint: "<project-directory-name> [件数]"
allowed-tools:
  - Bash
  - Read
  - Write
  - WebFetch
  - mcp__claude_ai_Gmail__gmail_create_draft
  - mcp__claude_ai_Gmail__gmail_search_messages
  - mcp__claude_ai_Gmail__gmail_read_message
  - mcp__claude_in_chrome__tabs_context_mcp
  - mcp__claude_in_chrome__tabs_create_mcp
  - mcp__claude_in_chrome__navigate
  - mcp__claude_in_chrome__read_page
  - mcp__claude_in_chrome__get_page_text
  - mcp__claude_in_chrome__find
  - mcp__claude_in_chrome__form_input
  - mcp__claude_in_chrome__computer
  - mcp__claude_in_chrome__javascript_tool
---

# Outbound - アウトバウンド営業実行

営業リストの営業先に対して、メール・問い合わせフォーム・SNS DMで順次アプローチするスキル。全自動で実行する。

## 実行手順

### 1. 準備

プロジェクトディレクトリのBUSINESS.mdとSALES_STRATEGY.mdを読み込み、メッセージングの方針を把握する。

未アプローチの営業先リストをDBから取得する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "SELECT p.id, p.company_name, p.overview, p.email, p.contact_form_url, p.sns_accounts, pp.match_reason, pp.priority FROM prospects p JOIN project_prospects pp ON p.id = pp.prospect_id WHERE pp.project_id = ? AND pp.status = 'new' AND p.do_not_contact = 0 AND (p.email IS NOT NULL OR p.contact_form_url IS NOT NULL OR p.sns_accounts IS NOT NULL) ORDER BY pp.priority ASC, p.id ASC LIMIT ?" "<project_id>" "<件数>"
```

件数の指定がない場合は全件を対象とする。

### 2. 各営業先へのアプローチ

優先度順に、各営業先に対して利用可能なチャネルで順次アプローチする。チャネルの優先順位:

1. **メール** — メールアドレスがある場合
2. **問い合わせフォーム** — フォームURLがある場合
3. **SNS DM** — SNSアカウントがある場合

1つの営業先につき、利用可能なチャネル全てでアプローチする必要はない。最も効果的な1チャネルで十分。ただし、メールアドレスがある場合はメールを優先する。

### 3. メール送信

Gmail MCPを使用してメールを送信する。`references/email-guidelines.md` のガイドラインに従ってメールを作成する。

`mcp__claude_ai_Gmail__gmail_create_draft` でドラフトを作成し、送信する。

送信後、outreach_logsに記録する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT INTO outreach_logs (project_id, prospect_id, channel, subject, body, status) VALUES (?, ?, ?, ?, ?, ?)" "<project_id>" "<prospect_id>" "email" "<subject>" "<body>" "sent"
```

### 4. 問い合わせフォーム入力

claude-in-chromeを使用してフォームに入力する。`references/form-filling.md` の手順に従う。

送信後、outreach_logsに記録する（channel: 'form'）。

### 5. SNS DM

claude-in-chromeを使用してSNSでDMを送る。

**手順:**
1. prospects.sns_accounts（JSON）からアカウント情報を取得
2. ブラウザでSNSプロフィールページに移動
3. DMまたはメッセージ機能を使ってメッセージを送る

**メッセージ:** SNS用に短く簡潔にする。SALES_STRATEGY.mdの「SNSメッセージ」セクションを参考に。

送信後、outreach_logsに記録する（channel: 'sns_twitter' 等）。

### 6. ステータス更新

アプローチ完了した営業先のステータスを更新する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "UPDATE project_prospects SET status = 'contacted', updated_at = datetime('now') WHERE project_id = ? AND prospect_id = ?" "<project_id>" "<prospect_id>"
```

### 7. 結果レポート

以下を報告する:
- アプローチした営業先数
- チャネル別の内訳（メール: N件、フォーム: N件、SNS: N件）
- 失敗した件数と理由
- 次のステップとして `/check-results` の実行を案内する
