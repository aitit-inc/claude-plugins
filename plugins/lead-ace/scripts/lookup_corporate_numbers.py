#!/usr/bin/env python3
"""法人番号が未設定の prospects を国税庁法人番号公表サイトで検索し、organizations に登録するスクリプト

Usage:
  python3 lookup_corporate_numbers.py <db_path> [--limit N] [--dry-run]

corporate_number が NULL の prospects を抽出し、check_corporate_number.py（国税庁サイト検索）
で法人番号を検索する。1件のみヒットした場合は自動採用、複数ヒット時は最も名前が近い候補を選択。
見つかった場合は organizations テーブルに INSERT し、prospects.corporate_number を更新する。

Output: JSON
  {"searched": N, "found": N, "not_found": N, "details": [...]}
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from typing import TypedDict

from check_corporate_number import SearchResult, search  # pyright: ignore[reportMissingModuleSource]
from sales_db import (  # pyright: ignore[reportMissingModuleSource]
    get_connection,
    print_json,
    upsert_organization,
)


# ---------------------------------------------------------------------------
# 型定義
# ---------------------------------------------------------------------------


class LookupDetail(TypedDict, total=False):
    prospect_id: int
    company_name: str
    status: str  # "found" | "ambiguous" | "not_found" | "error"
    corporate_number: str
    address: str
    candidates: list[SearchResult]
    message: str


class LookupResult(TypedDict):
    searched: int
    found: int
    ambiguous: int
    not_found: int
    errors: int
    details: list[LookupDetail]


# ---------------------------------------------------------------------------
# 法人番号検索
# ---------------------------------------------------------------------------

_LEGAL_ENTITY_PATTERN = re.compile(
    r"(株式会社|有限会社|合同会社|一般社団法人|一般財団法人|公益社団法人|"
    r"公益財団法人|学校法人|社会福祉法人|医療法人|NPO法人|特定非営利活動法人)"
)


class LookupHit(TypedDict):
    """1件確定ヒットの結果"""
    number: str
    name: str
    address: str


class LookupAmbiguous(TypedDict):
    """複数候補で確定できなかった結果"""
    candidates: list[SearchResult]


def search_corporate_number(company_name: str) -> LookupHit | LookupAmbiguous | None:
    """国税庁法人番号公表サイトで法人番号を検索する。

    check_corporate_number.py の search() を使用。
    1件ヒット → LookupHit（確定）。
    複数ヒット → LookupAmbiguous（候補一覧、DB更新しない）。
    0件 / エラー → None。
    """
    search_name = unicodedata.normalize("NFKC", company_name).strip()
    clean_name = _LEGAL_ENTITY_PATTERN.sub("", search_name).strip()

    try:
        result = search(clean_name)
    except (RuntimeError, subprocess.TimeoutExpired):
        return None

    candidates: list[SearchResult] = result["results"]
    if not candidates:
        return None

    if len(candidates) == 1:
        c = candidates[0]
        return LookupHit(number=c["number"], name=c["name"], address=c["address"])

    # 複数候補 → 確定できないので候補を返すのみ
    return LookupAmbiguous(candidates=candidates)


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="法人番号未設定の prospects を国税庁法人番号公表サイトで検索し organizations に登録する。",
    )
    _ = parser.add_argument("db_path", help="SQLite データベースのパス")
    _ = parser.add_argument(
        "--limit", type=int, default=20,
        help="検索する最大件数（デフォルト: 20。playwright-cli でブラウザ操作するため件数が多いと時間がかかる）",
    )
    _ = parser.add_argument(
        "--dry-run", action="store_true",
        help="検索のみ実行し、DBは更新しない",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path: str = args.db_path
    limit: int = args.limit
    dry_run: bool = args.dry_run

    conn = get_connection(db_path)

    # corporate_number が NULL の prospects を取得（重複する company_name は1件だけ）
    cursor = conn.execute(
        "SELECT id, company_name, website_url, industry, overview"
        " FROM prospects"
        " WHERE corporate_number IS NULL"
        " GROUP BY company_name"
        " ORDER BY id ASC"
        " LIMIT ?",
        (limit,),
    )
    targets: list[sqlite3.Row] = cursor.fetchall()

    if not targets:
        print("法人番号未設定の prospects はありません。", file=sys.stderr)
        empty: LookupResult = {
            "searched": 0, "found": 0, "ambiguous": 0,
            "not_found": 0, "errors": 0, "details": [],
        }
        print_json(empty)
        return

    print(f"検索対象: {len(targets)}件", file=sys.stderr)

    result: LookupResult = {
        "searched": len(targets),
        "found": 0,
        "ambiguous": 0,
        "not_found": 0,
        "errors": 0,
        "details": [],
    }

    for i, row in enumerate(targets):
        prospect_id: int = row["id"]
        company_name: str = row["company_name"]
        website_url: str = row["website_url"] or ""

        print(f"  [{i + 1}/{len(targets)}] {company_name}...", file=sys.stderr, end=" ")

        detail = LookupDetail(
            prospect_id=prospect_id,
            company_name=company_name,
        )

        try:
            hit = search_corporate_number(company_name)
        except Exception as e:
            detail["status"] = "error"
            detail["message"] = str(e)
            result["errors"] += 1
            result["details"].append(detail)
            print("ERROR", file=sys.stderr)
            continue

        if hit is None:
            # 0件ヒット
            detail["status"] = "not_found"
            result["not_found"] += 1
            print("→ 見つからず", file=sys.stderr)

        elif "candidates" in hit:
            # 複数候補 → DB更新しない、候補を出力
            ambiguous_hit: LookupAmbiguous = hit  # type: ignore[assignment]
            detail["status"] = "ambiguous"
            detail["candidates"] = ambiguous_hit["candidates"]
            detail["message"] = f"{len(ambiguous_hit['candidates'])}件の候補あり。WebSearch等で確認が必要"
            result["ambiguous"] += 1
            names = ", ".join(c["name"] for c in ambiguous_hit["candidates"][:3])
            print(f"→ 複数候補: {names}", file=sys.stderr)

        else:
            # 1件確定
            confirmed_hit: LookupHit = hit  # type: ignore[assignment]
            corp_num = confirmed_hit["number"]
            detail["status"] = "found"
            detail["corporate_number"] = corp_num
            detail["address"] = confirmed_hit["address"]
            result["found"] += 1
            print(f"→ {corp_num} ({confirmed_hit['name']})", file=sys.stderr)

            if not dry_run:
                upsert_organization(
                    conn,
                    corporate_number=corp_num,
                    name=company_name,
                    website_url=website_url,
                    industry=row["industry"],
                    overview=row["overview"],
                    address=confirmed_hit["address"],
                )
                conn.execute(
                    "UPDATE prospects SET corporate_number = ?,"
                    " updated_at = datetime('now', 'localtime')"
                    " WHERE company_name = ? AND corporate_number IS NULL",
                    (corp_num, company_name),
                )

        result["details"].append(detail)

        # playwright-cli のブラウザ操作間隔
        if i < len(targets) - 1:
            time.sleep(2)

    if not dry_run:
        conn.commit()

    conn.close()
    print_json(result)


if __name__ == "__main__":
    main()
