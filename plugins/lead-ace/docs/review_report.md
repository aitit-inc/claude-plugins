# Lead Ace プラグイン レビュー指摘事項タスクリスト

レビュー実施日: 2026-04-06
対象バージョン: 0.3.1

---

## Critical（即修正）

### C-1. check_duplicate.py `check_sns` の SQLインジェクション脆弱性

- [x] 修正する

**ファイル:** `scripts/check_duplicate.py` L62-65

**問題:** `sns_key` が f-string でSQL文に直接埋め込まれている。

```python
f"AND json_extract(sns_accounts, '$.{sns_key}') = ?"
```

`sns_key` はCLIの `--sns KEY VALUE` やAI生成JSONのキーから来るため、悪意ある値（例: `') OR 1=1--`）でSQLインジェクションが成立する。

**修正方法:** ホワイトリスト検証を追加する。

```python
ALLOWED_SNS_KEYS = {"twitter", "x", "linkedin", "facebook", "instagram"}
if sns_key not in ALLOWED_SNS_KEYS:
    return []
```

---

### C-2. merge_prospects.py `make_key` で `None` が `"None"` 文字列になる

- [x] 修正する

**ファイル:** `scripts/merge_prospects.py` L37

**問題:**

```python
url = str(entry.get("website_url", ""))
```

JSON入力で `"website_url": null` の場合、`entry.get("website_url", "")` は `None` を返す（キーは存在するためデフォルト値が使われない）。`str(None)` → `"None"` → `extract_domain("None")` → `"none"` となり、`website_url` が null の全候補が同一ドメインとして誤マッチする。

**修正方法:**

```python
url = entry.get("website_url") or ""
```

---

## High（早期修正推奨）

### H-1. `list-reachable` 全件取得時にエラーになる

- [x] 修正する

**ファイル:** `scripts/sales_queries.py` L72-73, `skills/outbound/SKILL.md` L42, L57

**問題:** outbound SKILL.md ステップ1で「件数の指定がない場合は全件を対象とする」と記載しているが、`sales_queries.py` の `cmd_list_reachable` は `if len(args) < 2: error_exit(...)` で引数2つ（project_id, limit）を必須にしている。ユーザーが `/outbound project-a`（件数省略）で起動すると `$1` が空になりエラー。

**修正方法（いずれか）:**

- A: `sales_queries.py` で limit 省略時のデフォルト値を設定する（`limit = args[1] if len(args) >= 2 else "999999"`）
- B: outbound SKILL.md に「`$1` が空の場合は `999999` を指定する」と明記する

---

### H-2. daily-cycle ステップ8c の参照番号誤り（`7b` → `8b`）

- [x] 修正する

**ファイル:** `skills/daily-cycle/SKILL.md` L235

**問題:** 「7b で絞り込まれた新規候補を」→ 正しくは「8b」。ステップ7は outbound であり、8b が重複フィルタ。AIが誤って outbound の結果を参照する可能性がある。

**修正方法:** `7b` → `8b` に修正する。

---

### H-3. delete-project の複数DELETEがトランザクション未保護

- [x] 修正する

**ファイル:** `skills/delete-project/SKILL.md` L41-46

**問題:** 5つのDELETE文を個別の `query_db.py` 呼び出しで実行。各呼び出しは独立したDB接続・トランザクションのため、途中で1つが失敗するとデータ不整合が発生する（例: outreach_logs は削除されたが responses は残っている状態）。

**修正方法（いずれか）:**

- A: 専用スクリプト `delete_project.py` を作成し、1トランザクションで全DELETEを実行
- B: `query_db.py` を複数SQL対応にする（セミコロン区切り等）

---

### H-4. evaluate の evaluation-queries.sql 実行手順が曖昧

- [x] 修正する

**ファイル:** `skills/evaluate/SKILL.md` L33, `skills/evaluate/references/evaluation-queries.sql`

