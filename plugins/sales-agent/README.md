# sales-agent

セールス活動の全工程を自動化する Claude Code プラグイン。
戦略策定 → 営業リスト作成 → アウトバウンド営業 → 結果収集 → PDCA改善 を一気通貫で実行する。

## 利用者向け

### 前提条件

- Claude Code
- SQLite3
- Gmail MCP（メール送信・確認用）
- claude-in-chrome MCP（フォーム入力・SNS操作用）

### インストール

Claude Code 内で以下を実行:

```
/plugin marketplace add aitit-inc/claude-plugins
/plugin install sales-agent@aitit-plugins
```

更新する場合:

```
/plugin marketplace update
/plugin update sales-agent@aitit-plugins
```

### 使い方

以下のスラッシュコマンドをパイプライン的に順番に実行する。

| コマンド | 概要 |
|---|---|
| `/setup <dir>` | プロジェクト初期化（DB・ディレクトリ作成） |
| `/strategy <dir>` | 営業・マーケ戦略を策定 |
| `/build-list <dir>` | Web探索で営業先リストを作成 |
| `/outbound <dir>` | メール・フォーム・SNS DMでアプローチ |
| `/check-results <dir>` | 反応を確認・記録 |
| `/evaluate <dir>` | データ分析に基づいてPDCA改善 |

`<dir>` は製品/サービスごとのサブディレクトリ名（例: `product-a-sales`）。
データベース（`data.db`）はプロジェクトルートで共有、ナレッジファイル類はサブディレクトリに分離される。

### 基本的な流れ

```
/setup my-product
/strategy my-product        # 対話で事業情報を入力 → BUSINESS.md, SALES_STRATEGY.md 生成
/build-list my-product      # Web探索で営業先を収集
/outbound my-product        # 自動でアウトバウンド営業
/check-results my-product   # 反応を確認
/evaluate my-product        # 結果を分析して戦略を自動改善
```

`/build-list` → `/outbound` → `/check-results` → `/evaluate` のサイクルを繰り返すことで営業活動が改善されていく。

---

## 開発者向け

### プラグイン構成

```
.claude-plugin/plugin.json   # マニフェスト
skills/                      # スラッシュコマンド（各ディレクトリに SKILL.md）
scripts/                     # 共有スクリプト（DB初期化・クエリ実行等）
```

- 各スキルの仕様は `skills/<name>/SKILL.md` を参照
- 詳細なテンプレートやガイドラインは `skills/<name>/references/` に分離
- スクリプト内では `${CLAUDE_PLUGIN_ROOT}` でプラグインルートを参照

### DBスキーマ

`scripts/sales-db.sql` に定義。主要テーブル: `projects`, `prospects`, `outreach_logs`, `responses`, `evaluations`。

### ローカルでの開発・テスト

```bash
# このリポジトリのディレクトリで Claude Code を起動すればスキルが自動ロードされる
claude

# または別プロジェクトからプラグインとして指定
claude --plugin-dir /path/to/this/repo
```
