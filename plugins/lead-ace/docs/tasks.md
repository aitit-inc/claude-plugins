# Tasks

## 対応済み


---

## すぐ進められるタスク

### 🔴 1. outbound サブエージェントのキックプロンプト改善

**問題:**
daily-cycle Step 7 でサブエージェントに outbound を実行させる際、キックプロンプトが「outbound/SKILL.md を読んで従え」という間接的な指示のみ。サブエージェントは新しいコンテキストで起動するため、必要なファイルの読み込み順がブレたり、SALES_STRATEGY.md の A/Bテスト指示が遵守されなかったりする。また、確認なし実行の承認がテキストベースのみで、Agent tool の mode パラメータによる制御がされていない。

**対象ファイル:** `skills/daily-cycle/SKILL.md` の Step 7

**修正内容:**
サブエージェント起動時のプロンプトを以下のように具体化する:

1. **ファイル読み込み順を明示的に指定:**
   - まず `$0/SALES_STRATEGY.md` と `$0/BUSINESS.md` を読み込む（営業方針・送信者情報の把握）
   - 次に `${CLAUDE_PLUGIN_ROOT}/skills/outbound/SKILL.md` を読み込む（実行手順）
   - チャネルに応じて `references/email-guidelines.md` / `references/form-filling.md` を読み込む

2. **キープロンプトに営業方針の要点を直接含める:**
   - 「件名は SALES_STRATEGY.md の件名パターンからランダムに選択すること」
   - 「本文冒頭は相手企業の具体的な特徴・業種に言及すること（汎用挨拶だけは不可）」
   - 「A/Bテスト指示がある場合、バッチ内で複数パターンを均等に使い分けること」

3. **Agent tool の mode パラメータで確認なし実行を保証:**
   - サブエージェントは親セッションの `permissions.allow` を継承する（調査済み）
   - daily-cycle が Agent tool を起動する際に `mode: "auto"` を指定するよう SKILL.md に明記する
   - `auto` mode ではバックグラウンドの安全性チェックのみで、許可済みツールは確認なしで実行される
   - テキストでの「承認済み」記載も引き続き残す（補助的に）
   - /setup スキルで、settings.json の permissions.allow に `Bash`, `mcp__claude_in_chrome__computer`, `mcp__claude_in_chrome__form_input` 等が含まれているか確認するステップを追加する

4. **前バッチの結果を次バッチに引き継ぐ:**
   - 前バッチで使った件名パターンを次バッチのプロンプトに含め、同じパターンの偏りを防ぐ

---

### 🔴 2. form-filling.md の「営業お断り」検出時の処理を明確なSQLに修正

**問題:**
form-filling.md L19-21 の「営業お断り」検出時の処理が自然言語のみで書かれており、テーブル名・カラム名が曖昧。2026-04-06 セッションで AI が `project_prospects.do_not_contact`（存在しないカラム）を更新しようとしてエラーが発生した。また、`project_prospects.status` の更新が指示に含まれていないため、次回 outbound で同じ営業先が再抽出される。

**対象ファイル:** `skills/outbound/references/form-filling.md`

**修正内容:**
L18-21 のセーフティネット処理を以下の明示的 SQL に置換:

```sql
-- 営業お断り検出時（3テーブルを更新）
INSERT INTO outreach_logs (project_id, prospect_id, channel, subject, body, status, error_message)
  VALUES (?, ?, 'form', '', '', 'failed', '営業お断りの記載あり');
UPDATE project_prospects SET status='unreachable', updated_at=datetime('now')
  WHERE project_id=? AND prospect_id=?;
UPDATE prospects SET do_not_contact=1, notes='営業お断りの記載あり（フォームページ）', updated_at=datetime('now')
  WHERE id=?;
```

ポイント:
- `outreach_logs`: 失敗ログを記録（channel='form'）
- `project_prospects`: status を `unreachable` に更新（再抽出防止）
- `prospects`: `do_not_contact=1` をグローバルに設定（全プロジェクトで今後アプローチしない）

---

### 🟡 3. wpcf7（Contact Form 7）の既知問題を form-filling.md に追記

**問題:**
2026-04-06 セッションで発見された2パターンが form-filling.md に未文書化のため、AI が毎回試行錯誤する。

