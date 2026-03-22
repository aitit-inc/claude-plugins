---
name: build-list
description: "This skill should be used when the user asks to \"営業先リストを作って\", \"営業先を探して\", \"見込み客を集めて\", \"ターゲットを探索して\", or wants to build a prospect list. BUSINESS.mdとSALES_STRATEGY.mdに基づきWeb探索で営業先候補を収集しDBに登録する。"
argument-hint: "<project-directory-name> [目標件数=30]"
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

### 1. 準備

- プロジェクトディレクトリ名: `$0`（必須）
- 目標件数: `$1`（省略時: 30。厳密でなく「だいたいN件」で良い）

以下を読み込む:
- `$0/BUSINESS.md`
- `$0/SALES_STRATEGY.md`

存在しない場合は `/strategy` の実行を案内する。

### 2. 既存リストと探索メモの確認

探索を始める前に、以下の2つを確認する:

**2a. 既存リストの傾向:**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "SELECT p.company_name, p.industry, p.website_url FROM prospects p JOIN project_prospects pp ON p.id = pp.prospect_id WHERE pp.project_id = ? ORDER BY p.id DESC LIMIT 50" "$0"
```

**2b. 探索メモ:**

`$0/SEARCH_NOTES.md` が存在すれば読み込む。ここには前回までの探索で得られた知見が記録されている:
- 有用な情報源サイト（まだ掘り切れていないもの）
- 前回使ったキーワードと探索アングル
- 次回に試すべき方向性

これらを踏まえて、今回の探索を前回の続きから始められるようにする。

### 3. 検索戦略の策定

SALES_STRATEGY.mdの「検索キーワード」「ターゲット」セクションを基に、複数の検索クエリを策定する。

検索クエリの種類（ターゲットの種別に応じて適切なものを選ぶ）:
- ターゲット業種 + 地域での検索
- 業界団体・協会・連盟のメンバーリスト
- 業界メディア・ニュースサイトでの営業先収集
- 展示会・イベントの出展者リスト
- 競合のクライアント事例
- 求人サイトでのターゲット探索
- 学校・法人の一覧サイトや公的データベース

### 4. Web探索の実行

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
- 目標件数（`$1`、デフォルト30）に達したら探索を終了する。重複で弾かれた件数はカウントしない（新規登録できた件数でカウント）

**重複が多い場合の探索の深掘り:**

リストが蓄積されてくると、検索上位に出る有名な営業先は既に登録済みで重複が増えてくる。その場合は**ターゲットや戦略自体を変えるのではなく**、同じターゲット内でより深く探索する:

- 検索結果の上位だけでなく、2ページ目・3ページ目以降まで見る
- キーワードに地域名を付加して絞る（例: 「SaaS企業」→「SaaS企業 福岡」「SaaS企業 名古屋」）
- 類義語や関連語でキーワードを変える（例: 「学習塾」→「進学塾」「個別指導」「予備校」）
- 業界特化のポータルサイト・ディレクトリを探して、そこに掲載されている営業先を辿る
- 一覧ページの中で見落としていた営業先を拾う
- 既に登録済みの営業先の「競合」「類似サービス」を検索して芋づる式に見つける

重複で弾かれたら、それを「もうこの方面は掘り尽くした」というシグナルとして、**探索のアングルを変える**（ターゲットを変えるのではなく、探し方を変える）。

### 5. 優先度・マッチ理由の判定

各営業先について、SALES_STRATEGY.mdの基準でマッチ理由（なぜターゲットとして適切か、相手の課題・ニーズを含む）と優先度（1-5）を付与する:
- 1: 最有力（ターゲットに完全合致、ニーズが明確）
- 2: 有力（ターゲットに概ね合致）
- 3: 通常（ターゲット範囲内）
- 4: やや外れる（一部条件のみ合致）
- 5: 要検討（間接的な可能性）

### 6. データベース登録

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
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db "INSERT OR IGNORE INTO project_prospects (project_id, prospect_id, match_reason, priority) VALUES (?, ?, ?, ?)" "$0" "<prospect_id>" "<match_reason>" "<priority>"
```

`project_prospects` には UNIQUE(project_id, prospect_id) 制約があるため、同じプロジェクトへの重複紐付けは自動で弾かれる。

### 7. 結果レポート

以下を報告する:
- 新規登録した営業先数 / 目標件数
- 優先度別の内訳
- チャネル別のカバレッジ（メールあり: N件、フォームあり: N件、SNSあり: N件）
- 重複で弾かれた件数（多かった場合、どのように探索アングルを変えたか簡潔に記載）
- 次のステップとして `/outbound` の実行を案内する

### 8. 探索メモの更新

`$0/SEARCH_NOTES.md` を上書き更新する。以下の構成で、次回の探索に役立つ情報を簡潔に記録する:

```markdown
# 探索メモ
最終更新: YYYY-MM-DD

## 有用な情報源
- （まだ掘り切れていないポータルサイト・一覧ページのURL等）

## 前回の探索で使ったキーワード・アングル
- （今回使った主な検索キーワードとアプローチ）

## 次回に試すべき方向性
- （今回手が回らなかった探索方法、まだ見ていない地域・切り口等）

## 所感
- （重複が多かった方面、意外と見つかった方面など、次回に活かせる気づき）
```

過去の内容は保持せず、常に最新の状態に上書きする。
