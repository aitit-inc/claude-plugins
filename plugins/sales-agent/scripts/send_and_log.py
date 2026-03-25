#!/usr/bin/env python3
"""メール送信+ログ記録のアトミック実行スクリプト

Usage:
  python3 send_and_log.py <db_path> --project <id> --prospect-id <id> \
    --account <email> --to <email> --subject <subject> \
    [--body <text> | --body-file <path>] [--from <alias>] [--cc <emails>]

gog send でメールを送信し、結果をDBに記録する。
成功時: outreach_logs (status='sent') + project_prospects (status='contacted') を1トランザクションで更新
失敗時: outreach_logs (status='failed', error_message) を記録

Output: JSON
  {"status": "sent"|"failed", "outreach_log_id": N, "error_message": null|"..."}

Exit code: 0 = 送信成功, 1 = 送信失敗（ログは記録済み）, 2 = スクリプトエラー
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from typing import TypedDict

from sales_db import error_exit, get_connection, print_json  # pyright: ignore[reportMissingModuleSource]


# ---------------------------------------------------------------------------
# 型定義
# ---------------------------------------------------------------------------

class SendResult(TypedDict):
    status: str  # "sent" | "failed"
    outreach_log_id: int
    error_message: str | None


# ---------------------------------------------------------------------------
# 処理関数
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "メール送信+ログ記録のアトミック実行。"
            + "gog send でメール送信し、結果をDBに記録する。"
        ),
    )
    _ = parser.add_argument("db_path", help="SQLite データベースのパス")
    _ = parser.add_argument("--project", required=True, help="プロジェクトID")
    _ = parser.add_argument("--prospect-id", type=int, required=True, help="営業先ID")
    _ = parser.add_argument("--account", required=True, help="送信元メールアドレス（gog --account）")
    _ = parser.add_argument("--to", required=True, dest="to_addr", help="宛先メールアドレス")
    _ = parser.add_argument("--subject", required=True, help="件名")
    body_group = parser.add_mutually_exclusive_group(required=True)
    _ = body_group.add_argument("--body", help="本文（短い場合）")
    _ = body_group.add_argument("--body-file", help="本文ファイルパス（長い場合）")
    _ = parser.add_argument("--from", dest="from_addr", help="送信元エイリアス（gog --from）")
    _ = parser.add_argument("--cc", help="CCアドレス（カンマ区切り）")
    return parser


def read_body(body: str | None, body_file: str | None) -> str:
    """送信本文を取得する。"""
    if body is not None:
        return body
    if body_file is not None:
        with open(body_file, encoding="utf-8") as f:
            return f.read()
    return ""


def send_email(
    account: str,
    to_addr: str,
    subject: str,
    body: str | None,
    body_file: str | None,
    from_addr: str | None,
    cc: str | None,
) -> tuple[bool, str | None]:
    """gog send を実行し、(成功フラグ, エラーメッセージ) を返す。"""
    cmd = [
        "gog", "send", "--json", "--no-input",
        "--account", account,
        "--to", to_addr,
        "--subject", subject,
    ]

    if body is not None:
        cmd.extend(["--body", body])
    elif body_file is not None:
        cmd.extend(["--body-file", body_file])

    if from_addr is not None:
        cmd.extend(["--from", from_addr])

    if cc is not None:
        cmd.extend(["--cc", cc])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, "gog send がタイムアウトしました（60秒）"
    except FileNotFoundError:
        return False, "gog コマンドが見つかりません"

    if result.returncode == 0:
        return True, None

    error = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
    return False, error


def record_result(
    conn: sqlite3.Connection,
    project_id: str,
    prospect_id: int,
    subject: str,
    body_text: str,
    success: bool,
    error_message: str | None,
) -> int:
    """送信結果をDBに記録する。1トランザクションで実行。"""
    status = "sent" if success else "failed"

    insert_sql = (
        "INSERT INTO outreach_logs"
        + " (project_id, prospect_id, channel, subject, body, status, error_message)"
        + " VALUES (?, ?, 'email', ?, ?, ?, ?)"
    )
    cursor = conn.execute(
        insert_sql,
        (project_id, prospect_id, subject, body_text, status, error_message),
    )
    log_id = cursor.lastrowid
    if log_id is None:
        raise RuntimeError("INSERT後にlastrowidが取得できませんでした")

    # 送信成功時のみ project_prospects のステータスを更新
    if success:
        update_sql = (
            "UPDATE project_prospects SET status = 'contacted', updated_at = datetime('now')"
            + " WHERE project_id = ? AND prospect_id = ?"
        )
        conn.execute(update_sql, (project_id, prospect_id))

    conn.commit()
    return log_id


def main() -> None:
    args = build_parser().parse_args()

    db_path: str = args.db_path
    project_id: str = args.project
    prospect_id: int = args.prospect_id
    account: str = args.account
    to_addr: str = args.to_addr
    subject: str = args.subject
    body: str | None = args.body
    body_file: str | None = args.body_file
    from_addr: str | None = args.from_addr
    cc: str | None = args.cc

    # 本文取得（DB記録用）
    body_text = read_body(body, body_file)

    # メール送信
    success, error_message = send_email(
        account=account,
        to_addr=to_addr,
        subject=subject,
        body=body,
        body_file=body_file,
        from_addr=from_addr,
        cc=cc,
    )

    # DB記録
    conn = get_connection(db_path)
    try:
        log_id = record_result(
            conn, project_id, prospect_id, subject, body_text, success, error_message,
        )
    except Exception as e:
        conn.rollback()
        error_exit(f"DB記録失敗: {e}")
    finally:
        conn.close()

    result: SendResult = {
        "status": "sent" if success else "failed",
        "outreach_log_id": log_id,
        "error_message": error_message,
    }
    print_json(result)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
