#!/bin/bash
# Initialize the sales agent SQLite database
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="${1:-$PLUGIN_ROOT/data.db}"
SCHEMA_PATH="$SCRIPT_DIR/sales-db.sql"

if [ ! -f "$SCHEMA_PATH" ]; then
    echo "ERROR: Schema file not found: $SCHEMA_PATH" >&2
    exit 1
fi

sqlite3 "$DB_PATH" < "$SCHEMA_PATH"
echo "Database initialized: $DB_PATH"
