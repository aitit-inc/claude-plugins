# スキル改善アイデア

daily-cycle 実行（2026-03-28 speech-monster）を通じて発見した改善ポイント。
スキルは全プロジェクト共通なので、個別事業固有の改善は含めない。

---

## 1. 業務の全体的な進め方

### 1a. build-list → outbound の順序を逆にすべきケースへの対応

現状の daily-cycle はステップ4でリスト残数を確認し、残があればまず outbound → 必要なら build-list の順。しかしリスト残数が少ない場合（今回は6件）、少数を outbound してから build-list するより、先に build-list でリストを充填してから outbound した方が効率的。

**改善案:** ステップ4のリスト残数が outbound 指定件数の 1/3 未満の場合、outbound より先に build-list を実行する。その後、充填されたリストから outbound を実行する。

### 1b. build-list で登録した件数と reachable 件数の乖離

今回30件候補収集 → 29件DB登録したが、reachable は10件しか増えなかった。約19件は連絡先なし（email/form/SNS全てnull）または SNS のみで事実上 unreachable。候補収集の労力に対して実際にアプローチ可能な件数が少なすぎる。

**改善案:**
- build-list の完了レポート（ステップ8）に「reachable 内訳」を追加する（email有: N件、form有: N件、SNSのみ: N件、連絡先なし: N件）
- daily-cycle のステップ6で build-list 完了後に count-reachable を再チェックし、まだ不足なら追加の build-list を実行する判断を入れる
- build-list の目標件数を「登録件数」ではなく「reachable 件数」ベースにする（例: reachable 30件を目標に、連絡先なし分を見越して多めに候補収集する）

---

## 2. 特定のスキルの指示内容

### 2a. daily-cycle ステップ6d: JSON マージが手動で脆弱

現状: 6a（候補収集）の出力と 6c（連絡先取得）の出力を、メインコンテキストで手動マージして `add_prospects.py` に渡す。今回も30件中1件をマージ漏れした。

**問題の根本:** 6a は `{company_name, website_url, overview, industry, match_reason, priority}` を返し、6c は `{company_name, website_url, email, form_url, sns_url}` を返す。この2つのJSON配列を company_name で突き合わせてマージする作業がLLMの手作業になっている。

**改善案:**
- `merge_prospects.py` スクリプトを作成する。6a の出力JSONファイルと 6c の出力JSONファイルを受け取り、company_name + website_url で突き合わせてマージ済みJSONを出力する
- または、6c のサブエージェントに 6a の全フィールドも渡して、マージ済みの完全なJSONを返させる（enrich-contacts.md のリファレンスは既にこれを想定しているが、daily-cycle の 6c プロンプト指示がこれと整合していない）

### 2b. daily-cycle ステップ6b: 重複フィルタもスクリプト化すべき

現状: `all-prospect-identifiers` の結果と 6a の候補を、メインコンテキストで手動突き合わせしている。候補が増えると見落としリスクが高い。

**改善案:** `filter_duplicates.py` スクリプトを作成。6a の候補JSON と DB の既存一覧を突き合わせ、新規分のみをフィルタして出力する。

### 2c. build-list の priority スケールが不統一

- `build-list/SKILL.md` ステップ5: 優先度を 1-5（数値）で定義
- `daily-cycle/SKILL.md` ステップ6a: サブエージェントに `priority` を返させるが、フォーマット指定がない

実際の実行では 6a のサブエージェントが "high/medium/low" を返し、`add_prospects.py` が期待する数値と不一致になる可能性がある（今回は add_prospects.py が文字列を受け入れたが、DBスキーマ的に数値が正しいはず）。

**改善案:** daily-cycle の 6a プロンプトで明示的に `priority: 1-5 の数値` と指定する。または add_prospects.py 側で "high"→1, "medium"→3, "low"→5 の変換を入れる。

### 2d. enrich-contacts の出力スキーマと add_prospects.py の入力スキーマが不一致

- enrich-contacts は `form_url`, `sns_url`, `sns_type` を返す
- add_prospects.py は `contact_form_url`, `sns_accounts`（JSON object）を期待する

