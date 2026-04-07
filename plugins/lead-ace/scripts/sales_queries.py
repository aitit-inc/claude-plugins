#!/usr/bin/env python3
"""営業DBの定型クエリ実行スクリプト

Usage:
  sales_queries.py <db_path> <command> [args...]

シェルのエスケープ問題を回避するため、シングルクォートを含む複雑なSQLを
名前付きサブコマンドとして実行する。

Commands:
  list-projects                        全プロジェクト一覧
  project-exists <project_id>          プロジェクトの存在確認
  count-reachable <project_id>         アプローチ可能な未送信営業先数（email/form/SNSいずれかあり）
  list-reachable <project_id> <limit>  アプローチ可能な未送信営業先リスト（email→form→SNSの優先順）
  recent-outreach <project_id>         直近4営業日以内のアプローチ済み営業先
  data-sufficiency <project_id>        evaluate用のデータ充足度チェック
  last-evaluation <project_id>         最新のevaluation日時
  existing-list <project_id>           登録済み営業先の直近50件
  all-prospect-identifiers <project_id>  全登録済み営業先の名前・URL一覧（重複回避用）
"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Callable

from sales_db import error_exit, get_connection, print_json, rows_to_dicts  # pyright: ignore[reportMissingModuleSource]


# ---------------------------------------------------------------------------
# クエリ定義
# ---------------------------------------------------------------------------

def cmd_list_projects(conn: sqlite3.Connection, args: list[str]) -> None:
    """全プロジェクト一覧"""
    cursor = conn.execute(
        "SELECT id, created_at FROM projects ORDER BY created_at ASC",
    )
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_project_exists(conn: sqlite3.Connection, args: list[str]) -> None:
    """プロジェクトの存在確認"""
    if len(args) < 1:
        error_exit("Usage: project-exists <project_id>")
    cursor = conn.execute("SELECT id FROM projects WHERE id = ?", (args[0],))
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_count_reachable(conn: sqlite3.Connection, args: list[str]) -> None:
    """アプローチ可能な未送信営業先数（email/form/SNSいずれかあり）"""
    if len(args) < 1:
        error_exit("Usage: count-reachable <project_id>")
    cursor = conn.execute(
        "SELECT COUNT(*) as count"
        " FROM project_prospects pp"
        " JOIN prospects p ON pp.prospect_id = p.id"
        " WHERE pp.project_id = ? AND pp.status = 'new'"
        " AND p.do_not_contact = 0"
        " AND ("
        "   (p.email IS NOT NULL AND p.email != '')"
        "   OR (p.contact_form_url IS NOT NULL AND p.contact_form_url != '')"
        "   OR (p.sns_accounts IS NOT NULL AND p.sns_accounts != '{}')"
        " )",
        (args[0],),
    )
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_list_reachable(conn: sqlite3.Connection, args: list[str]) -> None:
    """アプローチ可能な未送信営業先リスト（email→form→SNSの優先順）"""
    if len(args) < 1:
        error_exit("Usage: list-reachable <project_id> [limit]")
    if len(args) < 2:
        args.append("30")
    cursor = conn.execute(
        "SELECT p.id, p.company_name, p.overview, p.email,"
        " p.contact_form_url, p.sns_accounts, pp.match_reason, pp.priority"
        " FROM prospects p"
        " JOIN project_prospects pp ON p.id = pp.prospect_id"
        " WHERE pp.project_id = ? AND pp.status = 'new'"
        " AND p.do_not_contact = 0"
        " AND ("
        "   (p.email IS NOT NULL AND p.email != '')"
        "   OR (p.contact_form_url IS NOT NULL AND p.contact_form_url != '')"
        "   OR (p.sns_accounts IS NOT NULL AND p.sns_accounts != '{}')"
        " )"
        " ORDER BY"
        "   CASE WHEN p.email IS NOT NULL AND p.email != '' THEN 0 ELSE 1 END,"
        "   CASE WHEN p.contact_form_url IS NOT NULL AND p.contact_form_url != ''"
        "     THEN 0 ELSE 1 END,"
        "   CASE WHEN p.sns_accounts IS NOT NULL AND p.sns_accounts != '{}'"
        "     THEN 0 ELSE 1 END,"
        "   pp.priority ASC, p.id ASC"
        " LIMIT ?",
        (args[0], args[1]),
    )
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_recent_outreach(conn: sqlite3.Connection, args: list[str]) -> None:
    """直近4営業日以内のアプローチ済み営業先"""
    if len(args) < 1:
        error_exit("Usage: recent-outreach <project_id>")
    cursor = conn.execute(
        "SELECT p.id, p.company_name, p.email, p.website_url, p.sns_accounts,"
        " o.id as outreach_id, o.channel, o.subject, o.sent_at"
        " FROM prospects p"
        " JOIN project_prospects pp ON p.id = pp.prospect_id"
        " JOIN outreach_logs o ON p.id = o.prospect_id AND o.project_id = pp.project_id"
        " WHERE pp.project_id = ? AND pp.status = 'contacted'"
        " AND o.sent_at >= datetime('now', 'localtime', '-6 days')"
        " ORDER BY o.sent_at ASC",
        (args[0],),
    )
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_data_sufficiency(conn: sqlite3.Connection, args: list[str]) -> None:
    """evaluate用のデータ充足度チェック"""
    if len(args) < 1:
        error_exit("Usage: data-sufficiency <project_id>")
    cursor = conn.execute(
        "SELECT COUNT(*) as total_sent, MAX(sent_at) as last_sent"
        " FROM outreach_logs"
        " WHERE project_id = ? AND status = 'sent'",
        (args[0],),
    )
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_last_evaluation(conn: sqlite3.Connection, args: list[str]) -> None:
    """最新のevaluation日時"""
    if len(args) < 1:
        error_exit("Usage: last-evaluation <project_id>")
    cursor = conn.execute(
        "SELECT evaluation_date"
        " FROM evaluations"
        " WHERE project_id = ?"
        " ORDER BY evaluation_date DESC LIMIT 1",
        (args[0],),
    )
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_existing_list(conn: sqlite3.Connection, args: list[str]) -> None:
    """登録済み営業先の直近50件"""
    if len(args) < 1:
        error_exit("Usage: existing-list <project_id>")
    cursor = conn.execute(
        "SELECT p.company_name, p.industry, p.website_url"
        " FROM prospects p"
        " JOIN project_prospects pp ON p.id = pp.prospect_id"
        " WHERE pp.project_id = ?"
        " ORDER BY p.id DESC LIMIT 50",
        (args[0],),
    )
    print_json(rows_to_dicts(cursor.fetchall()))


def cmd_all_prospect_identifiers(conn: sqlite3.Connection, args: list[str]) -> None:
    """全登録済み営業先の名前・URL一覧（重複回避用）"""
    if len(args) < 1:
        error_exit("Usage: all-prospect-identifiers <project_id>")
    cursor = conn.execute(
        "SELECT p.company_name, p.website_url"
        " FROM prospects p"
        " JOIN project_prospects pp ON p.id = pp.prospect_id"
        " WHERE pp.project_id = ?",
        (args[0],),
    )
    print_json(rows_to_dicts(cursor.fetchall()))


# ---------------------------------------------------------------------------
# コマンドディスパッチ
# ---------------------------------------------------------------------------

COMMANDS: dict[str, tuple[str, Callable[[sqlite3.Connection, list[str]], None]]] = {
    "list-projects": ("全プロジェクト一覧", cmd_list_projects),
    "project-exists": ("プロジェクトの存在確認", cmd_project_exists),
    "count-reachable": ("アプローチ可能な未送信営業先数（email/form/SNSいずれかあり）", cmd_count_reachable),
    "list-reachable": ("未送信営業先リスト（email→form→SNS優先順）", cmd_list_reachable),
    "recent-outreach": ("直近アプローチ済み営業先", cmd_recent_outreach),
    "data-sufficiency": ("evaluate用データ充足度", cmd_data_sufficiency),
    "last-evaluation": ("最新evaluation日時", cmd_last_evaluation),
    "existing-list": ("登録済み営業先の直近50件", cmd_existing_list),
    "all-prospect-identifiers": ("全登録済み営業先の名前・URL一覧", cmd_all_prospect_identifiers),
}


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: sales_queries.py <db_path> <command> [args...]", file=sys.stderr)
        print("\nCommands:", file=sys.stderr)
        for name, (desc, _) in COMMANDS.items():
            print(f"  {name:20s} {desc}", file=sys.stderr)
        sys.exit(1)

    db_path = sys.argv[1]
    command = sys.argv[2]
    args = sys.argv[3:]

    if command not in COMMANDS:
        error_exit(f"Unknown command: {command}. Use -h for help.")

    _, handler = COMMANDS[command]
    conn = get_connection(db_path)
    try:
        handler(conn, args)
    except Exception as e:
        error_exit(str(e))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
