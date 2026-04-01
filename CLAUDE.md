# Claude Code プラグイン開発リポジトリ

SurpassOne Inc. が提供する Claude Code プラグインのマーケットプレイスリポジトリ。

## リポジトリ構成

```
.claude-plugin/marketplace.json  # マーケットプレイス定義
plugins/<plugin-name>/           # 各プラグイン
```

## プラグインの標準構成

各プラグインは `plugins/<plugin-name>/` 配下に以下の構造で配置する:

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json       # プラグインマニフェスト（必須）
├── commands/              # スラッシュコマンド（.md）
├── agents/                # サブエージェント定義（.md）
├── skills/                # スキル（各サブディレクトリにSKILL.md）
├── hooks/                 # イベントフック
├── scripts/               # ヘルパースクリプト
└── README.md
```

## 開発ルール

- プラグイン名は kebab-case
- 新しいプラグインを追加したら `.claude-plugin/marketplace.json` の `plugins` 配列にも登録する
- 各プラグインは独立して動作すること（プラグイン間の依存禁止）
- パス参照は `${CLAUDE_PLUGIN_ROOT}` を使い、ハードコードしない
- 言語: 日本語（コード内コメント・ドキュメント共に）

## リリース
plugins/sales-agent/.claude-plugin/plugin.json
ここのバージョンをあげてコミット＆プッシュする。
バージョンについて特に指示がなければ、x.y.z のzをインクリメントすること。
バージョン上げる時は先にコード類をコミットしてから、バージョンアップだけのコミットを作る。
コミットメッセージは "chore: :bookmark: bump version to x.y.z" にする。
