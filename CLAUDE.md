# Claude Code プラグイン開発リポジトリ

SurpassOne Inc. が提供する Claude Code プラグインのマーケットプレイスリポジトリ。現在公開中のプラグインはありません。

## リポジトリ構成

```
.claude-plugin/marketplace.json  # マーケットプレイス定義
plugins/<plugin-name>/           # 各プラグイン（現在は空）
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

## スキルの書き方（公式ベストプラクティス準拠）

- **SKILL.md は500行以下**。超えそうなら references/ に分離する
- **description は250文字以内**（超過分はスキル一覧で切り詰められる）。キーユースケースを先頭に書く
- **references/ は自動読み込みされない**。SKILL.md 内で「いつ・どの条件で読むか」を明示すること
- **references/ のネストは1階層まで**。reference ファイルからさらに別ファイルを参照しない
- **300行超の reference ファイルには目次を付ける**
- **Claude が既に知っている知識は書かない**。トークンの無駄
- **プログレッシブ・ディスクロージャー**: SKILL.md に全手順を書き、条件付きでしか使わない詳細は references/ に置く。常に必要な情報だけ SKILL.md に残す

出典: [Extend Claude with skills](https://code.claude.com/docs/en/skills), [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)

## リリース

プラグインの `plugin.json` のバージョンをあげてコミット＆プッシュする。
バージョンについて特に指示がなければ、x.y.z の z をインクリメントすること（各数字は二桁以上も可。例: 0.3.9 → 0.3.10）。
バージョン上げる時は先にコード類をコミットしてから、バージョンアップだけのコミットを作る。
コミットメッセージは "chore: :bookmark: bump version to x.y.z" にする。
