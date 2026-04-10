#!/usr/bin/env python3
"""法人番号が未設定の prospects を国税庁法人番号公表サイトで検索し、候補を出力するスクリプト

Usage:
  python3 lookup_corporate_numbers.py <db_path> [--limit N]

corporate_number が NULL の prospects を抽出し、check_corporate_number.py（国税庁サイト検索）
で法人番号の候補を検索する。DBの更新は行わない（候補の確定は LLM または人間が判断する）。

Output: JSON
  {"searched": N, "candidates_found": N, "not_found": N, "details": [...]}
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
from sales_db import get_connection, print_json  # pyright: ignore[reportMissingModuleSource]


# ---------------------------------------------------------------------------
# 型定義
# ---------------------------------------------------------------------------


class LookupDetail(TypedDict, total=False):
    prospect_id: int
    name: str
    status: str  # "candidates_found" | "not_found" | "error"
    candidates: list[SearchResult]
    message: str


class LookupResult(TypedDict):
    searched: int
    candidates_found: int
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


def search_candidates(name: str) -> list[SearchResult]:
    """国税庁法人番号公表サイトで法人番号の候補を検索する。

    自動採用はしない。候補一覧を返すのみ。
    確定は LLM または人間が判断する。
    """
    search_name = unicodedata.normalize("NFKC", name).strip()
    clean_name = _LEGAL_ENTITY_PATTERN.sub("", search_name).strip()

    try:
        result = search(clean_name)
    except (RuntimeError, subprocess.TimeoutExpired):
        return []

    # name が空の候補は除外（パース失敗）
    return [c for c in result["results"] if c["name"].strip()]


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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path: str = args.db_path
    limit: int = args.limit

    conn = get_connection(db_path)

    # corporate_number が NULL の prospects を取得（重複する name は1件だけ）
    cursor = conn.execute(
        "SELECT id, name, website_url"
        " FROM prospects"
        " WHERE corporate_number IS NULL"
        " GROUP BY name"
        " ORDER BY id ASC"
        " LIMIT ?",
        (limit,),
    )
    targets: list[sqlite3.Row] = cursor.fetchall()
    conn.close()

    if not targets:
        print("法人番号未設定の prospects はありません。", file=sys.stderr)
        empty: LookupResult = {
            "searched": 0, "candidates_found": 0,
            "not_found": 0, "errors": 0, "details": [],
        }
        print_json(empty)
        return

    print(f"検索対象: {len(targets)}件", file=sys.stderr)

    result: LookupResult = {
        "searched": len(targets),
        "candidates_found": 0,
        "not_found": 0,
        "errors": 0,
        "details": [],
    }

    for i, row in enumerate(targets):
        prospect_id: int = row["id"]
        name: str = row["name"]

        print(f"  [{i + 1}/{len(targets)}] {name}...", file=sys.stderr, end=" ")

        detail = LookupDetail(
            prospect_id=prospect_id,
            name=name,
        )

        try:
            candidates = search_candidates(name)
        except Exception as e:
            detail["status"] = "error"
            detail["message"] = str(e)
            result["errors"] += 1
            result["details"].append(detail)
            print("ERROR", file=sys.stderr)
            continue

        if candidates:
            detail["status"] = "candidates_found"
            detail["candidates"] = candidates
            detail["message"] = f"{len(candidates)}件の候補。LLM または人間が確認して確定してください"
            result["candidates_found"] += 1
            names = ", ".join(c["name"] for c in candidates[:3])
            print(f"→ {len(candidates)}件: {names}", file=sys.stderr)
        else:
            detail["status"] = "not_found"
            result["not_found"] += 1
            print("→ 見つからず", file=sys.stderr)

        result["details"].append(detail)

        # playwright-cli のブラウザ操作間隔
        if i < len(targets) - 1:
            time.sleep(2)

    print_json(result)


if __name__ == "__main__":
    main()
