#!/usr/bin/env python3
"""候補JSONからDB既存分を除外するフィルタスクリプト

Usage:
  echo '<json_array>' | filter_duplicates.py <db_path> <project_id>

stdin から候補のJSON配列を受け取り、DBに登録済みの営業先を除外して
新規候補のみをstdoutに出力する。

判定基準:
  - company_name の完全一致
  - website_url のドメイン一致

Output (stdout): フィルタ済みJSON配列
Output (stderr): フィルタ結果のサマリー
"""

from __future__ import annotations

import json
import sys

from sales_db import error_exit, extract_domain, get_connection, normalize_name, print_json, rows_to_dicts  # pyright: ignore[reportMissingModuleSource]


def main() -> None:
    if len(sys.argv) < 3:
        error_exit("Usage: filter_duplicates.py <db_path> <project_id>")

    db_path = sys.argv[1]
    project_id = sys.argv[2]

    try:
        candidates: object = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        error_exit(f"JSON parse error: {e}")

    if not isinstance(candidates, list):
        error_exit("入力はJSON配列である必要があります")

    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT p.company_name, p.website_url"
            " FROM prospects p"
            " JOIN project_prospects pp ON p.id = pp.prospect_id"
            " WHERE pp.project_id = ?",
            (project_id,),
        )
        existing = rows_to_dicts(cursor.fetchall())
    finally:
        conn.close()

    existing_names: set[str] = {
        normalize_name(str(row["company_name"])) for row in existing if row.get("company_name")
    }
    existing_domains: set[str] = {
        extract_domain(str(row["website_url"]))
        for row in existing
        if row.get("website_url")
    }

    new_candidates: list[object] = []
    duplicates: list[dict[str, str]] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        raw_name = candidate.get("company_name", "")
        url = candidate.get("website_url", "")
        domain = extract_domain(url) if url else ""

        if normalize_name(raw_name) in existing_names:
            duplicates.append({"company_name": raw_name, "reason": "名称一致"})
        elif domain and domain in existing_domains:
            duplicates.append({"company_name": raw_name, "reason": f"ドメイン一致: {domain}"})
        else:
            new_candidates.append(candidate)

    print_json(new_candidates)

    print(
        f"フィルタ結果: 入力 {len(candidates)}件 → 新規 {len(new_candidates)}件, 重複除外 {len(duplicates)}件",
        file=sys.stderr,
    )
    if duplicates:
        for d in duplicates:
            print(f"  除外: {d['company_name']} ({d['reason']})", file=sys.stderr)


if __name__ == "__main__":
    main()