**対象ファイル:** `skills/outbound/references/form-filling.md`

**修正内容:**
エラーハンドリングセクション（L30-34）に以下の2パターンを追記:

**パターンA: wpcf7 REST API が spam 判定を返す場合**
- 症状: `POST /wp-json/contact-form-7/v1/contact-forms/{id}/feedback` が `status: 'spam'` を返す
- 原因: REST API 直接呼び出しでは wpcf7 の honeypot / トークン検証に通らない
- 対処: JavaScript で各フィールドに値をセットし、フォームの submit イベントを発火させる（UI経由送信）

**パターンB: submit クリックでブラウザがフリーズする場合**
- 症状: `computer` ツールで送信ボタンをクリック後、CDP タイムアウト（約45秒）でタブが応答不能になる
- 対処: `navigate` でページをリロードし、REST API（`POST /wp-json/contact-form-7/v1/contact-forms/{id}/feedback`）で直接送信する。FormData に `_wpcf7`, `_wpcf7_version`, 各フィールドを含める

**注意:** パターンAとBは逆の対処法。まず UI 経由を試し、フリーズしたら REST API にフォールバックする順序にする。

---

### 🟡 4. reCAPTCHA 検出時のステータスとログ記録を明文化

**問題:**
form-filling.md L33 は「reCAPTCHA等がある場合: スキップしてログに記録」としか書かれていない。outreach_logs の status、project_prospects の status をどうするかが未定義。reCAPTCHA は構造的に送信不可だが、`project_prospects.status` を `new` のまま維持すると永遠に再試行対象になり、`unreachable` にすると将来フォームが改修されて reCAPTCHA が外れた場合に復帰できない。

**対象ファイル:** `skills/outbound/references/form-filling.md`

**修正内容:**
エラーハンドリングの reCAPTCHA 項目を以下に書き換え:

```
reCAPTCHA / hCaptcha 等がある場合:
1. outreach_logs: status='failed', error_message='reCAPTCHAによりスキップ' で記録
2. project_prospects: status は 'new' のまま維持（フォーム改修で解消する可能性があるため）
3. 当該フォームのURLに対して、同一セッション内では再試行しない（他チャネルがあればそちらを試す）
```

理由: `new` のまま維持しても outreach_logs に失敗記録があるため、evaluate で「reCAPTCHA 率」を集計可能。将来的に reCAPTCHA が外れた場合に自動で再試行対象に戻る。同一セッション内での無駄な再試行は outreach_logs の失敗記録で判定して回避する。

---

### 🟡 5. outbound の件名A/Bテスト・本文個別化の強化

**問題:**
outbound SKILL.md L43 に「SALES_STRATEGY.md のA/Bテスト指示に従うこと」と書いてあるが、実際の実行では毎回同じ件名が使われ、本文の冒頭1行だけの差し替えでテンプレ感が強い。

**対象ファイル:** `skills/outbound/SKILL.md`, `skills/outbound/references/email-guidelines.md`

**修正内容:**

outbound SKILL.md のステップ3（メール送信）付近に以下を追記:
- 「件名は SALES_STRATEGY.md の件名パターンから**ランダムに選択**すること。Python の `random.choice` 等でバッチごとに異なるパターンを使う」
- 「本文の冒頭は相手企業の**具体的な特徴・業種・最近の取り組み**に言及すること。汎用的な挨拶（"貴社のウェブサイトを拝見し"等）だけでは不十分」

email-guidelines.md にも同様の強化指示がある場合はそちらも更新する。

**備考:** Issue 1（サブエージェントのキックプロンプト改善）でファイル読み込み順の明示・A/Bテスト指示の直接埋め込みを行うため、この問題も一定程度改善される。Issue 1 の対応後に効果を確認してから着手してもよい。

---

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

build-listで探すときのテクニックとして、これまで反応があった会社・組織と近い会社や競合などを探すのはありかも。
strategyで最初に戦略作るときにやることか？build-listか？それともevaluateか？

X/LinkedIn対応！！（claude in Chromeでやって、ってかくぐらいだと思うけど。）
・あとは、strategyの時に、chromeでXとLinkedInのアカウントにログインしておいて、って言うぐらいかな？