フィールド名の変換もLLMの手作業になっている。

**改善案:** どちらかに統一する。理想は enrich-contacts の出力が add_prospects.py にそのまま渡せるスキーマにすること。

### 2e. count-reachable が SNS のみの営業先を reachable としてカウントする

現状のクエリは `email OR form_url OR sns_accounts` のいずれかがあれば reachable。しかし実際には SNS（特に X/Twitter）の DM は開放されていないケースが多く、事実上 unreachable になる。今回も SNS のみの3件中3件が unreachable だった。

**改善案:** count-reachable のクエリを見直す。以下のいずれか:
- SNS のみの営業先は reachable にカウントしない（`email OR form_url` に限定）
- `count-reachable` と別に `count-reachable-reliable`（email/form のみ）クエリを追加し、daily-cycle はこちらを参照する

### 2g. daily-cycle ステップ8: 通知設定が SALES_STRATEGY.md のテンプレートに未定義

`strategy` スキルで生成する SALES_STRATEGY.md のテンプレートに「通知設定」セクションが存在しない。daily-cycle は毎回このセクションを探して見つからずスキップする。

**改善案:** `strategy` スキルのテンプレートに「通知設定」セクションを追加する（デフォルト値: なし）。

---

## 3. スクリプト化すべきもの

| スクリプト名 | 目的 | 現状の問題 |
|---|---|---|
| `merge_prospects.py` | 候補JSON + 連絡先JSONをマージ | 手動マージでの漏れ・フィールド名変換ミス (2a, 2d) |
| `filter_duplicates.py` | 候補JSONからDB既存分を除外 | 手動突き合わせの精度・コンテキスト消費 (2b) |
| `is_business_day_elapsed.py` | 2つの日付間の営業日数を計算 | LLMの日付計算は不正確になりうる（祝日考慮なし等） |

これらをスクリプト化すると、daily-cycle のステップ6全体がほぼ機械的に実行でき、LLMの判断ミスによる漏れ・不整合が減る。

### 最終的な理想形: build-list パイプライン

```
候補収集（サブエージェント）
  → filter_duplicates.py（スクリプト）
  → 連絡先取得（サブエージェント × バッチ）
  → merge_prospects.py（スクリプト）
  → add_prospects.py（スクリプト、既存）
```

各ステップの入出力がJSON配列で統一されていれば、パイプラインとして安定して動く。

---

## 4. その他

### 4a. 大企業向けフォームの品質問題

大企業（生保・不動産等）の問い合わせフォームは「ご意見・ご要望」「チャット窓口」等、B2B営業には不適切なものが多い。enrich-contacts の「不適切なフォーム」の定義はあるが、「ご意見・ご要望フォーム」「チャット窓口」が含まれていない。

**改善案:** enrich-contacts.md の「不適切なフォーム」リストに以下を追加:
- 「ご意見・ご要望」「お客様の声」等のフィードバック用フォーム
- チャットのみの窓口（URLを保存しても自動入力できない）
- 保険契約者・既存顧客専用の問い合わせフォーム

### 4b. build-list Phase 1 で大企業を候補に入れるリスクの明示

大企業は知名度が高く検索上位に出やすいため候補に入りやすいが、実際にはメールアドレスが非公開で汎用フォームしかなく、到達率が低い。Phase 1 の探索ガイドラインに「連絡先取得の容易さ」を判断基準の一つとして追加すべき。

**改善案:** build-list SKILL.md のステップ5（優先度判定）に、連絡先到達性の考慮を追加。「代表メールアドレスが公開されている可能性が低い大企業は、優先度を1段階下げることを検討する」等。ただし、これはあくまでヒューリスティックであり、大企業でもB2B向けフォームが充実しているケースもあるため、厳密なルールにはしない。

### 4c. outbound バッチサイズ10件の妥当性

今回は reachable 6件で1バッチ完了。10件バッチ × 直列は、1バッチあたりの所要時間が長い（約10分）。一方、バッチサイズを小さくすると起動オーバーヘッドが増える。現状の10件は妥当だが、将来的にバッチサイズを設定可能にしてもよい。