**問題:** SKILL.md に「`<project_id>` を取得して置換し、順次実行する」とあるが、具体的な実行方法が不明。テキスト置換でSQLを組み立てるとSQLインジェクションのリスクがある。`query_db.py` の `?` パラメータバインディングを使うべきだが、`<project_id>` を `?` に置換して渡すのか明示されていない。

**修正方法:**

- evaluation-queries.sql の `<project_id>` を `?` に統一する
- SKILL.md に具体的な実行コマンド例を記載する:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query_db.py data.db \
  "SELECT COUNT(*) as total_outreach FROM outreach_logs WHERE project_id = ?" "$0"
```

加えて、evaluate SKILL.md のパス参照に `${CLAUDE_PLUGIN_ROOT}` プレフィックスを追加する:

```
`${CLAUDE_PLUGIN_ROOT}/skills/evaluate/references/evaluation-queries.sql` のクエリテンプレートを使い
```

---

### H-5. daily-cycle ステップ9c/9d の順序問題（一時ファイルがコミットされる）

- [x] 修正する

**ファイル:** `skills/daily-cycle/SKILL.md` L330-342

**問題:** ステップ9c で `git add .` → ステップ9d で `.tmp/` 削除、の順序になっている。`git add .` により `.tmp/` 内の一時ファイル（check-results-summary.md, evaluate-summary.md, outbound-batch-N.md 等）がステージングされ、コミット＆プッシュされてしまう。

**修正方法:** 9d（一時ファイル削除）を 9c（コミット・プッシュ）の前に移動する。

```markdown
**9c. 一時ファイルの削除**
rm -rf "$0/.tmp"

