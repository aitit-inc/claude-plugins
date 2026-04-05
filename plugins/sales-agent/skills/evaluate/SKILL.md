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

**前提:** `${CLAUDE_PLUGIN_ROOT}/references/workspace-conventions.md` の規約に従うこと（data.dbの配置・cdしないルール）。

## 実行手順

### 1. データ収集

- プロジェクトディレクトリ名: `$0`（必須）

`references/evaluation-queries.sql` のクエリテンプレートを使い、`$0` のプロジェクトIDを取得して置換し、順次実行する。各クエリの結果を分析用に保持する。

### 2. 既存戦略の読み込み

以下を読み込む:
- `$0/BUSINESS.md`
- `$0/SALES_STRATEGY.md`
- `$0/RESULTS_REPORT.md`（存在する場合）
- 過去の `evaluations` テーブルの記録（全件）

過去のevaluationsが存在する場合、各レコードの `evaluation_date`、`findings`、`improvements` を時系列で整理し、これまでに何を試し、何が効果的で、何が効果がなかったかを把握する。この情報はステップ4の改善アクション決定時に使う。

### 3. 多角的分析

`${CLAUDE_PLUGIN_ROOT}/skills/evaluate/references/analysis-frameworks.md` を参照し、以下の観点で分析を行う:

**反応率分析:**
- 全体の反応率
- チャネル別の反応率（メール vs フォーム vs SNS）
- 優先度別の反応率
- 時間帯・曜日別の傾向（送信日時から分析）

**メッセージ分析:**
- 反応があったメールの本文（outreach_logs.body）を全件読み込み、共通点を抽出
- 反応がなかったメールからは数件サンプリングして比較
- 件名の効果
- 本文の長さ・構成の効果

**ターゲット分析:**
- 反応が良い業種・規模
- 反応が悪いセグメント
- 想定外の反応パターン

**チャネル分析:**
- 最も効果的なチャネル
- チャネルごとのコスト対効果

### 4. 改善アクションの決定と自動適用

**データ量の確認（必須）:**

改善アクションを適用する前に、データが十分かどうかを確認する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sales_queries.py data.db data-sufficiency "$0"
```

以下のいずれかに該当する場合、**SALES_STRATEGY.mdへの変更適用・優先度再計算は行わない**。レポート生成（ステップ5・6）のみ実行し、「データ不足のためモニタリング継続」と報告する:
- アプローチ総数（status='sent'）が30件未満
- 最終送信から3営業日未満

データ不足でもevaluationsテーブルへの記録（ステップ5）とレポート生成（ステップ6）は行う。現状把握として有用なため。

---

データが十分な場合、分析結果に基づいて具体的な改善を決定し、**自動で適用する**。

**過去の改善履歴との照合（必須）:**
改善アクションを決定する前に、ステップ2で整理した過去のevaluations履歴を確認し、以下を守る:
- 過去に実施済みで効果がなかった施策を再採用しない
- 過去に効果があった施策の方向性を継続・深化させる
- 過去と同じ改善を提案する場合は、なぜ今回は異なる結果が期待できるか理由を明記する

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
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "UPDATE project_prospects SET priority = ?, updated_at = datetime('now') WHERE project_id = ? AND prospect_id IN (SELECT id FROM prospects WHERE industry = ?) AND status = 'new'" "<new_priority>" "$0" "<industry>"
```

### 5. 評価記録の保存

evaluationsテーブルに記録する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT INTO evaluations (project_id, metrics, findings, improvements) VALUES (?, ?, ?, ?)" "$0" "<metrics_json>" "<findings>" "<improvements_json>"
```

### 6. 結果レポート

以下を報告する:
- 主要KPI（反応率、ポジティブ率等）
- 前回評価からの変化（あれば）
- 分析で発見した重要な知見
- 適用した改善内容の一覧
- 次に取るべきアクション（`/build-list` で追加探索、`/outbound` で再アプローチ等）

レポートをプロジェクトディレクトリに `EVALUATION_REPORT.md` として保存する（上書き。履歴はDBに保存済み）。
