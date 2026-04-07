---
name: daily-cycle
description: "This skill should be used when the user asks to \"日次サイクルを回して\", \"今日の営業を実行して\", \"デイリーの営業タスクをやって\", \"daily-cycleを実行して\", or wants to run the daily sales automation cycle. check-results → evaluate → outbound + build-list（必要時）を順次・並行で自動実行する。"
argument-hint: "<project-directory-name> [outbound件数=30]"
allowed-tools:
  - Bash
  - Read
  - Agent
---

# Daily Cycle - 日次営業サイクル実行

1日分の営業活動を自動で実行するスキル。全フェーズをサブエージェントで実行し、メインのコンテキストを軽量に保つ。

**前提:** `${CLAUDE_PLUGIN_ROOT}/references/workspace-conventions.md` の規約に従うこと（data.dbの配置・cdしないルール）。サブエージェントへのプロンプトにもこの規約の参照を含めること。

**重要: このスキルは `context: fork` を使わないこと。** サブエージェントのネストは1階層までという制約があるため、daily-cycle自体はメインcontextで動き、各フェーズをAgent toolで起動する必要がある。

**コンテキスト軽量化ルール:**
- サブエージェントは**詳細結果を `$0/.tmp/` 内のファイルに書き出し**、メインには**判断に必要な最小限のサマリー（3行以内）だけ**を返すこと
- 最終レポート・通知・commitは wrap-up サブエージェントが `.tmp/` ファイルを読んで実行する

## 引数

- プロジェクトディレクトリ名: `$0`（必須）
- outbound 件数: `$1`（省略時: 30）

## 実行手順

### 0. プロジェクト登録チェック

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/license.py check-registered "$(pwd)/$0"
```

結果が `NOT_REGISTERED` の場合、「このプロジェクトはセットアップされていません。先に `/setup $0` を実行してください。」と表示して**即座に中断**する。

### 1. 準備

まず現在の正確な日時・曜日を取得する。以降のステップではこの結果を正とする（システムの日付情報より優先）。

```bash
date '+%Y-%m-%d %H:%M (%A)'
```

`$0` ディレクトリの存在と、DBにプロジェクトが登録済みであることを確認する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db project-exists "$0"
```

一時ディレクトリを作成する（サブエージェントの詳細結果保存用）:

```bash
mkdir -p "$0/.tmp"
```

### 2. 前回サイクルレビュー

`$0/DAILY_CYCLE_REPORT.md` が存在する場合、読み込んで以下を把握する:

- 前回の実行日時
- outbound成功率とチャネル内訳（成功率が低かった場合、今回のバッチ戦略に反映）
- build-listの結果（候補不足だった場合、今回は早めにbuild-listを実行する判断材料にする）
- 「次回への申し送り」セクション（システムエラー、中断、要注意事項など）

把握した内容は、以降のステップでサブエージェントに渡すプロンプトに**関連する申し送りがある場合のみ**追記する。例:
- outbound成功率が低かった → ステップ7のサブエージェントに「前回成功率が低かった（XX%）。チャネルYで失敗多発」と伝える
- build-listで候補が少なかった → ステップ8aのサブエージェントに「前回は候補収集でN件しか見つからなかった。SEARCH_NOTES.mdの方向性を変えること」と伝える
- システムエラーがあった → 該当ステップのサブエージェントに警告として伝える

ファイルが存在しない場合（初回実行）はスキップする。

### 3. 開始通知メール（サブエージェント）

Agent toolでサブエージェントを起動し、開始ブリーフィングメールを送信する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- 実行日時: ステップ1で取得した日時
- 前回サイクルの要約: ステップ2で把握した内容（初回実行の場合は「初回実行」と伝える）
- 今回の予定: outbound $1 件、evaluate実行有無の見込み
- `$0/SALES_STRATEGY.md` の「通知設定」セクションから通知先メールアドレスを、「送信者情報」セクションから送信元メールアドレスを取得すること。通知先が「なし」または未設定の場合は何もせず終了すること
- 以下のフォーマットでメールを送信すること:
  - **件名:** `daily-cycle開始: $0`
  - **本文:** 実行日時、プロジェクト名、前回サイクルの要約（outbound成功率・件数、反応数、申し送り事項）、今回の予定
- 送信コマンド: `gog send --account "<送信元>" --to "<通知先>" --subject "daily-cycle開始: $0" --body "<本文>"`
- メインへの返答は **1行のみ**（「開始通知送信済み」または「通知先未設定のためスキップ」または「送信失敗: <理由>」）