**9d. 作業結果のコミット・プッシュ**
git add . && git commit -m "work: :e-mail: $0" && git push
```

加えて、`git add .` を明示的なファイル指定に変更することも推奨:

```bash
git add data.db "$0/" && git commit -m "work: :e-mail: $0" && git push
```

---

### H-6. daily-cycle ステップ8c2 で WebSearch が allowed-tools に未含

- [x] 修正する（8c2をサブエージェント化して解消）

**ファイル:** `skills/daily-cycle/SKILL.md` L5-8, L245-247

**問題:** ステップ8c2「連絡先なし候補の再探索（メインコンテキスト）」で WebSearch を使うが、daily-cycle の frontmatter allowed-tools は `Bash`, `Read`, `Agent` の3つのみ。WebSearch が含まれていない。

**修正方法（いずれか）:**

- A: daily-cycle の allowed-tools に `WebSearch`, `WebFetch` を追加する
- B: ステップ8c2をサブエージェント内で完結させる設計に変更する

---

### H-7. sales_queries.py の COMMANDS 辞書の型定義が `object`

- [x] 修正する

**ファイル:** `scripts/sales_queries.py` L177

**問題:**

```python
COMMANDS: dict[str, tuple[str, object]] = {
```

`object` では型チェッカーが `handler(conn, args)` の呼び出しを検証できない。

**修正方法:**

```python
from collections.abc import Callable

COMMANDS: dict[str, tuple[str, Callable[[sqlite3.Connection, list[str]], None]]] = {
```

---

### H-8. license.py の register_project に TOCTOU 競合状態

- [x] 修正する

**ファイル:** `scripts/license.py` L67-82

**問題:** `list_projects()` で読み取り（ファイルロック取得→解放）してから `open(PROJECTS_FILE, "a")` で書き込み（ロック取得→書き込み→解放）する間に、別プロセスが同じパスを追記する可能性がある。結果として同一パスが2行登録される。

**修正方法:** 読み取りと書き込みを同一ロック内で行う。

```python
def register_project(project_path: str) -> str:
    ensure_leadace_dir()
    path = os.path.abspath(project_path)
    with open(PROJECTS_FILE, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        lines = f.readlines()
        projects = [l.strip() for l in lines if l.strip()]
        if path in projects:
            return "ALREADY_REGISTERED"
        if not is_paid() and len(projects) >= 1:
            return "FREE_LIMIT"
        f.write(path + "\n")
    return "REGISTERED"
```

---

## Medium（計画的修正推奨）

### M-1. extract_domain が3箇所に重複定義、check_duplicate.py 版だけ `.lower()` なし

- [x] 修正する

**ファイル:** `scripts/check_duplicate.py` L31-36, `scripts/filter_duplicates.py` L27-32, `scripts/merge_prospects.py` L26-31

**問題:** 3箇所で `extract_domain` が個別定義されており、`check_duplicate.py` 版だけ `.lower()` を呼んでいない。`Example.com` と `example.com` が異なるドメインとして扱われる。

**修正方法:** `sales_db.py` に統一定義して3箇所からインポートする。`.lower()` を含める。

---

### M-2. SEARCH_NOTES.md の上書き（build-list）と追記（evaluate）が矛盾

- [x] 修正する

**ファイル:** `skills/build-list/SKILL.md` L247, `skills/evaluate/SKILL.md` L107-114

**問題:** build-list ステップ9で「過去の内容は保持せず、常に最新の状態に上書きする」、evaluate ステップ4で「追記は既存の SEARCH_NOTES.md の内容を保持したまま末尾に追加する」。daily-cycle の実行フロー（check-results → evaluate → outbound → build-list）では evaluate が追記した内容が同サイクル内の build-list で消失する。

**修正方法:** build-list のステップ9を「evaluate からの追記（`## 反応パターンからの探索ヒント` セクション等）があればそれを保持した上で更新する」に変更する。

---

### M-3. outbound のフォーム送信・SNS DM のログ記録が非アトミック

- [x] 修正する

**ファイル:** `skills/outbound/SKILL.md` L121-124, L149-153

**問題:** メール送信は `send_and_log.py` でアトミック（送信+ログ+ステータス更新が1スクリプト）だが、フォーム送信（ステップ4）とSNS DM（ステップ5）では `query_db.py` で INSERT + UPDATE を2コマンドに分けて実行。1つ目が成功し2つ目が失敗すると、outreach_logs にログはあるがステータスが `new` のまま → 次回再アプローチされる可能性。

**修正方法（いずれか）:**

- A: SKILL.md で「2つのコマンドは `&&` で連結して実行する」ことを明示する
- B: `send_and_log.py` にフォーム/SNS用モード（送信処理なし、ログ+ステータス更新のみ）を追加する

---

### M-4. check-results の `inactive` と outbound の `unreachable` の使い分けが不明確

- [x] 修正する

**ファイル:** `skills/check-results/SKILL.md` L118, `skills/outbound/SKILL.md` L157-168, `scripts/sales-db.sql`

**問題:** check-results ではバウンス時に `inactive` を使い、outbound ではアプローチ不可時に `unreachable` を使う。スキーマのコメントには `new, contacted, responded, converted, rejected, inactive` のみで `unreachable` が含まれていない。2つのステータスの違いが定義されていない。

**修正方法:** スキーマコメントに `unreachable` を追加し、`inactive`（外部要因で非アクティブ）と `unreachable`（構造的にアプローチ不可）の定義を明記する。

---

### M-5. delete-project で prospects テーブルが削除されない

- [x] 対応する（H-3 対応時に delete-project SKILL.md に注記を追加済み）

**ファイル:** `skills/delete-project/SKILL.md` ステップ4

**問題:** `project_prospects`（中間テーブル）は削除されるが、`prospects` 本体は削除されない。他プロジェクトと共有される設計だが、ドキュメントに明記されていない。どのプロジェクトにも紐づかない孤立レコードが残り続ける。

**修正方法:** 方針を明示する。例: ステップ4の末尾に「※ prospects テーブルのレコードは他プロジェクトで再利用される可能性があるため削除しません」と注記。または、孤立レコード削除クエリを追加する。

---

### M-6. count-reachable と list-reachable の対象範囲の不一致

- [x] 修正する

**ファイル:** `scripts/sales_queries.py` L55-67 (count-reachable), L70-96 (list-reachable)

**問題:** `count-reachable` は email/form がある営業先のみカウント（SNSのみを除外）。`list-reachable` は SNSのみの営業先も返す（L84: `sns_accounts IS NOT NULL` を含む条件）。daily-cycle ステップ6でカウントし、ステップ7でリスト取得すると、カウントより多い件数が返される。

**修正方法:** 両コマンドの条件を統一する（SNSのみも含めるか除外するかを揃える）。

---

### M-7. check_duplicate.py 全関数の引数 `conn: object` 型

- [x] 修正する

**ファイル:** `scripts/check_duplicate.py` L39, L58, L79, L98, L117

**問題:** 全ての `check_*` 関数で `conn: object` と宣言し、関数内で `assert isinstance(conn, sqlite3.Connection)` している。型安全性が損なわれている。

**修正方法:** `conn: sqlite3.Connection` に変更し、冒頭に `import sqlite3` を追加（関数内の import と assert を削除）。

---

### M-8. company_name の大文字小文字・全角半角の正規化なし

- [x] 修正する

**ファイル:** `scripts/filter_duplicates.py` L83, `scripts/check_duplicate.py` L102-103

**問題:** 完全一致のみで判定するため、「株式会社Example」と「株式会社EXAMPLE」「株式会社Ｅｘａｍｐｌｅ」は別扱い。日本語企業名では全角/半角の揺れが起きやすい。

**修正方法:** 比較前に正規化処理（`.lower()` + unicodedata.normalize('NFKC')）を適用する。

---

### M-9. send_and_log.py で project_prospects の該当行がない場合にサイレント成功

- [x] 修正する

**ファイル:** `scripts/send_and_log.py`

**問題:** `record_result` で `UPDATE project_prospects` のUPDATE対象が0行の場合、`cursor.rowcount` をチェックせずサイレントに成功する。プロジェクト未紐付けの prospect に送信した場合にステータスが更新されない。

**修正方法:** `cursor.rowcount == 0` の場合に stderr へ警告を出力する。

---

### M-10. form-filling.md の営業お断り時に既存 notes を上書きしてしまう

- [x] 修正する（M-3 対応時に COALESCE パターンで修正済み）

**ファイル:** `skills/outbound/references/form-filling.md` L33

**問題:**

```sql
UPDATE prospects SET do_not_contact=1, notes='営業お断りの記載あり（フォームページ）' ...
```

固定文字列で `notes` を上書きするため、既存の notes が消える。check-results SKILL.md ステップ5では既存 notes の保持を意識している（`<既存のnotesがあれば保持>`）が、form-filling.md では考慮なし。

**修正方法:**

```sql
UPDATE prospects SET do_not_contact=1,
  notes = CASE WHEN notes IS NOT NULL AND notes != ''
    THEN notes || CHAR(10) || '営業お断りの記載あり（フォームページ）'
    ELSE '営業お断りの記載あり（フォームページ）' END,
  updated_at=datetime('now', 'localtime') WHERE id=?
```

---

### M-11. query_db.py の SQL 文種別判定が脆弱

- [x] 修正する

**ファイル:** `scripts/query_db.py` L33

**問題:** `sql.strip().upper().split()[0]` で先頭トークンのみ判定。以下のケースで誤判定:

- `WITH ... SELECT ...` → `stmt_type = "WITH"` → else 節に入り commit される（SELECT なのに）
- コメント付き `-- comment\nSELECT ...` → `stmt_type = "--"` → else 節

**修正方法:** コメント除去後、WITH 句を考慮した判定に改善する:

```python
clean_sql = re.sub(r'--[^\n]*', '', sql).strip().upper()
# WITH 句は後続の SELECT/INSERT/UPDATE/DELETE で判定
if clean_sql.startswith("WITH"):
    # WITH ... SELECT の場合
    if "SELECT" in clean_sql:
        stmt_type = "SELECT"
    else:
        stmt_type = clean_sql.split()[-1]  # fallback
else:
    stmt_type = clean_sql.split()[0]
```

---

### M-12. daily-cycle サブエージェントの allowed-tools 未指定

- [x] 修正する（サブエージェントに allowed-tools 指定は不要。ステップ3 の記載も削除して統一）

**ファイル:** `skills/daily-cycle/SKILL.md` ステップ4, 5, 7

**問題:** check-results サブエージェント（ステップ4）、evaluate サブエージェント（ステップ5）、outbound サブエージェント（ステップ7）のプロンプトに allowed-tools が明示されていない。ステップ3の開始通知では `Bash, Read` が明示されている。

check-results は Gmail MCP + Chrome MCP、evaluate は `Bash, Read, Write, WebSearch, WebFetch`、outbound は `Bash, Read, Write, WebFetch` + Chrome MCP が必要。

**修正方法:** 各サブエージェントのプロンプト仕様に allowed-tools を明記する。

---

### M-13. setup の環境チェック（ステップ3）が実質デッドコード

- [x] 修正する（環境チェックをステップ2に、ライセンスチェックをステップ3に入れ替え）

**ファイル:** `skills/setup/SKILL.md`

**問題:** ステップ3で「python3 が使えない場合は中断」と書いているが、ステップ2のライセンスチェックが既に `python3` を使用。python3 がなければステップ2でエラーになるため、ステップ3の python3 不在ガイダンスに到達しない。

**修正方法:** 環境チェック（python3の存在確認）をステップ2のライセンスチェックより前（ステップ1の後）に移動する。または、ステップ3の python3 チェックを削除して gog/Git のチェックのみ残す。

---

### M-14. init_db.py の executescript 後の conn.commit() は冗長

- [x] 修正する

**ファイル:** `scripts/init_db.py`

**問題:** `conn.executescript()` は内部で暗黙の COMMIT を発行するため、直後の `conn.commit()` は冗長。害はないが、動作を誤解させる。

**修正方法:** `conn.commit()` を削除する。

---

### M-15. sys.argv 直接参照と argparse の混在

- [x] 統一する（CLAUDE.md に argparse 統一ルールを追記。未使用 import argparse は H-7 で削除済み。既存スクリプトの移行は今後新規修正時に順次対応）

**ファイル:** `scripts/sales_queries.py`, `scripts/filter_duplicates.py`, `scripts/merge_prospects.py`, `scripts/query_db.py`, `scripts/license.py`

**問題:** 一部は argparse を使用（add_prospects.py, send_and_log.py, check_duplicate.py）、一部は sys.argv 直接参照。`--help` が使えないスクリプトがある。

加えて `sales_queries.py` L24 に未使用の `import argparse` が残っている。

**修正方法:** 全スクリプトを argparse に統一するか、少なくとも未使用 import を削除する。

---

### M-16. RESULTS_REPORT.md の追記モードのフォーマット・ローテーションが未定義

- [x] 対応する

**ファイル:** `skills/check-results/SKILL.md` L168

**問題:** 「追記モード」と書かれているが、追記時の日付区切りやセパレータのフォーマットが未定義。追記を繰り返すとファイルが肥大化し、evaluate での読み込み時にコンテキストを圧迫する。

**修正方法:** 追記フォーマット（日付ヘッダ、セパレータ `---` 等）を定義する。必要に応じてローテーション方針（例: 直近10回分のみ保持）を追加する。

---

### M-17. build-list SKILL.md ステップ7のトランザクション記述が実際の挙動とずれている

- [x] 修正する

**ファイル:** `skills/build-list/SKILL.md` L201

**問題:** 「全件を1トランザクションで処理（途中エラーがあっても他のエントリは処理を継続）」と記載。実際の `add_prospects.py` では、個別エントリのバリデーションエラーは continue で処理継続するが、DB例外（IntegrityError 等）の場合は外側の try-except で全件 rollback される。

**修正方法:** 「個別エントリのバリデーションエラーは処理を継続するが、DB例外が発生した場合は全件ロールバックされる」と正確に記述する。

---

### M-18. license.py の list_projects 戻り値型が `list`（要素型なし）

- [x] 修正する

**ファイル:** `scripts/license.py` L104

**問題:** `def list_projects() -> list:` で要素型が不明。`list[str]` とすべき。同様に `main()` にも `-> None` を追加すべき。

**修正方法:** `-> list[str]` に修正。`main` / `ensure_leadace_dir` にも `-> None` を追加。

---

## Low（改善推奨）

### L-1. daily-cycle ステップ9c の `git add .` でセンシティブなファイルがコミットされるリスク

- [x] 対応する（setup SKILL.md に .gitignore 自動作成ステップを追加）

**ファイル:** `skills/daily-cycle/SKILL.md` L335

`.env`、API キー等が存在する場合にコミットされるリスク。setup で `.gitignore` に `.env` 等を追加する指示を含めるか、`git add` の対象を明示する。

---

### L-2. setup-guide.html のバージョンバッジが v0.2.0 のまま

- [x] 対応する（setup-guide.html を削除。別の場所で管理）

**ファイル:** `docs/setup-guide.html` L305

`<span class="badge">v0.2.0</span>` → `v0.3.1` に更新する。

---

### L-3. enrich-contacts.md のステップ番号重複

- [x] 修正する（2番目のステップ3をステップ4に修正）

**ファイル:** `skills/build-list/references/enrich-contacts.md`

ステップ3が2つある（「問い合わせフォームURLの探索」と「SNSアカウントの確認」）。2番目のステップ3をステップ4に修正する。

---

### L-4. 件名文字数制限の不統一

- [ ] 統一する

**ファイル:** `skills/strategy/references/industry-email-templates.md`, `skills/outbound/references/email-guidelines.md`

IT/Web向けは「15文字以内」、汎用は「12文字以内」、email-guidelines では「20文字以内」。基準を統一するか、補足関係を明確にする。

---

### L-5. check_duplicate.py の extract_domain に `.lower()` がない（M-1 で対応）

- [x] M-1 の extract_domain 統合で解消済み。

---

### L-6. Prospect TypedDict の `total=False` で必須フィールドも optional に

- [ ] 検討する

**ファイル:** `scripts/sales_db.py`

`Prospect(TypedDict, total=False)` → 全フィールドが optional になる。`total=True` にして optional フィールドだけ `NotRequired` にする方が型安全。

---

### L-7. check_website_domain がテーブル全件スキャン

- [ ] 検討する

**ファイル:** `scripts/check_duplicate.py` L125-128

全 prospects を取得して Python 側でドメイン比較。レコード数が数万件以上で顕著に遅くなる可能性。

---

### L-8. `mkdir -p $0` のクォーティング不足

- [x] 修正する（L-1 対応時に `mkdir -p "$0"` に修正済み）

**ファイル:** `skills/setup/SKILL.md` ステップ5

`mkdir -p $0` → `mkdir -p "$0"` に修正する。スペースを含むプロジェクト名で問題が発生する。

---

### L-9. improvements_idea.md の問題1-5が対応済みか未対応か不明確

- [ ] 整理する

**ファイル:** `docs/improvements_idea.md`, `docs/tasks.md`

2つのドキュメントの状態管理が分離しており、どの問題が残っているか把握しづらい。

---

### L-10. check_duplicate.py で main() 一致なし時に exit(1)

- [ ] 検討する

CLI として使う場合は問題ないが、SKILL.md からは関数が直接インポートされるため影響なし。grep の慣習には沿っている。現状維持でも可。

---

### L-11. fcntl は macOS/Linux のみ（Windows 非対応）

- [ ] 検討する

**ファイル:** `scripts/license.py` L19

Claude Code は macOS/Linux 想定だが、Windows 対応が必要になった場合は `try/except ImportError` か `filelock` パッケージの使用を検討。

---

### L-12. save_key の明示的 LOCK_UN が冗長

- [ ] 修正する

**ファイル:** `scripts/license.py` L43, L62, L81, L95, L100, L112

`with` ブロックでファイルクローズ時にロックは自動解放されるため、明示的な `fcntl.flock(f, fcntl.LOCK_UN)` は冗長。

---

### L-13. industry-email-templates の件名文字数制限（L-4 と同一）

L-4 で対応。
