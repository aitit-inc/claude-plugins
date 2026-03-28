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

### 2. check-results（サブエージェント）

Agent toolでサブエージェントを起動し、返信確認を実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/check-results/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、結果サマリー（反応数、内訳、送付NG件数）を返すこと

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 3. evaluate（サブエージェント、条件付き）

前回の evaluate 実行日を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db last-evaluation "$0"
```

前回 evaluate から **3営業日以上経過している場合のみ** サブエージェントを起動する。3営業日未満の場合は「前回evaluateから日が浅いためスキップ」と報告してステップ4に進む。evaluations レコードが存在しない場合（初回）は実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/evaluate/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、主要KPIと適用した改善内容のサマリーを返すこと

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 4. リスト残数を確認

未アプローチ（status = 'new'）の営業先数を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db count-reachable "$0"
```

### 5. outbound（サブエージェント × バッチ分割）

**実際のoutbound件数の決定:** `min(指定件数, ステップ4のリスト残数)` を実際のoutbound件数とする。リスト残数が0の場合はoutboundをスキップし、ステップ6（build-list）に進む。

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
- 失敗理由が連絡先不足（unreachable多発）→ ステップ6のbuild-listを優先実行し、連絡先付きの営業先を補充する
- 失敗理由がシステム的問題（gog send認証エラー等）→ outbound全体を中断し、完了レポートで問題を報告する
- 失敗理由がフォーム不適合等 → 残りバッチはメールありの営業先のみに絞って継続する

### 6. build-list（必要時のみ、3ステップ構成）

以下のいずれかの場合に実行する:
- リスト残数（ステップ4の結果 − ステップ5で消費した件数）が outbound件数の3倍未満
- ステップ5でバッチ間成功率チェックにより連絡先補充が必要と判断された

目標件数はoutbound件数と同じ（`$1`、デフォルト30）とする。

build-list スキルはサブエージェント内でさらにサブエージェントを起動する構成のため、daily-cycle からは直接呼び出せない（ネスト制約）。代わりに、build-list の各フェーズを個別のサブエージェントとして実行する:

**6a. 候補収集（サブエージェント）**

ステップ5の最後のoutboundバッチと**並行起動**しても良い（候補収集は新規追加のみなので重複リスクなし）。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- 目標件数
- `${CLAUDE_PLUGIN_ROOT}/skills/build-list/SKILL.md` の Phase 1（ステップ1〜5）を読み込んで、その手順に従うこと
- **連絡先（メール・フォーム等）の取得は不要**。候補の名前・公式URL・概要・業種・マッチ理由・優先度のみ収集すること
- 完了後、候補リストをJSON配列で返すこと（各オブジェクト: company_name, website_url, overview, industry, match_reason, priority）
- 探索メモ（`$0/SEARCH_NOTES.md`）の更新も行うこと

**6b. 連絡先取得（サブエージェント × バッチ）**

6a で返された候補リストを **5件ずつのバッチ** に分割し、それぞれサブエージェントを起動する。

各サブエージェントのプロンプトに以下を含める:
- 担当する候補のリスト（6aの出力から該当分を渡す）
- `${CLAUDE_PLUGIN_ROOT}/skills/build-list/references/enrich-contacts.md` を読み込んで、その手順に従うこと
- 各候補の公式サイトを探索し、メールアドレス・フォームURL・SNSアカウントを取得すること
- 完了後、取得結果をJSON配列で返すこと

サブエージェントの allowed-tools: `WebFetch`, `WebSearch`, `Read`

**6c. DB登録（メインコンテキスト）**

6b の各サブエージェントから返されたJSONをまとめて `add_prospects.py` で登録する:

```bash
cat <<'EOF' | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/add_prospects.py data.db "$0"
<6bの結果をマージしたJSON配列>
EOF
```

登録結果を確認し、新規登録数をサマリーに含める。

### 7. 完了レポート

全フェーズのサマリーを集約して報告する:
- check-results: 反応数、ポジティブ/ネガティブの内訳
- evaluate: 主要KPI、適用した改善内容
- outbound: 合計アプローチ数、チャネル内訳、失敗数
- build-list: 追加数（またはスキップ）
- 現在のリスト残数
- 次回の daily-cycle で注意すべき点（あれば）

### 8. 完了通知メール

SALES_STRATEGY.mdの「通知設定」セクションから通知先メールアドレスを、「送信者情報」セクションから送信元メールアドレスを取得する。通知先が「なし」または未設定の場合はスキップする。

```bash
gog send --account "<送信元メールアドレス>" --to "<通知先メールアドレス>" --subject "daily-cycle完了: $0" --body "<ステップ7のレポート内容>"
```

本文が長い場合は `--body-file` を使用する。
