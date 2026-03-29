---
name: outbound
description: "This skill should be used when the user asks to \"メールを送って\", \"営業をかけて\", \"アプローチして\", \"営業先に連絡して\", \"アウトバウンドを実行して\", or wants to execute outbound sales. 営業リストの営業先に対してメール送付・フォーム入力・SNS DMを自動で行う。件数指定も可能。"
argument-hint: "<project-directory-name> [件数]"
allowed-tools:
  - Bash
  - Read
  - Write
  - WebFetch
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

**前提:** `${CLAUDE_PLUGIN_ROOT}/references/workspace-conventions.md` の規約に従うこと（data.dbの配置・cdしないルール）。

## 実行手順

### 1. 準備

- プロジェクトディレクトリ名: `$0`（必須）
- アプローチ件数: `$1`（省略時: 全件）

`$0/BUSINESS.md` と `$0/SALES_STRATEGY.md` を読み込み、メッセージングの方針を把握する。

未アプローチの営業先リストをDBから取得する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db list-reachable "$0" "$1"
```

件数の指定がない場合は全件を対象とする。

### 2. 各営業先へのアプローチ

SALES_STRATEGY.mdの「営業チャネル」セクションに記載されたチャネルと優先順位に従う。使わないチャネルが指定されている場合はスキップする。

「営業チャネル」セクションに特に制限がない場合のデフォルト優先順位:

1. **メール** — メールアドレスがある場合
2. **問い合わせフォーム** — フォームURLがある場合
3. **SNS DM** — SNSアカウントがある場合（X/Twitter のみ対応。相手のDM設定により送信不可の場合あり）

1つの営業先につき、利用可能なチャネル全てでアプローチする必要はない。最も効果的な1チャネルで十分。

**SNS DMの注意:** SNS DM は到達率が低い（相手のDM開放設定に依存）。SALES_STRATEGY.mdの「営業チャネル」セクションで優先順位が指定されている場合はそれに従う。SNSが無効化されている場合はスキップする。

**ブラウザツール（claude-in-chrome）が利用できない場合:** フォーム入力・SNS DMは実行不可。メールアドレスがある営業先のみを対象とし、フォーム/SNSのみの営業先はスキップする。スキップした件数は結果レポートで「ブラウザ未接続によりスキップ: N件」として報告する。

### 3. メール送信

`references/email-guidelines.md` のガイドラインに従ってメールを作成する。SALES_STRATEGY.mdの「送信者情報」セクションから送信元メールアドレスと署名を取得する。

`send_and_log.py` でメール送信+ログ記録+ステータス更新を一括で行う:

```bash
echo "<本文（署名含む）>" > /tmp/email_body.txt
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/send_and_log.py data.db \
  --project "$0" \
  --prospect-id <prospect_id> \
  --account "<送信元メールアドレス>" \
  --to "<宛先>" \
  --subject "<件名>" \
  --body-file /tmp/email_body.txt
```

本文が短い場合は `--body-file` の代わりに `--body "<本文>"` も可。

**スクリプトの動作:**
- メールを送信し、結果をDBに記録する（送信+ログ+ステータス更新がアトミック）
- 成功時: outreach_logs (status='sent') に記録し、project_prospects を 'contacted' に更新
- 失敗時: outreach_logs (status='failed', error_message) に記録。ステータスは 'new' のまま維持
- 出力: `{"status": "sent"|"failed", "outreach_log_id": N, "error_message": null|"..."}`

**注意:**
- **メール送信は必ず `send_and_log.py` 経由で行うこと。** gog コマンドを直接叩かない（DBにログが残らなくなるため）
- `--body` / `--body-file` に渡す本文は署名を含めた完全な内容にする
- Gmail MCP（`gmail_create_draft`）はドラフト作成のみで送信不可
- 送信元エイリアスを指定する場合は `--from "<エイリアス>"` を追加

### 4. 問い合わせフォーム入力

claude-in-chromeを使用してフォームに入力する。`references/form-filling.md` の手順に従う。

**送信本文の検証:** outreach_logs に記録する前に、フォームに入力した本文（body）が空でないことを確認する。空の場合は送信失敗として `status = 'failed'`, `error_message = 'body empty'` で記録し、ステータスは `new` のまま維持する。

送信成功時、outreach_logsに記録し、ステータスを更新する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT INTO outreach_logs (project_id, prospect_id, channel, subject, body, status) VALUES (?, ?, 'form', ?, ?, 'sent')" "$0" "<prospect_id>" "<subject>" "<body>"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "UPDATE project_prospects SET status = 'contacted', updated_at = datetime('now') WHERE project_id = ? AND prospect_id = ?" "$0" "<prospect_id>"
```

### 5. SNS DM

claude-in-chromeを使用してSNSでDMを送る。

**手順:**
1. prospects.sns_accounts（JSON）からアカウント情報を取得
2. ブラウザでSNSプロフィールページに移動
3. DMまたはメッセージ機能を使ってメッセージを送る

**メッセージ:** SNS用に短く簡潔にする。SALES_STRATEGY.mdの「SNSメッセージ」セクションを参考に。

送信後、outreach_logsに記録し、ステータスを更新する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT INTO outreach_logs (project_id, prospect_id, channel, subject, body, status) VALUES (?, ?, ?, ?, ?, 'sent')" "$0" "<prospect_id>" "sns_twitter" "" "<body>"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "UPDATE project_prospects SET status = 'contacted', updated_at = datetime('now') WHERE project_id = ? AND prospect_id = ?" "$0" "<prospect_id>"
```

### 6. アプローチ不可の営業先の処理

アプローチに失敗した営業先のうち、**構造的な理由**で今後もアプローチ不可能と判断できる場合は `unreachable` に更新する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "UPDATE project_prospects SET status = 'unreachable', updated_at = datetime('now') WHERE project_id = ? AND prospect_id = ?" "$0" "<prospect_id>"
```

**`unreachable` にすべきケース:**
- メールアドレスが不正でバウンスした（恒久的なエラー）
- SNSのDMが開放されていない
- フォームがB2B問い合わせ用途でなかった
- そもそも利用可能な連絡手段がなかった

**`unreachable` にしないケース（`new` のまま維持）:**
- 一時的なネットワークエラーやタイムアウト
- gog send の認証エラーなどシステム側の問題

### 7. 結果レポート

以下を報告する:
- アプローチした営業先数
- チャネル別の内訳（メール: N件、フォーム: N件、SNS: N件）
- 失敗した件数と理由
- 次のステップとして `/check-results` の実行を案内する
