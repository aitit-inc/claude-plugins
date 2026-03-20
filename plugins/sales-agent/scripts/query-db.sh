#!/bin/bash
# Execute SQL query against the sales database
# Usage: query-db.sh <sql> [db_path]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="${2:-$PLUGIN_ROOT/data.db}"

if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found: $DB_PATH" >&2
    echo "Run /setup first to initialize the database." >&2
    exit 1
fi

sqlite3 -header -column "$DB_PATH" "$1"
