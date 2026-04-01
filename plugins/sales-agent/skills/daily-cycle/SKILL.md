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

## 引数

- プロジェクトディレクトリ名: `$0`（必須）
- outbound 件数: `$1`（省略時: 30）

## 実行手順

### 1. 準備

`$0` ディレクトリの存在と、DBにプロジェクトが登録済みであることを確認する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db project-exists "$0"
```

### 2. 前回サイクルレビュー

`$0/DAILY_CYCLE_REPORT.md` が存在する場合、読み込んで以下を把握する:

- 前回の実行日時
- outbound成功率とチャネル内訳（成功率が低かった場合、今回のバッチ戦略に反映）
- build-listの結果（候補不足だった場合、今回は早めにbuild-listを実行する判断材料にする）
- 「次回への申し送り」セクション（システムエラー、中断、要注意事項など）

把握した内容は、以降のステップでサブエージェントに渡すプロンプトに**関連する申し送りがある場合のみ**追記する。例:
- outbound成功率が低かった → ステップ6のサブエージェントに「前回成功率が低かった（XX%）。チャネルYで失敗多発」と伝える
- build-listで候補が少なかった → ステップ7aのサブエージェントに「前回は候補収集でN件しか見つからなかった。SEARCH_NOTES.mdの方向性を変えること」と伝える
- システムエラーがあった → 該当ステップのサブエージェントに警告として伝える

ファイルが存在しない場合（初回実行）はスキップする。

### 3. check-results（サブエージェント）

Agent toolでサブエージェントを起動し、返信確認を実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/check-results/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、結果サマリー（反応数、内訳、送付NG件数）を返すこと

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 4. evaluate（サブエージェント、条件付き）

前回の evaluate 実行日を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db last-evaluation "$0"
```

前回 evaluate から **3営業日以上経過している場合のみ** サブエージェントを起動する。3営業日未満の場合は「前回evaluateから日が浅いためスキップ」と報告してステップ5に進む。evaluations レコードが存在しない場合（初回）は実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/evaluate/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、主要KPIと適用した改善内容のサマリーを返すこと

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 5. リスト残数を確認し、実行順序を決定

未アプローチ（status = 'new'）の営業先数を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db count-reachable "$0"
```

**実行順序の判定:** リスト残数が outbound 指定件数の **1/3 未満** の場合、outbound より先にステップ7（build-list）を実行してリストを充填する。充填後にステップ6の outbound に戻る。

- リスト残数 ≥ 指定件数の 1/3 → ステップ6（outbound）→ ステップ7（build-list、必要時）
- リスト残数 < 指定件数の 1/3 → ステップ7（build-list）→ ステップ5を再実行 → ステップ6（outbound）
- リスト残数 = 0 かつ build-list 未実行 → ステップ7（build-list）→ ステップ5を再実行 → ステップ6（outbound）

### 6. outbound（サブエージェント × バッチ分割）

**実際のoutbound件数の決定:** `min(指定件数, ステップ5のリスト残数)` を実際のoutbound件数とする。リスト残数が0の場合（ステップ7実行後も0の場合）はoutboundをスキップし、完了レポートに進む。

outbound件数を **10件ずつのバッチ** に分割し、それぞれ別のサブエージェントとして**直列**で起動する。

例: 30件 → 3回のサブエージェント起動（各10件）

各サブエージェントのプロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- 処理件数: 10（最終バッチは端数）
- `${CLAUDE_PLUGIN_ROOT}/skills/outbound/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、アプローチ数（成功/失敗内訳）・チャネル内訳・unreachable件数のサマリーを返すこと

**直列にする理由:** 各バッチが同じDBの同じステータスを参照するため、並列実行すると同じ営業先に重複アプローチするリスクがある。

各バッチのサマリーが返るたびに進捗を報告する（例: 「outbound: 10/30件完了」）。

**バッチ間の成功率チェック:** 各バッチ完了後、成功率（成功数 / 処理数）を確認する。成功率が30%未満の場合、残りバッチの実行を中断し、以下を自律的に判断・実行する:
- 失敗理由が連絡先不足（unreachable多発）→ ステップ7のbuild-listを優先実行し、連絡先付きの営業先を補充する
- 失敗理由がシステム的問題（gog send認証エラー等）→ outbound全体を中断し、完了レポートで問題を報告する
- 失敗理由がフォーム不適合等 → 残りバッチはメールありの営業先のみに絞って継続する

### 7. build-list（必要時のみ、3ステップ構成）

以下のいずれかの場合に実行する:
- ステップ5の判定で outbound より先に build-list を実行すると決定された
- リスト残数（ステップ5の結果 − ステップ6で消費した件数）が outbound件数の3倍未満
- ステップ6でバッチ間成功率チェックにより連絡先補充が必要と判断された

目標件数はoutbound件数と同じ（`$1`、デフォルト30）とする。ただし、登録件数ではなく **reachable 件数** で目標に近づけることを意識する（連絡先なし分を見越して多めに候補収集する）。

