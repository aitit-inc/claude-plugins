#!/usr/bin/env python3
"""SQL クエリ実行スクリプト（パラメータバインディング対応）

Usage:
  query_db.py <db_path> <sql> [param1] [param2] ...

SELECT の場合は結果を JSON 配列で stdout に出力する。
INSERT の場合は {"last_id": <rowid>} を出力する。
UPDATE/DELETE の場合は {"rows_affected": <count>} を出力する。

パラメータは SQL 内の ? プレースホルダに順番に対応する。
"""

from __future__ import annotations

import sys

from sales_db import error_exit, get_connection, print_json, rows_to_dicts


def main() -> None:
    if len(sys.argv) < 3:
        error_exit("Usage: query_db.py <db_path> <sql> [param1] [param2] ...")

    db_path = sys.argv[1]
    sql = sys.argv[2]
    params = sys.argv[3:]

    conn = get_connection(db_path)
    try:
        cursor = conn.execute(sql, params)

        stmt_type = sql.strip().upper().split()[0]
        if stmt_type == "SELECT":
            rows = cursor.fetchall()
            print_json(rows_to_dicts(rows))
        elif stmt_type == "INSERT":
            conn.commit()
            print_json({"last_id": cursor.lastrowid})
        else:
            conn.commit()
            print_json({"rows_affected": cursor.rowcount})
    except Exception as e:
        error_exit(str(e))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
