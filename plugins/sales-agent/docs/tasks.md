# Tasks

## 対応済み

### commit & push
daily-cycle のステップ10で `git add . && git commit && git push` が実装済み。

### 自動改善の仕組み
/evaluate で実装済み。送信30件以上 & 最終送信から3営業日以上経過で戦略更新が発動する。
分析観点: 反応率（チャネル別/優先度別）、メッセージ感情分析、ターゲットセグメンテーション、チャネル効果比較。
改善履歴は evaluations テーブルに蓄積され、過去に失敗した施策の再適用を回避する仕組みもある。

### lead-machine テンプレート取り込み（2026-04-05 対応）
lead-machine の30個のプロンプトテンプレートを分析し、以下のリファレンスファイルに統合:
- `skills/strategy/references/industry-email-templates.md` — 業界別メール（B-1〜B-10）の要点をカテゴリ別に整理。/strategy でメッセージング生成時に自動参照
- `skills/strategy/references/targeting-guide.md` — ペルソナ設計・競合分析・USP・チャネル選定・KPI・検索キーワード設計（A-1〜A-5, C系）を凝縮
- `skills/evaluate/references/analysis-frameworks.md` — 返信率低下の6観点分析、A/Bテスト設計、ターゲティング精度検証（D-1〜D-3）
- /strategy SKILL.md のステップ6で上記リファレンスを参照するよう更新
- /evaluate SKILL.md のステップ3で analysis-frameworks.md を参照するよう更新

### /strategy で既存プロジェクト参照（2026-04-05 対応）
- /strategy SKILL.md のステップ2に「他プロジェクトの参照」を追加
- `list-projects` コマンドを sales_queries.py に追加
- 2つ目以降のプロジェクト作成時、既存の BUSINESS.md / SALES_STRATEGY.md を参考にできる

### 返信へのドラフト作成（2026-04-05 対応）
- /check-results SKILL.md にステップ6「返信ドラフト作成」を追加
- allowed-tools に `mcp__claude_ai_Gmail__gmail_create_draft` を追加
- ポジティブ/ニュートラルな返信に対して、内容に応じたドラフトを自動作成（送信はしない）
- 結果レポートにドラフト作成数を報告
- /daily-cycle のサブエージェントサマリーにもドラフト数を追加

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
