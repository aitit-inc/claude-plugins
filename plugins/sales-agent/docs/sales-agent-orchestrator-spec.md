# Sales Agent Orchestrator 仕様書

sales-agent プラグインの各スキルを自動的・定期的に実行するオーケストレーションの仕様。

## 方針

- オーケストレーターは **Claude Code CLI 経由でのみ** プラグインを操作する
- スクリプトやDBを直接触らない。判断・実行は全て Claude に委ねる
- 定期実行は OS の cron で `claude` コマンドを呼び出す

## 前提

- Claude Code CLI (`claude`) がインストール済み
- sales-agent プラグインがインストール済み
- 初回セットアップ（`/setup`, `/strategy`）は手動で完了済み

## 初回セットアップ（手動）

```bash
# 1. プロジェクト初期化
claude -p "/setup my-product"

# 2. 戦略策定（対話が必要なため手動）
claude
> /strategy my-product
```

## 定期実行（cron）

```crontab
# 毎日 9:00 - 日次サイクル（返信確認 → 30件アプローチ → リスト補充）
0 9 * * * cd /path/to/workspace && claude -p --dangerously-skip-permissions "/daily-cycle my-product 30" >> /path/to/logs/daily-cycle.log 2>&1

# 月・木 10:00 - PDCA評価・戦略改善
0 10 * * 1,4 cd /path/to/workspace && claude -p --dangerously-skip-permissions "/evaluate my-product" >> /path/to/logs/evaluate.log 2>&1
```

### 各 cron エントリの役割

**daily-cycle（毎日）**

内部で以下が順次・並行実行される:
1. check-results: 返信確認、ステータス更新、送付NG判定
2. outbound: 指定件数のアプローチ（メール/フォーム/SNS）
3. build-list: リスト残数が少なければ新規営業先を探索・追加

**evaluate（週2回）**

- 反応率・チャネル別効果・メッセージ分析
- SALES_STRATEGY.md の自動更新
- 営業先の優先度再計算
- evaluations テーブルに履歴を記録

## 複数プロジェクトの場合

```crontab
0 9 * * * cd /path/to/workspace && claude -p --dangerously-skip-permissions "/daily-cycle product-a 30"
30 9 * * * cd /path/to/workspace && claude -p --dangerously-skip-permissions "/daily-cycle product-b 20"
0 10 * * 1,4 cd /path/to/workspace && claude -p --dangerously-skip-permissions "/evaluate product-a"
30 10 * * 1,4 cd /path/to/workspace && claude -p --dangerously-skip-permissions "/evaluate product-b"
```

同じ DB を共有するため、同時実行は避けて時刻をずらす。

## 状況確認（手動 or 必要時）

cron とは別に、状況確認も `claude` 経由で行う:

```bash
# リスト残数・反応率などの状況確認
claude -p "my-product プロジェクトの現在の状況を教えて。リスト残数、直近7日のアプローチ数と反応率を確認して。"

# 特定の営業先の詳細確認
claude -p "my-product プロジェクトで反応があった営業先の一覧を見せて"
```

## エラー時の対処

| 症状 | 対処 |
|---|---|
| daily-cycle のログが空 or エラー | `claude -p "my-product の daily-cycle が失敗した原因を調べて"` で確認 |
| リスト残数が減り続ける | build-list の検索キーワードが枯渇。`/evaluate` で戦略改善するか、手動で `/strategy` を更新 |
| 反応率が急落 | `/evaluate` を手動実行して原因分析・改善 |
| Gmail 認証切れ | 手動で Claude Code を起動して再認証 |

## 将来の拡張

- **AIエージェントによる判断**: cron の代わりに、状況を見て実行タイミング・件数を動的に調整する軽量エージェント
- **通知**: 日次レポートを Slack やメールで送信
- **ダッシュボード**: DB の内容を可視化する Web UI