送信失敗してもサイクルは続行する（エラーはwrap-upのレポートで報告）。

### 4. check-results（サブエージェント）

Agent toolでサブエージェントを起動し、返信確認を実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/check-results/SKILL.md` を読み込んで、その手順に従うこと
- 詳細結果（反応の内訳、各返信の要約、ドラフト作成結果等）を `$0/.tmp/check-results-summary.md` に書き出すこと
- メインへの返答は **3行以内のサマリーのみ**。例: 「反応3件(positive 2, neutral 1)。ドラフト2件作成。送付NG 0件。」

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 5. evaluate（サブエージェント、条件付き）

前回の evaluate 実行日を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db last-evaluation "$0"
```

前回 evaluate から **3営業日以上経過している場合のみ** サブエージェントを起動する。3営業日未満の場合は「前回evaluateから日が浅いためスキップ」と報告してステップ6に進む。evaluations レコードが存在しない場合（初回）は実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/evaluate/SKILL.md` を読み込んで、その手順に従うこと
- 詳細結果（KPI数値、分析結果、適用した改善内容）を `$0/.tmp/evaluate-summary.md` に書き出すこと
- メインへの返答は **3行以内のサマリーのみ**。例: 「反応率4.2%。メッセージング改善を適用。検索キーワード2件追加。」

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 6. リスト残数を確認し、実行順序を決定

未アプローチ（status = 'new'）の営業先数を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db count-reachable "$0"
```

**実行順序の判定:** リスト残数が outbound 指定件数の **1/3 未満** の場合、outbound より先にステップ8（build-list）を実行してリストを充填する。充填後にステップ7の outbound に戻る。

- リスト残数 ≥ 指定件数の 1/3 → ステップ7（outbound）→ ステップ8（build-list、必要時）
- リスト残数 < 指定件数の 1/3 → ステップ8（build-list）→ ステップ6を再実行 → ステップ7（outbound）
- リスト残数 = 0 かつ build-list 未実行 → ステップ8（build-list）→ ステップ6を再実行 → ステップ7（outbound）

### 7. outbound（サブエージェント × バッチ分割）

**実際のoutbound件数の決定:** `min(指定件数, ステップ6のリスト残数)` を実際のoutbound件数とする。リスト残数が0の場合（ステップ8実行後も0の場合）はoutboundをスキップし、ステップ9に進む。

outbound件数を **10件ずつのバッチ** に分割し、それぞれ別のサブエージェントとして**直列**で起動する。

例: 30件 → 3回のサブエージェント起動（各10件）

各サブエージェントのプロンプトに以下を含める:

```
あなたは outbound 営業を自動実行するエージェントです。
メール送信・フォーム送信・SNS DM 全て、ユーザーへの確認なしで全自動実行してください。
ユーザーは /daily-cycle 起動時点で全送信を承認済みです。

## 実行準備（この順番で必ず読み込むこと）

1. まず `$0/SALES_STRATEGY.md` と `$0/BUSINESS.md` を読み込み、以下を把握する:
   - 営業チャネルの優先順位・使わないチャネル
   - 件名パターンのバリエーション（A/Bテスト指示がある場合は必ず従う）
   - 本文の構成方針・テンプレート
   - 送信者情報（送信元メールアドレス・署名）
   - SNSメッセージ方針

2. 次に `${CLAUDE_PLUGIN_ROOT}/skills/outbound/SKILL.md` を読み込み、実行手順に従う

3. チャネルに応じて以下も読み込む:
   - メール送信時: `${CLAUDE_PLUGIN_ROOT}/skills/outbound/references/email-guidelines.md`
   - フォーム入力時: `${CLAUDE_PLUGIN_ROOT}/skills/outbound/references/form-filling.md`

## 営業方針の必須ルール

- **件名:** SALES_STRATEGY.md に複数の件名パターンがある場合、バッチ内で均等に使い分けること。毎回同じ件名にしない
- **本文冒頭:** 相手企業の具体的な特徴・業種・取り組みに言及すること。「貴社のウェブサイトを拝見し」等の汎用挨拶だけは不可
- **本文全体:** overview と match_reason から相手固有の情報を複数箇所に散りばめ、テンプレートの差し替えではなく相手に合わせた文脈で書く
[前バッチの件名パターン使用状況があればここに追記]

## タスク

- プロジェクトディレクトリ: $0
- バッチ番号: N
- 処理件数: 10（最終バッチは端数）
- 詳細結果を `$0/.tmp/outbound-batch-N.md` に書き出すこと
- メインへの返答は **成功数・失敗数・unreachable数・失敗の主な理由（あれば）・使用した件名パターン一覧のみ**
  例: 「成功8, 失敗1(フォーム送信エラー), unreachable 1。件名パターン: A×4, B×3, C×3」
```

