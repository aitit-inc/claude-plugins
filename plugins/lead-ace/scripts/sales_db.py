#!/usr/bin/env python3
"""Lead Ace DB - 共有モジュール（型定義・DB接続・共通操作）"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import unicodedata
from typing import NoReturn, TypedDict


# ---------------------------------------------------------------------------
# 型定義
# ---------------------------------------------------------------------------

class Project(TypedDict):
    id: str  # PRIMARY KEY (テキスト、例: "my-product")
    created_at: str
    updated_at: str


class Prospect(TypedDict, total=False):
    id: int
    company_name: str
    corporate_number: str | None
    overview: str
    industry: str | None
    website_url: str
    email: str | None
    contact_form_url: str | None
    sns_accounts: str | None  # JSON string
    do_not_contact: int
    notes: str | None
    created_at: str
    updated_at: str


class ProjectProspect(TypedDict, total=False):
    id: int
    project_id: str
    prospect_id: int
    match_reason: str
    priority: int
    status: str
    created_at: str
    updated_at: str


class OutreachLog(TypedDict, total=False):
    id: int
    project_id: str
    prospect_id: int
    channel: str
    subject: str | None
    body: str
    status: str
    sent_at: str
    error_message: str | None


class Response(TypedDict, total=False):
    id: int
    outreach_log_id: int
    channel: str
    content: str
    sentiment: str
    response_type: str
    received_at: str


class Evaluation(TypedDict, total=False):
    id: int
    project_id: str
    evaluation_date: str
    metrics: str  # JSON string
    findings: str
    improvements: str  # JSON string


class DuplicateMatch(TypedDict):
    match_type: str  # EXACT_MATCH | POSSIBLE_MATCH
    prospect_id: int
    company_name: str
    reason: str


# ---------------------------------------------------------------------------
# DB接続
# ---------------------------------------------------------------------------

def get_db_path(explicit_path: str | None = None) -> str:
    """DBパスを決定する。明示的に指定されていなければCWDの data.db を使う。"""
    if explicit_path:
        return explicit_path
    return os.path.join(os.getcwd(), "data.db")


def get_connection(db_path: str) -> sqlite3.Connection:
    """SQLite接続を取得する。外部キー制約を有効化し、行をdictで返す設定。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ = conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_schema_path() -> str:
    """スキーマファイルのパスを返す。"""
    return os.path.join(os.path.dirname(__file__), "sales-db.sql")


# ---------------------------------------------------------------------------
# 出力ヘルパー
# ---------------------------------------------------------------------------

def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    """sqlite3.Row のリストを dict のリストに変換する。"""
    return [dict(row) for row in rows]


def print_json(data: object) -> None:
    """JSON を stdout に出力する。"""
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()


def error_exit(message: str, code: int = 1) -> NoReturn:
    """エラーメッセージを stderr に出力して終了する。"""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# 文字列ユーティリティ
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """企業名を正規化する。全角→半角変換、小文字化、前後空白除去。"""
    return unicodedata.normalize("NFKC", name).lower().strip()


def extract_domain(url: str) -> str:
    """URLからドメインを抽出する。プロトコル・www・パスを除去し、小文字化する。"""
    domain = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    domain = re.sub(r"^www\.", "", domain, flags=re.IGNORECASE)
    domain = domain.split("/")[0]
    return domain.lower()