build-list スキルはサブエージェント内でさらにサブエージェントを起動する構成のため、daily-cycle からは直接呼び出せない（ネスト制約）。代わりに、build-list の各フェーズを個別のサブエージェントとして実行する:

**7a. 候補収集（サブエージェント）**

ステップ6の最後のoutboundバッチと**並行起動**しても良い（候補収集は新規追加のみなので重複リスクなし）。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- 目標件数
- `${CLAUDE_PLUGIN_ROOT}/skills/build-list/SKILL.md` の Phase 1（ステップ1〜5）を読み込んで、その手順に従うこと
- **連絡先（メール・フォーム等）の取得は不要**。候補の名前・公式URL・概要・業種・マッチ理由・優先度のみ収集すること
- 完了後、候補リストをJSON配列で返すこと（各オブジェクト: company_name, website_url, overview, industry, match_reason, priority（1-5の数値。build-list SKILL.mdの定義に従う））
- 探索メモ（`$0/SEARCH_NOTES.md`）の更新も行うこと

**7b. 重複フィルタ（メインコンテキスト）**

7a で返された候補リストから、既にDBに登録済みの営業先を除外する。7a の出力をJSONファイルに保存し、`filter_duplicates.py` に渡す:

```bash
cat <<'EOF' | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/filter_duplicates.py data.db "$0"
<7aの出力JSON配列>
EOF
```

スクリプトが company_name の完全一致と website_url のドメイン一致で重複を自動除外し、新規候補のみをJSON配列で出力する（除外結果のサマリーは stderr に出力される）。出力されたJSON配列を 7c に渡す。

新規候補が0件の場合は 7c・7d をスキップし、完了レポートで報告する。

**7c. 連絡先取得（サブエージェント × バッチ）**

7b で絞り込まれた新規候補を **5件ずつのバッチ** に分割し、それぞれサブエージェントを起動する。

各サブエージェントのプロンプトに以下を含める:
- 担当する候補のリスト（7aの出力から該当分を渡す）
- `${CLAUDE_PLUGIN_ROOT}/skills/build-list/references/enrich-contacts.md` を読み込んで、その手順に従うこと
- 各候補の公式サイトを探索し、メールアドレス・フォームURL・SNSアカウントを取得すること
- 完了後、取得結果をJSON配列で返すこと

サブエージェントの allowed-tools: `WebFetch`, `WebSearch`, `Read`

**7c2. 連絡先なし候補の再探索（メインコンテキスト、該当がある場合のみ）**

7c の結果で email / contact_form_url の両方が null の候補がある場合、公式サイト以外の情報源から補完を試みる。対象候補ごとに WebSearch で `"{会社名}" メールアドレス` `"{会社名}" 問い合わせ` 等を検索し、業界ディレクトリやプレスリリース配信サイト等から連絡先を探す。最大10件まで。見つかれば 7c の結果JSONに反映する。

**7d. DB登録（メインコンテキスト）**

7b のフィルタ済み候補（Phase 1情報）と 7c の連絡先取得結果をマージし、`add_prospects.py` で登録する。

まず、7b の出力（候補JSON）と 7c の出力（連絡先JSON）をそれぞれファイルに保存する:
- 7b の出力 → `/tmp/candidates.json`
- 7c の各サブエージェントの出力を1つのJSON配列に結合 → `/tmp/contacts.json`

`merge_prospects.py` で company_name + ドメインで突き合わせマージし、そのまま `add_prospects.py` に渡す:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_prospects.py /tmp/candidates.json /tmp/contacts.json \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/add_prospects.py data.db "$0"
```

マージ結果のサマリー（未マッチ件数等）は stderr に出力される。未マッチが多い場合は完了レポートで報告する。

**7e. reachable 再チェック**

build-list 完了後、reachable 件数を再確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db count-reachable "$0"
```

ステップ5の判定で build-list を先に実行した場合は、ここからステップ6（outbound）に進む。

### 8. 完了レポート

全フェーズのサマリーを集約して報告する:
- check-results: 反応数、ポジティブ/ネガティブの内訳
- evaluate: 主要KPI、適用した改善内容
- outbound: 合計アプローチ数、チャネル内訳、成功率、失敗数
- build-list: 追加数（またはスキップ）
- 現在のリスト残数
- 次回への申し送り（問題・注意点・戦略調整の提案があれば）

レポート内容を `$0/DAILY_CYCLE_REPORT.md` に保存する（上書き）。フォーマット:

```markdown
# Daily Cycle Report

- 実行日時: YYYY-MM-DD HH:MM
- プロジェクト: $0

## check-results
（反応数、内訳）

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

### 9. 完了通知メール

SALES_STRATEGY.mdの「通知設定」セクションから通知先メールアドレスを、「送信者情報」セクションから送信元メールアドレスを取得する。通知先が「なし」または未設定の場合はスキップする。

```bash
gog send --account "<送信元メールアドレス>" --to "<通知先メールアドレス>" --subject "daily-cycle完了: $0" --body "<ステップ8のレポート内容>"
```

本文が長い場合は `--body-file` を使用する。