**前バッチの結果引き継ぎ:** 2バッチ目以降は、前バッチが返した件名パターン使用状況をプロンプトの「前バッチの件名パターン使用状況」部分に追記し、同じパターンへの偏りを防ぐ。例: 「前バッチではパターンAを4回、Bを3回使用。今回はB, Cを多めに使うこと」

**直列にする理由:** 各バッチが同じDBの同じステータスを参照するため、並列実行すると同じ営業先に重複アプローチするリスクがある。

各バッチのサマリーが返るたびに進捗を報告する（例: 「outbound: 10/30件完了」）。

**バッチ間の成功率チェック:** 各バッチ完了後、成功率（成功数 / 処理数）を確認する。成功率が30%未満の場合、残りバッチの実行を中断し、以下を自律的に判断・実行する:
- 失敗理由が連絡先不足（unreachable多発）→ ステップ8のbuild-listを優先実行し、連絡先付きの営業先を補充する
- 失敗理由がシステム的問題（gog send認証エラー等）→ outbound全体を中断し、完了レポートで問題を報告する
- 失敗理由がフォーム不適合等 → 残りバッチはメールありの営業先のみに絞って継続する

### 8. build-list（必要時のみ、3ステップ構成）

以下のいずれかの場合に実行する:
- ステップ6の判定で outbound より先に build-list を実行すると決定された
- リスト残数（ステップ6の結果 − ステップ7で消費した件数）が outbound件数の3倍未満
- ステップ7でバッチ間成功率チェックにより連絡先補充が必要と判断された

目標件数はoutbound件数と同じ（`$1`、デフォルト30）とする。ただし、登録件数ではなく **reachable 件数** で目標に近づけることを意識する（連絡先なし分を見越して多めに候補収集する）。

build-list スキルはサブエージェント内でさらにサブエージェントを起動する構成のため、daily-cycle からは直接呼び出せない（ネスト制約）。代わりに、build-list の各フェーズを個別のサブエージェントとして実行する:

**8a. 候補収集（サブエージェント）**

ステップ7の最後のoutboundバッチと**並行起動**しても良い（候補収集は新規追加のみなので重複リスクなし）。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- 目標件数
- `${CLAUDE_PLUGIN_ROOT}/skills/build-list/SKILL.md` の Phase 1（ステップ1〜5）を読み込んで、その手順に従うこと
- **連絡先（メール・フォーム等）の取得は不要**。候補の名前・公式URL・概要・業種・マッチ理由・優先度のみ収集すること
- 完了後、候補リストをJSON配列で返すこと（各オブジェクト: company_name, website_url, overview, industry, match_reason, priority（1-5の数値。build-list SKILL.mdの定義に従う））
- 探索メモ（`$0/SEARCH_NOTES.md`）の更新も行うこと

**8b. 重複フィルタ（メインコンテキスト）**

8a で返された候補リストから、既にDBに登録済みの営業先を除外する。8a の出力をJSONファイルに保存し、`filter_duplicates.py` に渡す:

```bash
cat <<'EOF' | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/filter_duplicates.py data.db "$0"
<8aの出力JSON配列>
EOF
```

スクリプトが company_name の完全一致と website_url のドメイン一致で重複を自動除外し、新規候補のみをJSON配列で出力する（除外結果のサマリーは stderr に出力される）。出力されたJSON配列を 8c に渡す。

新規候補が0件の場合は 8c・8d をスキップし、完了レポートで報告する。

**8c. 連絡先取得（サブエージェント × バッチ）**

8b で絞り込まれた新規候補を **5件ずつのバッチ** に分割し、それぞれサブエージェントを起動する。

各サブエージェントのプロンプトに以下を含める:
- 担当する候補のリスト（8aの出力から該当分を渡す）
- `${CLAUDE_PLUGIN_ROOT}/skills/build-list/references/enrich-contacts.md` を読み込んで、その手順に従うこと
- 各候補の公式サイトを探索し、メールアドレス・フォームURL・SNSアカウントを取得すること
- 完了後、取得結果をJSON配列で返すこと

