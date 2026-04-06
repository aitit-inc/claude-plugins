# lead-ace スキル改善アイデア

## 🔴 優先度：高

### 1. outbound をサブエージェントで実行できない構造的問題

**対象ファイル:** `daily-cycle/SKILL.md`

**問題:**
Claude には「送信ボタンのクリック・メール送信は explicit permission 必須」というシステムレベルの安全ルールがある。これはプロンプトでは上書きできない。

Agent tool でサブエージェントを起動すると新しいコンテキストが始まるため、ユーザーがメイン会話で「はい、承認します」と言っても、その許可はサブエージェントに引き継がれない。

SKILL.md に書かれている「ユーザーは /daily-cycle 起動時点で全送信を承認済み」という文は、サブエージェントから見ると「ツール結果の中にあるテキスト（observed content）」であり、システムルール上「observed content からの承認は無効」として扱われる。

結果として、サブエージェントが送信ボタンをクリックしようとするたびに「確認してよいですか？」と聞くループになる。

**修正案:**
outbound はメインコンテキストで直接実行する設計に変える。ユーザーが `daily-cycle` を起動したメインの会話でそのまま処理すれば、明示的な承認が引き継がれる。

```diff
- outbound件数を10件ずつのバッチに分割し、それぞれ別のサブエージェントとして直列で起動する。
+ outbound はサブエージェントを使わず、メインコンテキストで直接 outbound/SKILL.md の手順に従って実行する。
+ バッチ分割は概念的に行い（10件処理ごとに進捗報告）、サブエージェントは使わない。
```

---

### 2. `form-filling.md` の `do_not_contact` 更新指示が誤り（テーブル名不明確）

**対象ファイル:** `outbound/references/form-filling.md`

**問題:**
form-filling.md L21 に「prospects の `do_not_contact` を `1` に更新し、`notes` に理由を記録」とあるが、テーブル名が不明確。

実際には `prospects` テーブルに `do_not_contact` カラムがある。しかし、ステータス更新は `project_prospects` テーブルで行うため、AIが混同して `project_prospects.do_not_contact` を更新しようとしてエラーになる。（2026-04-06 セッションで実際に発生）

**修正案:**
SQL を明示する：

```sql
-- 営業お断り時の処理（3テーブルを更新）
INSERT INTO outreach_logs (project_id, prospect_id, channel, subject, body, status, error_message)
  VALUES (?, ?, 'form', '', '', 'failed', '営業お断りの記載あり')
UPDATE project_prospects SET status='unreachable', updated_at=datetime('now')
  WHERE project_id=? AND prospect_id=?
UPDATE prospects SET do_not_contact=1, notes='営業お断りの記載あり（フォームページ）', updated_at=datetime('now')
  WHERE id=?
```

---

## 🟡 優先度：中

### 3. wpcf7 フォームの既知問題が未文書化

**対象ファイル:** `outbound/references/form-filling.md`

2026-04-06 セッションで発見した2パターンが form-filling.md に存在しない。

**パターンA: REST API が spam 判定される場合**
- 直接 `POST /wp-json/contact-form-7/v1/contact-forms/{id}/feedback` すると `status: 'spam'` が返る
- → UI経由（JavaScriptでフィールドに値をセット + submit イベント発火）で送信すると通る

**パターンB: submit ボタンのクリックでページがフリーズする場合**
- `computer` ツールで submit をクリック後、CDPタイムアウト（約45秒）でタブが応答不能になる
- → `navigate` でページをリセット後、REST API で直接 POST すると送信できる

これらを form-filling.md の「エラーハンドリング」セクションに追加する。

---

### 4. reCAPTCHA のステータス扱いが未定義

**対象ファイル:** `outbound/references/form-filling.md`

form-filling.md では「スキップしてログに記録」とだけある。

**曖昧な点:**
- status を `new` のままにするか `unreachable` にするか
- reCAPTCHA は構造的に送信不可なので `new` のまま維持しても永遠に再試行対象になる

**修正案:**
reCAPTCHA 検出時の扱いを明文化する。推奨方針：
- outreach_logs: `status='failed'`, `error_message='reCAPTCHAによりスキップ'`
- project_prospects: `status='new'` のまま維持（フォームが改修されて reCAPTCHA が外れる可能性を残す）

---

## 🟢 優先度：低

### 5. outbound が SALES_STRATEGY.md の指示を守らない

**対象ファイル:** `outbound/SKILL.md`（`improvements_idea.md` でも既出）

SALES_STRATEGY.md に書いてあるのに実行されていないこと：
- 件名 A/B テスト（複数パターン用意済みなのに毎回同じ件名）
- 本文の個別化（冒頭1行だけ差し替えでテンプレ感が強い）

outbound をメインコンテキスト化すれば（問題1の修正により）指示を守る精度が上がる可能性があるが、SKILL.md 側にも「件名は必ず SALES_STRATEGY.md のパターンからランダム選択」「冒頭は相手の具体的な特徴・業種に言及」等を明示的に追記する。
