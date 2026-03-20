---
name: setup
description: "This skill should be used when the user asks to \"セットアップして\", \"新しいプロジェクトを作成\", \"初期化して\", \"プロジェクトを始めたい\", or wants to set up a new sales project. SQLiteデータベースの初期化と営業プロジェクト用サブディレクトリを作成する。"
argument-hint: "<project-directory-name>"
allowed-tools:
  - Bash
  - Read
  - Write
---

# Setup - プロジェクト初期セットアップ

営業プロジェクトの初期セットアップを行うスキル。SQLiteデータベースの初期化と、製品/サービスごとのサブディレクトリを作成する。

## 実行手順

### 1. 引数の確認

引数としてプロジェクトディレクトリ名を受け取る（例: `product-a-sales`）。引数がない場合はエラーを返す。

### 2. データベース初期化

`data.db` がプロジェクトルートに存在しない場合のみ、初期化スクリプトを実行する:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/init-db.sh
```

既にDBが存在する場合はスキップし、その旨を報告する。

### 3. サブディレクトリ作成

プロジェクトルート直下に指定名のディレクトリを作成する:

```bash
mkdir -p <project-directory-name>
```

既に存在する場合はスキップ。

### 4. プロジェクト登録

DBの `projects` テーブルにプロジェクトを登録する:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/query-db.sh "INSERT OR IGNORE INTO projects (name, directory) VALUES ('<name>', '<directory>');"
```

### 5. 完了報告

以下を報告する:
- データベースの状態（新規作成 or 既存）
- 作成したディレクトリパス
- 次のステップとして `/strategy` の実行を案内する
