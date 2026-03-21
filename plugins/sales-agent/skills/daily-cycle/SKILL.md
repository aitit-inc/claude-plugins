---
name: daily-cycle
description: "This skill should be used when the user asks to \"日次サイクルを回して\", \"今日の営業を実行して\", \"デイリーの営業タスクをやって\", \"daily-cycleを実行して\", or wants to run the daily sales automation cycle. check-results → outbound + build-list（必要時）を順次・並行で自動実行する。"
argument-hint: "<project-directory-name> [outbound件数=30]"
allowed-tools:
  - Bash
  - Read
  - Write
  - WebSearch
  - WebFetch
  - Agent
  - mcp__claude_ai_Gmail__gmail_create_draft
  - mcp__claude_ai_Gmail__gmail_search_messages
  - mcp__claude_ai_Gmail__gmail_read_message
  - mcp__claude_ai_Gmail__gmail_read_thread
  - mcp__claude_in_chrome__tabs_context_mcp
  - mcp__claude_in_chrome__tabs_create_mcp
  - mcp__claude_in_chrome__navigate
  - mcp__claude_in_chrome__read_page
  - mcp__claude_in_chrome__get_page_text
  - mcp__claude_in_chrome__find
  - mcp__claude_in_chrome__form_input
  - mcp__claude_in_chrome__computer
  - mcp__claude_in_chrome__javascript_tool
---

# Daily Cycle - 日次営業サイクル実行

1日分の営業活動（返信確認 → アウトバウンド + リスト補充）を自動で実行するスキル。

## 引数

- プロジェクトディレクトリ名: `$0`（必須）
- outbound 件数: `$1`（省略時: 30）

## 実行手順

### 1. 準備

`$0` ディレクトリの存在と、DBにプロジェクトが登録済みであることを確認する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "SELECT id FROM projects WHERE id = ?" "$0"
```

### 2. check-results を実行

まず返信を確認してステータスを最新にする。`/check-results` スキルと同じ手順を実行する:

- contacted 状態の営業先のメール返信・SNS反応を確認
- responses テーブルに記録
- project_prospects のステータスを更新
- 送付NGの判定

完了したら結果サマリーを報告する。

### 3. リスト残数を確認

未アプローチ（status = 'new'）の営業先数を確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "SELECT COUNT(*) as count FROM project_prospects pp JOIN prospects p ON pp.prospect_id = p.id WHERE pp.project_id = ? AND pp.status = 'new' AND p.do_not_contact = 0 AND (p.email IS NOT NULL OR p.contact_form_url IS NOT NULL OR p.sns_accounts IS NOT NULL)" "$0"
```

### 4. outbound + build-list を並行実行

Agent ツールで2つのタスクを**同時に**起動する:

**Agent 1: outbound（常に実行）**
- `/outbound` スキルと同じ手順で、指定件数分のアプローチを実行する
- BUSINESS.md と SALES_STRATEGY.md を読み込み、営業チャネルの方針に従う

**Agent 2: build-list（リスト残数が outbound 件数の3倍未満の場合のみ）**
- `/build-list` スキルと同じ手順で、新規営業先を探索・登録する
- 3倍以上のストックがあれば「リスト十分、スキップ」と報告してスキップ

2つの Agent は `run_in_background` を使わず、同一メッセージ内で並行起動する。

### 5. 完了レポート

以下を報告する:
- check-results の結果（反応数、ポジティブ/ネガティブの内訳）
- outbound の結果（アプローチ数、チャネル内訳、失敗数）
- build-list の結果（実行した場合: 追加数。スキップした場合: その旨）
- 現在のリスト残数
- 次回の daily-cycle で注意すべき点（あれば）
