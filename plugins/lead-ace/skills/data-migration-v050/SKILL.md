---
name: data-migration-v050
description: "v0.5.0で追加されたorganizationsテーブルへの既存データ移行。organization_idがNULLのprospectsに法人番号を特定・紐づけする。一時スキル（v0.6.0で削除予定）。"
argument-hint: "[--limit N]"
---

## 概要

v0.5.0 で organizations テーブルを追加し、prospects に organization_id（法人番号FK）を必須化した。
このスキルは、**旧データ（organization_id が NULL の prospects）を新スキーマに移行する**ための一時的なスキル。

## 手順

### 0. プリフライト

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py data.db "$0"
```

### 1. 未移行データの検索

`lookup_corporate_numbers.py` で organization_id が NULL の prospects を検索し、国税庁法人番号公表サイトから法人番号の候補を取得する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lookup_corporate_numbers.py data.db --limit 5
```

`--limit` はユーザーの引数で指定があればそれを使う。省略時は 5。

出力の `details` 配列に各 prospect の候補が入る。以降、1件ずつ確認していく。

### 2. 法人番号の照合・確定

候補の正確性を **必ず** 以下の手順で照合する。`lookup_corporate_numbers.py` の候補をそのまま信用してはならない。

#### 照合の原則

- **業種の整合性**: 営業先が学校なのに株式会社がヒットしていたらそれは別法人
- **所在地の整合性**: 全く異なる都道府県なら要注意
- **名称の整合性**: 類似名の別法人に注意（例: 「○○工業」と「○○工業株式会社」は別法人の可能性）

#### 照合手順

候補が見つかった prospect ごとに:

1. **prospect の情報を確認**: website_url からその営業先が何者かを把握する

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_url.py --url "<prospect の website_url>" --prompt "この法人の正式名称、業種、所在地を抽出して"
```

2. **候補の法人番号を検証**: 候補が1件でも、0件でも、複数件でも必ず実施

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_corporate_number.py "<法人名>"
```

必要に応じて WebSearch で追加調査する。

3. **判定**:
   - **確定**: 法人名・業種・所在地が全て整合 → ステップ3へ
   - **不明**: 情報不足で判断できない → スキップし、ユーザーに報告
   - **該当なし**: 候補が全て無関係 → スキップし、ユーザーに報告

### 3. DB更新

確定した法人番号を `link_organization.py` で一括更新する。

```bash
echo '<json_array>' | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/link_organization.py data.db
```

JSON配列の各オブジェクト:

```json
{
  "prospect_id": 42,
  "corporate_number": "1234567890123",
  "organization_name": "正式法人名（国税庁公表サイトの名称）",
  "address": "東京都新宿区...",
  "name": "営業先名（変更が必要な場合のみ）",
  "department": "部署名（追加が必要な場合のみ）"
}
```

- `prospect_id`, `corporate_number`, `organization_name` は必須
- `address` は check_corporate_number.py の結果から取得できれば含める
- `name` は現在の prospects.name を変更する必要がある場合のみ指定（例: 学校法人の場合、prospects.name を学校名に、organization_name を学校法人名にする）
- `department` は部署を追加する場合のみ指定

### 4. 結果報告

処理結果をユーザーに報告する:

- 確定・更新した件数
- スキップした件数とその理由
- 残りの未移行件数（`SELECT COUNT(*) FROM prospects WHERE organization_id IS NULL`）
