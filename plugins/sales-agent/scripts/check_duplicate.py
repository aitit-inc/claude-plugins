#!/usr/bin/env python3
"""営業先の重複チェックスクリプト

確実な判定から順にチェックし、マッチした候補を JSON で出力する。
チェック順: email → SNS → 法人番号 → 名称完全一致 → ドメイン一致

Usage:
  check_duplicate.py <db_path> [options]

Options:
  --email <email>
  --sns <key> <value>
  --corporate-number <number>
  --company-name <name>
  --website-url <url>

Output: JSON array of DuplicateMatch objects
Exit code: 0 = match found, 1 = no match, 2 = error
"""

from __future__ import annotations

import json
import re
import sys

from sales_db import DuplicateMatch, error_exit, get_connection


def extract_domain(url: str) -> str:
    """URLからドメインを抽出する。プロトコル・www・パスを除去。"""
    domain = re.sub(r"^https?://", "", url)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0]
    return domain


def check_email(conn: object, email: str) -> list[DuplicateMatch]:
    """email 完全一致チェック"""
    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    cursor = conn.execute(
        "SELECT id, company_name FROM prospects WHERE email = ?",
        (email,),
    )
    return [
        DuplicateMatch(
            match_type="EXACT_MATCH",
            prospect_id=row["id"],
            company_name=row["company_name"],
            reason=f"email一致: {email}",
        )
        for row in cursor
    ]


def check_sns(conn: object, sns_key: str, sns_value: str) -> list[DuplicateMatch]:
    """SNS アカウント完全一致チェック（json_extract 使用）"""
    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    cursor = conn.execute(
        "SELECT id, company_name FROM prospects "
        "WHERE sns_accounts IS NOT NULL "
        f"AND json_extract(sns_accounts, '$.{sns_key}') = ?",
        (sns_value,),
    )
    return [
        DuplicateMatch(
            match_type="EXACT_MATCH",
            prospect_id=row["id"],
            company_name=row["company_name"],
            reason=f"SNS一致: {sns_key}={sns_value}",
        )
        for row in cursor
    ]


def check_corporate_number(conn: object, number: str) -> list[DuplicateMatch]:
    """法人番号完全一致チェック"""
    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    cursor = conn.execute(
        "SELECT id, company_name FROM prospects WHERE corporate_number = ?",
        (number,),
    )
    return [
        DuplicateMatch(
            match_type="EXACT_MATCH",
            prospect_id=row["id"],
            company_name=row["company_name"],
            reason=f"法人番号一致: {number}",
        )
        for row in cursor
    ]


def check_company_name(conn: object, name: str) -> list[DuplicateMatch]:
    """名称完全一致チェック"""
    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    cursor = conn.execute(
        "SELECT id, company_name FROM prospects WHERE company_name = ?",
        (name,),
    )
    return [
        DuplicateMatch(
            match_type="EXACT_MATCH",
            prospect_id=row["id"],
            company_name=row["company_name"],
            reason="名称完全一致",
        )
        for row in cursor
    ]


def check_website_domain(conn: object, url: str) -> list[DuplicateMatch]:
    """ウェブサイトのドメイン一致チェック"""
    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    domain = extract_domain(url)
    if not domain:
        return []

    cursor = conn.execute(
        "SELECT id, company_name, website_url FROM prospects "
        "WHERE website_url IS NOT NULL",
    )
    return [
        DuplicateMatch(
            match_type="POSSIBLE_MATCH",
            prospect_id=row["id"],
            company_name=row["company_name"],
            reason=f"ドメイン一致: {domain}",
        )
        for row in cursor
        if extract_domain(row["website_url"]) == domain
    ]


def parse_args(argv: list[str]) -> tuple[str, dict[str, str | tuple[str, str]]]:
    """コマンドライン引数をパースする。"""
    if len(argv) < 2:
        error_exit(
            "Usage: check_duplicate.py <db_path> "
            "[--email <email>] [--sns <key> <value>] "
            "[--corporate-number <number>] [--company-name <name>] "
            "[--website-url <url>]",
            code=2,
        )

    db_path = argv[1]
    opts: dict[str, str | tuple[str, str]] = {}
    i = 2
    while i < len(argv):
        arg = argv[i]
        if arg == "--email":
            opts["email"] = argv[i + 1]
            i += 2
        elif arg == "--sns":
            opts["sns"] = (argv[i + 1], argv[i + 2])
            i += 3
        elif arg == "--corporate-number":
            opts["corporate_number"] = argv[i + 1]
            i += 2
        elif arg == "--company-name":
            opts["company_name"] = argv[i + 1]
            i += 2
        elif arg == "--website-url":
            opts["website_url"] = argv[i + 1]
            i += 2
        else:
            error_exit(f"Unknown option: {arg}", code=2)
    return db_path, opts


def main() -> None:
    db_path, opts = parse_args(sys.argv)

    conn = get_connection(db_path)
    matches: list[DuplicateMatch] = []

    try:
        if "email" in opts:
            val = opts["email"]
            assert isinstance(val, str)
            matches.extend(check_email(conn, val))

        if "sns" in opts:
            val = opts["sns"]
            assert isinstance(val, tuple)
            matches.extend(check_sns(conn, val[0], val[1]))

        if "corporate_number" in opts:
            val = opts["corporate_number"]
            assert isinstance(val, str)
            matches.extend(check_corporate_number(conn, val))

        if "company_name" in opts:
            val = opts["company_name"]
            assert isinstance(val, str)
            matches.extend(check_company_name(conn, val))

        if "website_url" in opts:
            val = opts["website_url"]
            assert isinstance(val, str)
            matches.extend(check_website_domain(conn, val))
    finally:
        conn.close()

    # 重複排除（同じ prospect_id が複数段階でヒットする場合）
    seen: set[int] = set()
    unique_matches: list[DuplicateMatch] = []
    for m in matches:
        if m["prospect_id"] not in seen:
            seen.add(m["prospect_id"])
            unique_matches.append(m)

    if unique_matches:
        json.dump(unique_matches, sys.stdout, ensure_ascii=False, indent=2)
        print()
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
