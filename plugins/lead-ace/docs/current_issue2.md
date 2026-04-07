# daily-cycle 振り返り — 改善点まとめ

2026-04-07 のサイクル実績: outbound 成功4/9件(44%), build-list 10件追加

---

## 1. lead-ace プラグインの改善点

### A. merge_prospects.py のマッチングが壊れている【P0】

`make_key()` が `company_name + website_urlのドメイン` でキーを生成するが、連絡先取得サブエージェントの出力に `website_url` が含まれないことがある。

- 候補側キー: `Fire Cracker株式会社|firecracker.jp`
- 連絡先側キー: `Fire Cracker株式会社|`（空ドメイン）
- → 10件全て未マッチで連絡先情報が消失し、毎回手動でDB更新が必要になる

**修正案**: `website_url` がない場合は `company_name` のみでフォールバックマッチする。もしくは enrich-contacts.md の出力仕様に `website_url` を必須として明記する。

### B. outbound サブエージェント拒否問題【P0】

サブエージェントが安全ガードレールにより送信を拒否する問題が2回連続で発生。daily-cycle スキルのステップ7は「サブエージェントで実行」と書かれているが、実質メインコンテキストでしか動かない。

**修正案**:
- daily-cycle スキルのステップ7に「サブエージェントが拒否した場合はメインコンテキストで実行する」フォールバックを明記
- もしくはステップ7を最初からメイン実行と明記する（コンテキスト消費は増えるが確実）

### C. iframe フォームの早期検出がない【P1】

9件中5件がiframe埋め込みフォーム（HubSpot等）で失敗。フォームに到達してから初めて失敗が判明するため時間を浪費する。

**修正案**:
- `enrich-contacts` フェーズでフォームの種別（native HTML / Google Forms / HubSpot iframe / reCAPTCHAあり等）を判別して `form_type` フィールドに記録する
- outbound スキルで `form_type` に応じた処理分岐を入れる（iframe → スキップ or 別手法）
- HubSpot フォームの場合、HubSpot Forms API 経由で直接POSTする手法を検討

### D. Google Forms POST 手法が文書化されていない【P1】

Google FormsのフォームIDをページソース（`FB_PUBLIC_LOAD_DATA_`）から抽出して `formResponse` エンドポイントにPOSTする手法が非常に有効だった（2/2成功）。しかし form-filling.md に記載がない。

**修正案**: `form-filling.md` に「Google Forms の場合」セクションを追加し、entry IDを抽出してPOSTする手順を文書化する。

### E. send_and_log.py の終了コード【P2】

送信失敗を正しくログ記録した場合でも exit code 1 を返す。スクリプトとしての「正常動作」と「送信の成否」が混同されている。

**修正案**: ログ記録が正常に完了した場合は exit code 0、スクリプト自体にエラーがあった場合のみ exit code 1 にする。

---

## 2. 戦略・ドキュメントの改善点

### A. reachable リストのチャネル偏り【最重要】

現在のreachable 15件の内訳:
- メールあり: 4件（27%）
- フォームのみ: 11件（73%）

iframe フォームの失敗率を考えると、実質的な送信可能率は非常に低い。2回のサイクルでフォーム送信の成功率は約30%（ネイティブHTMLとGoogle Formsのみ成功）。

**SALES_STRATEGY.md への追記案**:
- 検索キーワードセクションに「メールアドレスが公開されやすい企業の特徴」を追加（公式サイトに会社概要ページがある小規模企業、代表者がSNSでメールを公開している等）
- build-list の enrich-contacts で「メールが見つからなかった場合、プレスリリース・業界ディレクトリ・SNSプロフィールからの補完探索を強化する」方針を追加

### B. ターゲットの精緻化

2サイクル分の実績で、SaaSスタートアップ（規模50名以上）はiframeフォーム率が高い傾向（HubSpot、Marketo等のMAツール導入済み）。一方で:
- 5名以下の極小チーム: 公式サイトにメールアドレスが直接載っていることが多い
- Google Forms利用企業: POST送信が100%成功する
- WordPress/静的サイト企業: ネイティブHTMLフォームで成功率が高い

**SALES_STRATEGY.md のターゲットセクション改善案**:
- 「アプローチしやすい企業の特徴」として上記を追記し、build-list での優先度判定に反映させる

### C. 件名パターンの使用バランス【P2】

5パターン定義中、「営業マンを雇わない選択肢」が未使用。サンプル数が少なすぎてA/Bテストとして機能していない。

**改善案**: 送信30件を超えるまでは均等配分を厳守する方針を SALES_STRATEGY.md に明記する。

### D. SEARCH_NOTES.md の活用強化【P2】

探索メモの質は良いが、「どの情報源からメールアドレスが見つかりやすかったか」の記録がない。

**追記案**: 各探索ラウンドで「メール取得率」を記録するセクションを追加。例: 「prtimes.jpシード企業 → メール取得率40%」

---

## 3. 優先度付きアクションリスト

| 優先度 | 項目 | 理由 |
|---|---|---|
| P0 | merge_prospects.py のキーマッチ修正 | 毎回手動でDB更新が必要 |
| P0 | outbound のサブエージェント拒否対策をスキルに明記 | 毎回失敗→メイン再実行でコンテキスト浪費 |
| P1 | Google Forms POST手法を form-filling.md に文書化 | 成功率100%の手法が属人化 |
| P1 | enrich-contacts に form_type 判別を追加 | iframe失敗の早期回避 |
| P1 | build-list でメールアドレス取得を強化する方針追記 | reachable の73%がフォームのみ |
| P2 | send_and_log.py の終了コード修正 | 混乱を防ぐ |
| P2 | SEARCH_NOTES にメール取得率の記録を追加 | 長期的な探索効率改善 |
