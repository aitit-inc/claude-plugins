---
name: evaluate
description: "This skill should be used when the user asks to \"結果を分析して\", \"戦略を改善して\", \"PDCAを回して\", \"効果を評価して\", \"反応率を見て\", or wants to evaluate sales performance and improve strategy. 反応率等のデータに基づいて戦略・ターゲティング・メッセージングを自動で分析し改善する。"
argument-hint: "<project-directory-name>"
allowed-tools:
  - Bash
  - Read
  - Write
  - WebSearch
  - WebFetch
---

# Evaluate - PDCA評価＆改善

営業活動の結果データを分析し、戦略・戦術・ターゲティング・メッセージング等のあらゆる側面を評価して自動改善するスキル。

## 実行手順

### 1. データ収集

`references/evaluation-queries.sql` のクエリテンプレートを使い、`<project_id>` を実際のIDに置換して順次実行する。各クエリの結果を分析用に保持する。

### 2. 既存戦略の読み込み

プロジェクトディレクトリから以下を読み込む:
- `BUSINESS.md`
- `SALES_STRATEGY.md`
- `RESULTS_REPORT.md`（存在する場合）
- 過去の `evaluations` テーブルの記録

### 3. 多角的分析

以下の観点で分析を行う:

**反応率分析:**
- 全体の反応率
- チャネル別の反応率（メール vs フォーム vs SNS）
- 優先度別の反応率
- 時間帯・曜日別の傾向（送信日時から分析）

**メッセージ分析:**
- 反応があったメールの共通点
- 反応がなかったメールとの差異
- 件名の効果
- 本文の長さ・構成の効果

**ターゲット分析:**
- 反応が良い業種・企業規模
- 反応が悪いセグメント
- 想定外の反応パターン

**チャネル分析:**
- 最も効果的なチャネル
- チャネルごとのコスト対効果

### 4. 改善アクションの決定と自動適用

分析結果に基づいて具体的な改善を決定し、**自動で適用する**:

**SALES_STRATEGY.md の更新:**
- ターゲットの絞り込みまたは拡大
- メッセージングの改善（件名、本文構成、トーン）
- チャネル優先順位の見直し
- KPI目標の更新

**検索キーワードの更新:**
- 反応が良いセグメントに関連するキーワードの追加
- 効果が低いキーワードの削除

**優先度の再計算:**
- 反応パターンに基づいてprospectsの優先度を更新

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "UPDATE prospects SET priority = <new_priority>, updated_at = datetime('now') WHERE project_id = <id> AND industry = '<industry>' AND status = 'new';"
```

### 5. 評価記録の保存

evaluationsテーブルに記録する:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "INSERT INTO evaluations (project_id, metrics, findings, improvements, applied_changes) VALUES (<id>, '<metrics_json>', '<findings>', '<improvements_json>', '<applied_changes>');"
```

### 6. 結果レポート

以下を報告する:
- 主要KPI（反応率、ポジティブ率等）
- 前回評価からの変化（あれば）
- 分析で発見した重要な知見
- 適用した改善内容の一覧
- 次に取るべきアクション（`/build-list` で追加探索、`/outbound` で再アプローチ等）

レポートをプロジェクトディレクトリに `EVALUATION_REPORT.md` として保存する（上書き。履歴はDBに保存済み）。
