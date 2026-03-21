---
name: build-list
description: "This skill should be used when the user asks to \"営業先リストを作って\", \"営業先を探して\", \"見込み客を集めて\", \"ターゲットを探索して\", or wants to build a prospect list. BUSINESS.mdとSALES_STRATEGY.mdに基づきWeb探索で営業先候補を収集しDBに登録する。"
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

検索クエリの種類（ターゲットの種別に応じて適切なものを選ぶ）:
- ターゲット業種 + 地域での検索
- 業界団体・協会・連盟のメンバーリスト
- 業界メディア・ニュースサイトでの営業先収集
- 展示会・イベントの出展者リスト
- 競合のクライアント事例
- 求人サイトでのターゲット探索
- 学校・法人の一覧サイトや公的データベース

### 3. Web探索の実行

WebSearchとWebFetchを組み合わせて、片っ端から営業先情報を収集する。

各営業先について以下の情報を取得する:

**必須（これがないと登録しない）:**
- 名称（企業名、学校名、法人名等）
- 事業概要（何をしている組織か。公式サイトから1-2文で要約）
- 公式サイトURL

**可能な限り取得:**
- 業種・分野
- メールアドレス（問い合わせ先、代表メール等）
- 問い合わせフォームURL
- SNSアカウント（Twitter/X、LinkedIn、Facebook等）

公式サイトURLと事業概要が取得できない営業先はスキップする。

**探索のコツ:**
- 1つの検索クエリで見つかる営業先は限られるので、多角的にクエリを変えて探索する
- 公式サイトにアクセスして、問い合わせ先やフォームURLを取得する
- ポータルサイトや一覧ページを活用する
- 上限は設けず、見つかる限り収集する

### 4. 優先度・マッチ理由の判定

各営業先について、SALES_STRATEGY.mdの基準でマッチ理由（なぜターゲットとして適切か、相手の課題・ニーズを含む）と優先度（1-5）を付与する:
- 1: 最有力（ターゲットに完全合致、ニーズが明確）
- 2: 有力（ターゲットに概ね合致）
- 3: 通常（ターゲット範囲内）
- 4: やや外れる（一部条件のみ合致）
- 5: 要検討（間接的な可能性）

### 5. データベース登録

収集した営業先情報をDBに登録する。prospects は全プロジェクト共有のプールなので、まず重複チェックを行い、既存なら既存レコードを使い、新規なら登録する。

**Step 1: 重複チェック**

各営業先について、取得できた情報をすべて渡してチェックする:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_duplicate.py data.db \
  --company-name "<name>" \
  --email "<email>" \
  --website-url "<url>" \
  --sns twitter "<account>" \
  --corporate-number "<number>"
```

引数は取得できたものだけ渡せばよい（すべて省略可能）。

結果はJSON配列で返る。判定:
- `EXACT_MATCH` → 既存の prospect_id を使う。新規登録しない
- `POSSIBLE_MATCH` → 既存レコードの詳細（company_name, website_url, email 等）を確認し、同一の営業先か別の営業先かを判断する。同一なら既存IDを使い、別なら新規登録する
- マッチなし（exit code 1） → 新規登録する

**Step 2: 新規の場合、prospectsに登録**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT INTO prospects (company_name, corporate_number, overview, industry, website_url, email, contact_form_url, sns_accounts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)" "<company_name>" "<corporate_number>" "<overview>" "<industry>" "<website_url>" "<email>" "<contact_form_url>" "<sns_accounts_json>"
```

**Step 3: プロジェクトとの紐付けを登録**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT OR IGNORE INTO project_prospects (project_id, prospect_id, match_reason, priority) VALUES (?, ?, ?, ?)" "<project_id>" "<prospect_id>" "<match_reason>" "<priority>"
```

`project_prospects` には UNIQUE(project_id, prospect_id) 制約があるため、同じプロジェクトへの重複紐付けは自動で弾かれる。

### 6. 結果レポート

以下を報告する:
- 収集した営業先数（優先度別の内訳）
- チャネル別のカバレッジ（メールあり: N件、フォームあり: N件、SNSあり: N件）
- 次のステップとして `/outbound` の実行を案内する

結果の一覧をプロジェクトディレクトリ内に `PROSPECT_REPORT.md` として保存する。
