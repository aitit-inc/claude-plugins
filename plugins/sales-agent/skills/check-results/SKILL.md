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

**前提:** `${CLAUDE_PLUGIN_ROOT}/references/workspace-conventions.md` の規約に従うこと（data.dbの配置・cdしないルール）。

## 実行手順

### 1. 準備

- プロジェクトディレクトリ名: `$0`（必須）

`$0/SALES_STRATEGY.md` を読み込み、「反応の定義」セクションから以下を把握する:
- 何を「反応」とみなすか
- 使用中の日程調整サービスと通知元メールアドレス
- その他の反応シグナル

### 2. 直近のアプローチ情報を取得

直近4営業日以内に送信したアプローチのメタデータを取得する（本文は不要）:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db recent-outreach "$0"
```

### 3. 受信メールの確認

Gmail MCPを使い、以下の検索を行う:

**3a. 直接返信の検索**

各アプローチ済み営業先について、送信先メールアドレスの**ドメイン**で検索する（同じ組織の別の人から返信が来るケースに対応）:

1. `mcp__claude_ai_Gmail__gmail_search_messages` で `from:@<domain> newer_than:4d` を検索
2. ヒットがあれば `mcp__claude_ai_Gmail__gmail_read_message` で内容を確認
3. 内容がアプローチに対する反応かどうかを判定する

**3b. 日程調整通知の検索**

SALES_STRATEGY.mdに日程調整サービスが記載されている場合、その通知元アドレスからのメールを検索する:

1. `mcp__claude_ai_Gmail__gmail_search_messages` で `from:<通知元アドレス> newer_than:1d` を検索
2. ヒットがあれば内容を読み、通知本文に含まれる名前・メールアドレス・組織名をアプローチ済みリストと突き合わせる

**3c. バウンスメールの検索**

送信失敗（宛先不明、ドメイン不在等）を検出する:

1. `mcp__claude_ai_Gmail__gmail_search_messages` で `from:mailer-daemon OR from:postmaster newer_than:4d` を検索
2. ヒットがあれば `mcp__claude_ai_Gmail__gmail_read_message` で内容を確認
3. バウンスしたメールアドレスをアプローチ済みリストと照合し、該当する営業先を特定する

**3d. 突き合わせ（マッチング）**

受信メールをアプローチ済み営業先と紐づける。以下の優先順位で照合する:
1. **送信先アドレス完全一致**: 送った相手からの直接返信
2. **ドメイン一致**: 同じ組織の別の人からの返信（例: `contact@co.jp` に送信 → `tanaka@co.jp` から受信）
3. **組織名一致**: メール本文や送信者名にアプローチ済み営業先の `company_name` が含まれる（グループ会社や法人事務局からの返信に対応）
4. **日程調整通知**: 通知メール本文にアプローチ済み営業先の名前またはメールアドレスが含まれる

マッチの確信度が低い場合はレポートに「要確認」と記載し、ユーザーの判断に委ねる。

### 4. SNS反応の確認

SNSでDMを送った営業先について、claude-in-chromeで返信を確認する。

1. SNSアカウントのDM/メッセージ画面を開く
2. 返信の有無を確認
3. 返信があれば内容を取得

**ブラウザ拡張が未接続の場合:** SNS確認はスキップするが、SNS経由でアプローチした営業先のうち未確認の件数をカウントしておく。結果レポート（ステップ5）で「**未確認SNS DM: N件**」として必ず報告する。

### 5. データベース更新

反応があった場合、responsesテーブルに記録する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT INTO responses (outreach_log_id, channel, content, sentiment, response_type) VALUES (?, ?, ?, ?, ?)" "<outreach_id>" "<channel>" "<content>" "<sentiment>" "<type>"
```

反応に応じてproject_prospectsのステータスを更新する:
- ポジティブな返信 → `responded`
- ミーティング依頼/日程調整完了通知 → `responded`
- 明確な拒否 → `rejected`
- バウンス → `inactive`
- 自動返信のみ → `contacted` のまま

**response_type の種別:**
`reply` / `auto_reply` / `bounce` / `meeting_request` / `scheduling_confirmation` / `rejection` 等

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "UPDATE project_prospects SET status = ?, updated_at = datetime('now') WHERE project_id = ? AND prospect_id = ?" "<new_status>" "$0" "<prospect_id>"
```

**送付NGの判定**: 返信内容に「今後の連絡は不要」「配信停止」「連絡しないでください」等のオプトアウトの意思が含まれている場合、prospects に送付NGフラグを立て、notes に理由を記録する。これは全プロジェクト共通で適用される。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "UPDATE prospects SET do_not_contact = 1, notes = ?, updated_at = datetime('now') WHERE id = ?" "<既存のnotesがあれば保持>送付NG: <理由の要約>" "<prospect_id>"
```

単にこのプロジェクトの提案を断っただけ（「今回は見送ります」等）の場合は `project_prospects.status = 'rejected'` のみで、送付NGフラグは立てない。

### 6. 結果レポート

以下を報告する:
- チェックした営業先数
- 反応があった営業先数と内訳（ポジティブ/ニュートラル/ネガティブ）
- 反応率（反応数 / アプローチ数）
- 反応の種別内訳（直接返信 / 日程調整完了 / 等）
- マッチ確度が低い反応があれば「要確認」として一覧表示
- **未確認SNS DM: N件**（SNS確認がスキップされた場合。0件でも明示する）
- 注目すべき返信の要約
- 次のステップとして `/evaluate` の実行を案内する

レポートをプロジェクトディレクトリに `RESULTS_REPORT.md` として保存する（追記モード）。
