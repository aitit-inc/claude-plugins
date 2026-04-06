# Tasks

## 対応済み

### outbound サブエージェントのキックプロンプト改善（2026-04-06）
daily-cycle Step 7 のサブエージェント起動プロンプトを具体化。ファイル読み込み順の明示、営業方針の直接埋め込み、バッチ間の件名パターン引き継ぎを追加。権限は親セッション（`--dangerously-skip-permissions`）から自動継承されるため、mode 指定は不要。

### form-filling.md の「営業お断り」検出時の処理を明確なSQLに修正（2026-04-06）
自然言語だった処理を `query_db.py` の具体的コマンドに置換。outreach_logs + project_prospects + prospects の3テーブル更新を明示。

### wpcf7（Contact Form 7）の既知問題を form-filling.md に追記（2026-04-06）
submit フリーズ → REST API フォールバック、REST API spam 判定 → UI 経由送信の2パターンをエラーハンドリングに追加。

### reCAPTCHA 検出時のステータスとログ記録を明文化（2026-04-06）
outreach_logs に失敗記録、project_prospects は `new` 維持、同一セッション内再試行禁止のルールを明文化。

### outbound の件名A/Bテスト・本文個別化の強化（2026-04-06）
outbound SKILL.md のステップ3に件名バリエーション使い分け・本文全体の個別化の明示的指示を追記。

### evaluate → SEARCH_NOTES フィードバックループ追加（2026-04-06）
evaluate の改善適用ステップに SEARCH_NOTES.md への反応パターン追記を追加。反応が良い業種・セグメントを「次回に試すべき方向性」として build-list に自動フィードバック。

### LinkedIn DM 対応（2026-04-06）
outbound Step 5 に LinkedIn DM 手順を追加（コネクション済みのみ、InMail不使用）。check-results に LinkedIn メッセージ画面の確認手順を追加。strategy-template に SNS ログイン案内を追加。

---

## すぐ進められるタスク

### タスクごとのモデル切り替え
**調査結果: 可能。** agent の frontmatter で `model: sonnet` 等を指定できる。
- `inherit`: 親会話のモデルを継承（デフォルト）
- `sonnet` / `opus` / `haiku`: 明示指定

/daily-cycle が Agent ツールでサブタスクを実行する際、そのエージェント定義に model を指定すれば実現可能。
例: /build-list 用のエージェントを `model: sonnet` にして、コスト削減しつつ十分な品質を確保。
**優先度は低い**（現状の動作に問題はないため）。

---

## 将来対応

### /setup-cron（定期実行の自動設定）
/daily-cycle を毎日自動実行するためのセットアップスキル。
- Mac: LaunchAgent で実装
- Windows: タスクスケジューラで実装
- 代替: /loop スキル（既にプラグインとして存在）を使う手もある

Claude Code の /schedule 機能（Remote Trigger）も選択肢。これなら OS 依存なし。

### Gmail / Google Workspace 非依存化
現状、プラグイン全体が Gmail / GWS に深く依存している。送信だけでなく受信確認・ドラフト作成・通知も影響を受ける。

**Gmail/GWS 依存の全箇所:**

| 機能 | 依存ツール | Gmail なしの場合 |
|------|-----------|-----------------|
| メール送信 (/outbound) | gog CLI | smtplib / Resend で代替可能 |
| 返信確認 (/check-results) | Gmail MCP (search/read) | **代替手段なし** — 他メールプロバイダ用の MCP が存在しない |
| バウンス検出 (/check-results) | Gmail MCP (mailer-daemon検索) | **代替手段なし** |
| 日程調整通知確認 (/check-results) | Gmail MCP (通知メール検索) | **代替手段なし** |
| ドラフト作成 (/check-results) | Gmail MCP (create_draft) | **代替手段なし** |
| 完了通知 (/daily-cycle wrap-up) | gog CLI | smtplib / Resend で代替可能 |

**つまり:**
- gog だけ代替しても、**受信側（check-results）が Gmail MCP に完全依存**しているため、Gmail 以外のメールを使うユーザーは返信確認・バウンス検出・ドラフト作成が全て手動になる
- Resend 等で独自ドメインから送信しても、返信はそのドメインのメールボックスに届く。そのメールボックスを読む手段がない

**対応案（段階的）:**

1. **送信の抽象化（比較的容易）**: send_and_log.py に送信バックエンドを抽象化し、gog / smtplib / Resend を設定で切り替え可能にする。通知メールも同様
2. **受信確認の代替（難易度高）**: IMAP で受信確認する Python スクリプトを作る案はある（smtplib 同様、標準ライブラリの imaplib で可能）。ただし IMAP のセットアップはプロバイダごとに異なり、ユーザーの負担が大きい
3. **現実的な落とし所**: Gmail / GWS ユーザーをプライマリーターゲットとし、非 Gmail ユーザーには「送信は可能だが受信確認は手動」という制限を明記する。/setup の環境チェックで適切に案内済み

### アウトバウンドのドラフトモード（送信せずドラフトのみ）
完全自動送信が怖いユーザー向けに、gmail_create_draft でドラフトだけ作成するモード。
Gmail MCP が必須のため、Gmail 以外のユーザーには対応できない。
CSV エクスポート + 手動送信は UX が悪いのでやらない。

---

## やらない

### Python3 依存をシェルスクリプトに置き換え
全9スクリプトが Python3 で、SQLite操作・JSON処理・重複チェックなど複雑なロジックを含む。
シェルスクリプト化は非現実的で、保守性も大幅に低下する。
Python3 は macOS にプリインストールされており、Windows でも Claude Code / Cursor 利用者はほぼ開発環境があるため、実質的な問題にはならないと判断。

---

## アイディア

（なし）

