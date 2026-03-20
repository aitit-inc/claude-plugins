---
name: build-list
description: "This skill should be used when the user asks to \"営業先リストを作って\", \"企業を探して\", \"見込み客を集めて\", \"ターゲット企業を探索して\", or wants to build a prospect list. BUSINESS.mdとSALES_STRATEGY.mdに基づきWeb探索で営業先候補を収集しDBに登録する。"
argument-hint: "<project-directory-name>"
allowed-tools:
  - Bash
  - Read
  - Write
  - WebSearch
  - WebFetch
---

# Build List - 営業先リスト作成

BUSINESS.mdとSALES_STRATEGY.mdの情報に基づいて、Web探索で営業先候補を大量に収集し、データベースに登録するスキル。

## 実行手順

### 1. 戦略ドキュメント読み込み

プロジェクトディレクトリから以下を読み込む:
- `<project-dir>/BUSINESS.md`
- `<project-dir>/SALES_STRATEGY.md`

存在しない場合は `/strategy` の実行を案内する。

### 2. 検索戦略の策定

SALES_STRATEGY.mdの「検索キーワード」「ターゲット」セクションを基に、複数の検索クエリを策定する。

検索クエリの種類:
- ターゲット業種 + 地域での企業検索
- 業界団体・協会のメンバーリスト
- 業界メディア・ニュースサイトでの企業名収集
- 展示会・イベントの出展企業リスト
- 競合のクライアント事例
- 求人サイトでのターゲット企業探索

### 3. Web探索の実行

WebSearchとWebFetchを組み合わせて、片っ端から企業情報を収集する。

各企業について以下の情報を可能な限り取得する:
- 企業名
- 業種
- 公式サイトURL
- メールアドレス（問い合わせ先、代表メール等）
- 問い合わせフォームURL
- SNSアカウント（Twitter/X、LinkedIn、Facebook等）
- マッチ理由（なぜこの企業がターゲットとして適切か）

**探索のコツ:**
- 1つの検索クエリで見つかる企業は限られるので、多角的にクエリを変えて探索する
- 企業の公式サイトにアクセスして、問い合わせ先やフォームURLを取得する
- 業界ポータルサイトや企業一覧ページを活用する
- 上限は設けず、見つかる限り収集する

### 4. 優先度の判定

各企業にSALES_STRATEGY.mdの基準で優先度（1-5）を付与する:
- 1: 最有力（ターゲットに完全合致、ニーズが明確）
- 2: 有力（ターゲットに概ね合致）
- 3: 通常（ターゲット範囲内）
- 4: やや外れる（一部条件のみ合致）
- 5: 要検討（間接的な可能性）

### 5. データベース登録

収集した企業情報をDBに登録する。prospects は全プロジェクト共有のプールなので、まず企業を登録し、次にプロジェクトとの紐付けを登録する。

**Step 1: 企業をprospectsに登録（既存なら取得）**

```bash
# 既存チェック
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "SELECT id FROM prospects WHERE company_name = '<name>';"
# 新規の場合のみINSERT
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "INSERT INTO prospects (company_name, industry, website_url, email, contact_form_url, sns_accounts) VALUES (...);"
```

**Step 2: プロジェクトとの紐付けを登録**

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "INSERT OR IGNORE INTO project_prospects (project_id, prospect_id, match_reason, priority) VALUES (...);"
```

`project_prospects` には UNIQUE(project_id, prospect_id) 制約があるため、同じプロジェクトへの重複紐付けは自動で弾かれる。

### 6. 結果レポート

以下を報告する:
- 収集した企業数（優先度別の内訳）
- チャネル別のカバレッジ（メールあり: N件、フォームあり: N件、SNSあり: N件）
- 次のステップとして `/outbound` の実行を案内する

結果の一覧をプロジェクトディレクトリ内に `PROSPECT_REPORT.md` として保存する。
