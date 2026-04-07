#!/usr/bin/env python3
"""Lead Ace DB 初期化スクリプト

Usage: init_db.py [db_path]
"""

from __future__ import annotations

import sqlite3
import sys

from sales_db import error_exit, get_db_path, get_connection, get_schema_path


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """既存DBに対するスキーマ変更を適用する。冪等に動作する。"""
    cursor = conn.execute("PRAGMA table_info(prospects)")
    columns = {row[1] for row in cursor.fetchall()}

    if "form_type" not in columns:
        conn.execute(
            "ALTER TABLE prospects ADD COLUMN form_type TEXT"
        )
        conn.commit()


def main() -> None:
    db_path = get_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    schema_path = get_schema_path()

    try:
        with open(schema_path) as f:
            schema_sql = f.read()
    except FileNotFoundError:
        error_exit(f"Schema file not found: {schema_path}")

    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        _apply_migrations(conn)
    finally:
        conn.close()

    print(f"Database initialized: {db_path}")


if __name__ == "__main__":
    main()
