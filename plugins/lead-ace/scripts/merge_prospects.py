#!/usr/bin/env python3
"""候補JSON（Phase 1）と連絡先JSON（Phase 2）をマージするスクリプト

Usage:
  merge_prospects.py <candidates_file> <contacts_file>

Phase 1（候補収集）の出力と Phase 2（連絡先取得）の出力を
company_name + website_url のドメインで突き合わせてマージし、
add_prospects.py に渡せる形式でstdoutに出力する。

マッチしなかった候補は連絡先なし（email=null等）のまま出力する。

Output (stdout): マージ済みJSON配列
Output (stderr): マージ結果のサマリー
"""

from __future__ import annotations

import json
import re
import sys

from sales_db import error_exit, print_json  # pyright: ignore[reportMissingModuleSource]


def extract_domain(url: str) -> str:
    """URLからドメインを抽出する。"""
    domain = re.sub(r"^https?://", "", url)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0]
    return domain.lower()


def make_key(entry: dict[str, object]) -> str:
    """company_name + domain でマッチキーを生成する。"""
    name = str(entry.get("company_name", "")).strip()
    url = str(entry.get("website_url", ""))
    domain = extract_domain(url) if url else ""
    return f"{name}|{domain}"


# 連絡先フィールド（Phase 2 で取得されるもの）
CONTACT_FIELDS = ("email", "contact_form_url", "sns_accounts")


def main() -> None:
    if len(sys.argv) < 3:
        error_exit("Usage: merge_prospects.py <candidates_file> <contacts_file>")

    candidates_path = sys.argv[1]
    contacts_path = sys.argv[2]

    try:
        with open(candidates_path, encoding="utf-8") as f:
            candidates: object = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        error_exit(f"候補ファイル読み込みエラー: {e}")

    try:
        with open(contacts_path, encoding="utf-8") as f:
            contacts: object = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        error_exit(f"連絡先ファイル読み込みエラー: {e}")

    if not isinstance(candidates, list) or not isinstance(contacts, list):
        error_exit("両方のファイルがJSON配列である必要があります")

    # 連絡先をキーでインデックス化
    contacts_index: dict[str, dict[str, object]] = {}
    for contact in contacts:
        if isinstance(contact, dict):
            key = make_key(contact)
            contacts_index[key] = contact

    merged: list[dict[str, object]] = []
    matched_count = 0
    unmatched_names: list[str] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        key = make_key(candidate)
        result: dict[str, object] = dict(candidate)

        if key in contacts_index:
            contact = contacts_index[key]
            for field in CONTACT_FIELDS:
                if field in contact:
                    result[field] = contact[field]
            matched_count += 1
        else:
            for field in CONTACT_FIELDS:
                result.setdefault(field, None)
            unmatched_names.append(str(candidate.get("company_name", "?")))

        merged.append(result)

    print_json(merged)

    print(
        f"マージ結果: 候補 {len(candidates)}件, 連絡先 {len(contacts)}件"
        f" → マッチ {matched_count}件, 未マッチ {len(unmatched_names)}件",
        file=sys.stderr,
    )
    if unmatched_names:
        for name in unmatched_names:
            print(f"  連絡先未マッチ: {name}", file=sys.stderr)


if __name__ == "__main__":
    main()