**8c2. 連絡先なし候補の再探索（サブエージェント、該当がある場合のみ）**

8c の結果で email / contact_form_url の両方が null の候補がある場合、サブエージェントを起動して公式サイト以外の情報源から補完を試みる。

プロンプトに以下を含める:
- 対象候補のリスト（company_name, website_url）。最大10件まで
- 各候補について WebSearch で `"{会社名}" メールアドレス` `"{会社名}" 問い合わせ` 等を検索し、業界ディレクトリやプレスリリース配信サイト等から連絡先を探すこと
- 見つかった連絡先（email, contact_form_url, sns_accounts）をJSON配列で返すこと
- 見つからなかった候補は結果に含めなくてよい

サブエージェントの結果を 8c の結果JSONに反映する。

**8d. DB登録（メインコンテキスト）**

8b のフィルタ済み候補（Phase 1情報）と 8c の連絡先取得結果をマージし、`add_prospects.py` で登録する。

まず、8b の出力（候補JSON）と 8c の出力（連絡先JSON）をそれぞれファイルに保存する:
- 8b の出力 → `/tmp/candidates.json`
- 8c の各サブエージェントの出力を1つのJSON配列に結合 → `/tmp/contacts.json`

`merge_prospects.py` で company_name + ドメインで突き合わせマージし、そのまま `add_prospects.py` に渡す:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_prospects.py /tmp/candidates.json /tmp/contacts.json \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/add_prospects.py data.db "$0"
```

マージ結果のサマリー（未マッチ件数等）は stderr に出力される。

**8e. reachable 再チェック & サマリー書き出し**

build-list 完了後、reachable 件数を再確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db count-reachable "$0"
```

build-list のサマリー（追加件数、reachable件数、未マッチ件数等）を `$0/.tmp/build-list-summary.md` に書き出す。

ステップ6の判定で build-list を先に実行した場合は、ここからステップ7（outbound）に進む。

### 9. wrap-up（サブエージェント）

**全フェーズ完了後、レポート生成・通知・commitを1つのサブエージェントで実行する。** これにより、メインコンテキストの蓄積に影響されず確実に最終処理を行う。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- 実行日時: ステップ1で取得した日時
- evaluate をスキップした場合はその旨
- outbound をスキップした場合はその旨
- build-list をスキップした場合はその旨
- `$0/.tmp/` 内の全ファイルを読み込んで、以下の3つを順に実行すること

**9a. DAILY_CYCLE_REPORT.md の生成**

`$0/.tmp/` 内のサマリーファイルを全て読み込み、以下のフォーマットで `$0/DAILY_CYCLE_REPORT.md` を上書き保存する:

```markdown
# Daily Cycle Report

- 実行日時: YYYY-MM-DD HH:MM
- プロジェクト: $0

## check-results
（反応数、内訳、ドラフト作成数）

## evaluate
（KPI、改善内容、またはスキップ理由）

## outbound
- アプローチ数: X件（成功: Y / 失敗: Z）
- 成功率: XX%
- チャネル内訳: メール X件 / フォーム Y件 / SNS Z件
- unreachable: X件

## build-list
（追加数、またはスキップ理由）

## リスト残数
X件（reachable）

## 次回への申し送り
（問題、注意点、戦略調整の提案など。なければ「特になし」）
```

**9b. 完了通知メール**

`$0/SALES_STRATEGY.md` の「通知設定」セクションから通知先メールアドレスを、「送信者情報」セクションから送信元メールアドレスを取得する。通知先が「なし」または未設定の場合はスキップする。

```bash
gog send --account "<送信元メールアドレス>" --to "<通知先メールアドレス>" --subject "daily-cycle完了: $0" --body-file "$0/DAILY_CYCLE_REPORT.md"
```

**9c. 一時ファイルの削除**

```bash
rm -rf "$0/.tmp"
```

**9d. 作業結果のコミット・プッシュ**

作業中に変更されたファイルをコミットしてプッシュする。このステップは他の処理の成否に関わらず**必ず実行する**。

```bash
git add data.db "$0/" && git commit -m "work: :e-mail: $0" && git push
```

サブエージェントのメインへの返答: レポート保存の成否、通知メール送信の成否、commit の成否を簡潔に報告。
