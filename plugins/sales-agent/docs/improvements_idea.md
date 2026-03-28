# スキル改善案（2026-03-28 daily-cycle 実行後の振り返り）

## 1. build-list: 既存営業先を候補収集サブエージェントに渡す【影響度: 大】

**問題:** Phase 1 の候補収集サブエージェントが DB 内の既存営業先を知らないまま探索するため、大半が重複になる（今回 30件中27件が重複）。

**対応:**
- `sales_queries.py` に `list-existing-names` コマンドを追加（company_name + website_url の一覧を返す）
- build-list SKILL.md Phase 1 の冒頭で既存リストを取得し、サブエージェントのプロンプトに「以下は登録済みなので除外」として渡す

## 2. daily-cycle: 6a→6b の間に重複フィルタを挟む【影響度: 大】

**問題:** 6a（候補収集）の結果をそのまま 6b（連絡先取得）に渡すため、重複候補にも連絡先取得サブエージェントが走り、トークン・時間を大量に浪費する。

**対応:** daily-cycle のステップ6の順序を変更:
1. 6a: 候補収集（現状通り）
2. 6b: DB重複チェック（`check_duplicate.py` で一括）→ 新規分のみ抽出
3. 6c: 新規分の連絡先取得（サブエージェント × バッチ）
4. 6d: DB登録

## 3. outbound SKILL.md: `gog send` の記載修正【影響度: 中】

**問題:** SKILL.md 76行目に「gog send でメールを送信」と書いてあり、サブエージェントが `send_and_log.py` を使わず直接 `gog send` を叩いて失敗した（正しくは `gog gmail send`）。

**対応:**
- 76行目を「`gog gmail send` でメールを送信」に修正
- 「メール送信は必ず `send_and_log.py` 経由で行うこと。直接 gog コマンドを叩かない」を注意事項として追記

## 4. outbound SKILL.md: ブラウザ未接続時の SNS ハンドリング【影響度: 中】

**問題:** SNS のみの営業先がブラウザ拡張未接続で送信不可だが、`count-reachable` はこれらもカウントに含む。outbound 件数の計算がずれる。

**対応:**
- outbound SKILL.md の処理開始時に、ブラウザツール（claude-in-chrome）の利用可否を確認するステップを追加
- 利用不可なら SNS-only の営業先をスキップ対象として明示し、件数計算から除外

## 5. sales_queries.py: チャネルフィルタ付き count【影響度: 中】

**問題:** `count-reachable` / `list-reachable` にチャネルフィルタがなく、ブラウザ不可時に email/form のみで絞れない。

**対応:** `list-reachable` と `count-reachable` に `--channel email,form` のようなオプションを追加。

## 6. daily-cycle: build-list の実行判定に経過日数を加える【影響度: 小】

**問題:** リスト残数のみで判定するため、候補が枯渇したエリアで毎回 build-list が空振りする。

**対応:** build-list の条件に「前回 build-list からの経過日数」も加える。直近で実行済みなら頻度を下げる（evaluate と同様の考え方）。`sales_queries.py` に `last-build-list` コマンドも追加。
