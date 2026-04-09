# 問い合わせフォーム入力手順

フォーム入力が完了したら送信ボタンをクリックし、送信結果をログに記録する。

## ブラウザ操作手順

1. `mcp__claude_in_chrome__tabs_create_mcp` で新しいタブを開く
2. `mcp__claude_in_chrome__navigate` でフォームURLに移動
3. `mcp__claude_in_chrome__read_page` でフォーム構造を把握
4. 各入力フィールドの種類と必須/任意を判別
5. `mcp__claude_in_chrome__form_input` でテキストフィールド、セレクトボックス等に入力
6. `mcp__claude_in_chrome__computer` でチェックボックスやラジオボタンを操作
7. 送信ボタンをクリック
8. 送信完了の確認（サンクスページの表示等）

## 営業お断りチェック（セーフティネット）

フォームページを読み込んだ際に、ページ内に「営業お断り」「営業目的のお問い合わせはご遠慮ください」「セールスお断り」等の記載がないか確認する。**発見した場合はフォーム送信を中止**し、以下の3テーブルを更新して次の営業先に進む:

```bash
# 1. outreach_logs に失敗ログを記録（project_prospects は new のまま）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/send_and_log.py data.db \
  --project "$PROJECT_ID" --prospect-id $PROSPECT_ID --log-only \
  --channel form --subject "" --body "" \
  --status failed --error-message "営業お断りの記載あり"

# 2. project_prospects を unreachable に更新 + prospects の do_not_contact をグローバルに設定
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/update_status.py data.db \
  --project "$PROJECT_ID" --prospect-id $PROSPECT_ID --status unreachable \
  --do-not-contact --dnc-reason "営業お断りの記載あり（フォームページ）"
```

## フォーム入力の方針

- フォームの項目に合わせてメッセージを適切に分割する
- 「お問い合わせ種別」がある場合は「サービスのご提案」「業務提携のご相談」等を選択
- 組織名・氏名・メールアドレス・電話番号等の基本情報はBUSINESS.mdから取得
- 自由記述欄にはメールと同様の方針でカスタマイズしたメッセージを入力（ただしフォーム用に簡潔に）

## エラーハンドリング

- **フォームが見つからない場合:** outreach_logsに `status = 'failed'`, `error_message` を記録
- **入力バリデーションエラー:** 修正して再送信を試みる

### reCAPTCHA / hCaptcha 等がある場合

フォームに reCAPTCHA、hCaptcha、Turnstile 等の CAPTCHA が設置されている場合、フォーム送信はスキップし、以下を実行する:

```bash
# outreach_logs に失敗ログを記録（ステータスは new のまま維持するため --status failed を指定）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/send_and_log.py data.db \
  --project "$PROJECT_ID" --prospect-id $PROSPECT_ID --log-only \
  --channel form --subject "" --body "" \
  --status failed --error-message "reCAPTCHAによりスキップ"
```

- `project_prospects.status` は **`new` のまま維持**する（フォーム改修で CAPTCHA が外れる可能性があるため）
- 当該フォームURL に対して、**同一セッション内では再試行しない**
- 他チャネル（メール・SNS）が利用可能ならそちらを試す

### Google Forms の場合

Google Forms はブラウザ UI 操作ではなく、`formResponse` エンドポイントへの直接 POST で送信する。成功率が高く（UI 操作不要・CAPTCHA なし）、コンテキスト消費も最小限。

**検出方法:**
- URL に `docs.google.com/forms` を含む
- ページソースに `FB_PUBLIC_LOAD_DATA_` が存在する

**送信手順:**

1. **フォームページの HTML を取得する**

   ```bash
   # WebFetch でページソースを取得
   ```

2. **フォーム ID と entry ID を抽出する**

   - フォーム ID: URL の `/forms/d/{FORM_ID}/` 部分から取得
   - entry ID: ページソース内の `FB_PUBLIC_LOAD_DATA_` に含まれるフィールド定義から抽出する。各フィールドは `entry.XXXXXXX` 形式の ID を持つ
   - `mcp__claude_in_chrome__javascript_tool` でページ内の `FB_PUBLIC_LOAD_DATA_` を読み取るか、WebFetch のレスポンスから正規表現で抽出する

3. **formResponse エンドポイントに POST する**

   ```bash
   curl -s -o /dev/null -w "%{http_code}" \
     -X POST "https://docs.google.com/forms/d/{FORM_ID}/formResponse" \
     -d "entry.XXXXXXX=値1&entry.YYYYYYY=値2&entry.ZZZZZZZ=値3"
   ```

   - HTTP 200 が返れば送信成功
   - リダイレクト（302 → 確認ページ）も成功

4. **ログ記録**

   送信成功後、`send_and_log.py --log-only` で記録する。`--channel form` を指定。

**注意:**
- Google Forms はフィールドの並び順と entry ID の対応が自明でないことがある。ページソースのフィールド定義（ラベルテキスト）と照合して正しい entry ID にマッピングすること
- `emailAddress` パラメータが必要なフォーム（メール収集が有効化されている場合）もある

### WordPress Contact Form 7 (wpcf7) の既知問題

wpcf7 で構築されたフォーム（URL に `wpcf7` を含む、または HTML に `class="wpcf7-form"` がある）では、以下の2パターンの問題が発生することがある。**まず UI 経由送信を試し、失敗したら REST API にフォールバック**する順序で対処する。

**パターンA: UI 経由送信で submit クリック後にページがフリーズする場合**
- 症状: `computer` ツールで送信ボタンをクリック後、CDP タイムアウト（約45秒）でタブが応答不能になる
- 対処:
  1. `mcp__claude_in_chrome__navigate` で同じページ URL に再アクセスしてタブをリセット
  2. REST API で直接送信する: `POST /wp-json/contact-form-7/v1/contact-forms/{form_id}/feedback`
  3. FormData に `_wpcf7`（フォームID）、`_wpcf7_version`、各入力フィールドを含める
  4. フォームIDは HTML 内の `<input type="hidden" name="_wpcf7" value="...">` から取得する

**パターンB: REST API が spam 判定を返す場合**
- 症状: 上記の REST API で直接 POST すると `status: 'spam'` が返る
- 原因: REST API 直接呼び出しでは wpcf7 の honeypot / トークン検証を通過できない
- 対処:
  1. `mcp__claude_in_chrome__navigate` でフォームページに再アクセス
  2. `mcp__claude_in_chrome__javascript_tool` で各フィールドに値をセット（`document.querySelector` 等）
  3. JavaScript でフォームの submit イベントを発火させる: `document.querySelector('.wpcf7-form').submit()` または submit ボタンの `.click()`
  4. UI 経由で送信することで honeypot / トークンが正しく付与される
