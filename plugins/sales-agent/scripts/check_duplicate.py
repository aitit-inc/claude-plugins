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

import argparse
import json
import re
import sys

from sales_db import DuplicateMatch, get_connection


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="営業先の重複チェック。確実な判定から順にチェックし、マッチした候補を JSON で出力する。",
    )
    parser.add_argument("db_path", help="SQLite データベースのパス")
    parser.add_argument("--email", help="メールアドレスで完全一致チェック")
    parser.add_argument("--sns", nargs=2, metavar=("KEY", "VALUE"), help="SNS アカウントで完全一致チェック（例: --sns x @account）")
    parser.add_argument("--corporate-number", help="法人番号で完全一致チェック")
    parser.add_argument("--company-name", help="名称で完全一致チェック")
    parser.add_argument("--website-url", help="ウェブサイトのドメインで一致チェック")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    conn = get_connection(args.db_path)
    matches: list[DuplicateMatch] = []

    try:
        if args.email:
            matches.extend(check_email(conn, args.email))

        if args.sns:
            matches.extend(check_sns(conn, args.sns[0], args.sns[1]))

        if args.corporate_number:
            matches.extend(check_corporate_number(conn, args.corporate_number))

        if args.company_name:
            matches.extend(check_company_name(conn, args.company_name))

        if args.website_url:
            matches.extend(check_website_domain(conn, args.website_url))
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
