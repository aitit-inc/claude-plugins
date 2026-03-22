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

**重要: このスキルは `context: fork` を使わないこと。** サブエージェントのネストは1階層までという制約があるため、daily-cycle自体はメインcontextで動き、各フェーズをAgent toolで起動する必要がある。

## 引数

- プロジェクトディレクトリ名: `$0`（必須）
- outbound 件数: `$1`（省略時: 30）

## 実行手順

### 1. 準備

`$0` ディレクトリの存在と、DBにプロジェクトが登録済みであることを確認する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "SELECT id FROM projects WHERE id = ?" "$0"
```

### 2. check-results（サブエージェント）

Agent toolでサブエージェントを起動し、返信確認を実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/check-results/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、結果サマリー（反応数、内訳、送付NG件数）を返すこと

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 3. evaluate（サブエージェント）

Agent toolでサブエージェントを起動し、PDCA評価を実行する。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/evaluate/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、主要KPIと適用した改善内容のサマリーを返すこと

サブエージェントからサマリーが返ったら、ユーザーに報告する。

### 4. リスト残数を確認

未アプローチ（status = 'new'）の営業先数を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "SELECT COUNT(*) as count FROM project_prospects pp JOIN prospects p ON pp.prospect_id = p.id WHERE pp.project_id = ? AND pp.status = 'new' AND p.do_not_contact = 0 AND (p.email IS NOT NULL OR p.contact_form_url IS NOT NULL OR p.sns_accounts IS NOT NULL)" "$0"
```

### 5. outbound（サブエージェント × バッチ分割）

outbound件数（`$1`、デフォルト30）を **10件ずつのバッチ** に分割し、それぞれ別のサブエージェントとして**直列**で起動する。

例: 30件 → 3回のサブエージェント起動（各10件）

各サブエージェントのプロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- 処理件数: 10（最終バッチは端数）
- `${CLAUDE_PLUGIN_ROOT}/skills/outbound/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、アプローチ数・チャネル内訳・失敗数のサマリーを返すこと

**直列にする理由:** 各バッチが同じDBの同じステータスを参照するため、並列実行すると同じ営業先に重複アプローチするリスクがある。

各バッチのサマリーが返るたびに進捗を報告する（例: 「outbound: 10/30件完了」）。

### 6. build-list（サブエージェント、必要時のみ）

リスト残数（ステップ4の結果 − ステップ5で消費した件数）が outbound件数の3倍未満の場合のみ実行する。3倍以上あればスキップ。

ステップ5の最後のoutboundバッチと**並行起動**しても良い（build-listは新規追加のみなので重複リスクなし）。

プロンプトに以下を含める:
- プロジェクトディレクトリ: `$0`
- `${CLAUDE_PLUGIN_ROOT}/skills/build-list/SKILL.md` を読み込んで、その手順に従うこと
- 完了後、追加した営業先数のサマリーを返すこと

### 7. 完了レポート

全フェーズのサマリーを集約して報告する:
- check-results: 反応数、ポジティブ/ネガティブの内訳
- evaluate: 主要KPI、適用した改善内容
- outbound: 合計アプローチ数、チャネル内訳、失敗数
- build-list: 追加数（またはスキップ）
- 現在のリスト残数
- 次回の daily-cycle で注意すべき点（あれば）
