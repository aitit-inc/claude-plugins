---
name: check-results
description: "This skill should be used when the user asks to \"返信を確認して\", \"反応をチェックして\", \"結果を見て\", \"メールの返事があるか確認して\", or wants to check outbound outreach responses. メールの返信やSNSの反応を自動チェックしDBに記録する。"
argument-hint: "<project-directory-name>"
allowed-tools:
  - Bash
  - Read
  - Write
  - mcp__claude_ai_Gmail__gmail_search_messages
  - mcp__claude_ai_Gmail__gmail_read_message
  - mcp__claude_ai_Gmail__gmail_read_thread
  - mcp__claude_in_chrome__tabs_context_mcp
  - mcp__claude_in_chrome__tabs_create_mcp
  - mcp__claude_in_chrome__navigate
  - mcp__claude_in_chrome__read_page
  - mcp__claude_in_chrome__get_page_text
---

# Check Results - 結果収集

アウトバウンド営業の反応を自動チェックし、データベースに記録するスキル。

## 実行手順

### 1. アプローチ済み企業の取得

ステータスが `contacted` の企業リストとアプローチ履歴を取得する:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "SELECT p.id, p.company_name, p.email, p.sns_accounts, o.id as outreach_id, o.channel, o.subject, o.sent_at FROM prospects p JOIN outreach_logs o ON p.id = o.prospect_id WHERE p.project_id = <id> AND p.status = 'contacted' ORDER BY o.sent_at ASC;"
```

### 2. メール返信の確認

Gmail MCPを使って、送信先からの返信を確認する。

各アプローチ済み企業のメールアドレスについて:
1. `mcp__claude_ai_Gmail__gmail_search_messages` で `from:<email>` を検索
2. アプローチ日時以降の返信があれば `mcp__claude_ai_Gmail__gmail_read_message` で内容を確認
3. 返信内容のセンチメント（positive/neutral/negative）と種別（reply/auto_reply/bounce/meeting_request/rejection等）を判定

### 3. SNS反応の確認

SNSでDMを送った企業について、claude-in-chromeで返信を確認する。

1. SNSアカウントのDM/メッセージ画面を開く
2. 返信の有無を確認
3. 返信があれば内容を取得

### 4. データベース更新

反応があった場合、responsesテーブルに記録する:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "INSERT INTO responses (prospect_id, outreach_log_id, channel, content, sentiment, response_type) VALUES (<id>, <outreach_id>, '<channel>', '<content>', '<sentiment>', '<type>');"
```

反応に応じてprospectsのステータスを更新する:
- ポジティブな返信 → `responded`
- ミーティング依頼 → `responded`
- 明確な拒否 → `rejected`
- バウンス → `inactive`
- 自動返信のみ → `contacted` のまま

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "UPDATE prospects SET status = '<new_status>', updated_at = datetime('now') WHERE id = <id>;"
```

### 5. 結果レポート

以下を報告する:
- チェックした企業数
- 反応があった企業数と内訳（ポジティブ/ニュートラル/ネガティブ）
- 反応率（反応数 / アプローチ数）
- 注目すべき返信の要約
- 次のステップとして `/evaluate` の実行を案内する

レポートをプロジェクトディレクトリに `RESULTS_REPORT.md` として保存する（追記モード）。
