#!/bin/bash
# Check if a prospect already exists in the database
# Returns matching prospect(s) with match type, or nothing if no match
#
# Usage: check-duplicate.sh <db_path> [--email <email>] [--sns <key> <value>] [--corporate-number <number>] [--company-name <name>] [--website-url <url>]
# Multiple flags can be combined. Checks run in order of confidence (most certain first).
#
# Output format (one line per match):
#   EXACT_MATCH|<prospect_id>|<company_name>|<reason>
#   POSSIBLE_MATCH|<prospect_id>|<company_name>|<reason>
# Exit code 0 = match found, 1 = no match, 2 = error

set -euo pipefail

DB_PATH=""
EMAIL=""
SNS_KEY=""
SNS_VALUE=""
CORPORATE_NUMBER=""
COMPANY_NAME=""
WEBSITE_URL=""

# Parse arguments
if [ $# -lt 1 ]; then
    echo "Usage: check-duplicate.sh <db_path> [--email <email>] [--sns <key> <value>] [--corporate-number <number>] [--company-name <name>] [--website-url <url>]" >&2
    exit 2
fi

DB_PATH="$1"
shift

while [ $# -gt 0 ]; do
    case "$1" in
        --email) EMAIL="$2"; shift 2 ;;
        --sns) SNS_KEY="$2"; SNS_VALUE="$3"; shift 3 ;;
        --corporate-number) CORPORATE_NUMBER="$2"; shift 2 ;;
        --company-name) COMPANY_NAME="$2"; shift 2 ;;
        --website-url) WEBSITE_URL="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found: $DB_PATH" >&2
    exit 2
fi

FOUND=0

# --- Stage 1: email exact match ---
if [ -n "$EMAIL" ]; then
    RESULT=$(sqlite3 -separator '|' "$DB_PATH" "SELECT id, company_name FROM prospects WHERE email = '$(echo "$EMAIL" | sed "s/'/''/g")';")
    if [ -n "$RESULT" ]; then
        while IFS='|' read -r pid pname; do
            echo "EXACT_MATCH|${pid}|${pname}|email一致: ${EMAIL}"
            FOUND=1
        done <<< "$RESULT"
    fi
fi

# --- Stage 2: SNS account exact match ---
if [ -n "$SNS_KEY" ] && [ -n "$SNS_VALUE" ]; then
    ESCAPED_VALUE=$(echo "$SNS_VALUE" | sed "s/'/''/g")
    RESULT=$(sqlite3 -separator '|' "$DB_PATH" "SELECT id, company_name FROM prospects WHERE sns_accounts IS NOT NULL AND json_extract(sns_accounts, '$.${SNS_KEY}') = '${ESCAPED_VALUE}';")
    if [ -n "$RESULT" ]; then
        while IFS='|' read -r pid pname; do
            echo "EXACT_MATCH|${pid}|${pname}|SNS一致: ${SNS_KEY}=${SNS_VALUE}"
            FOUND=1
        done <<< "$RESULT"
    fi
fi

# --- Stage 3: corporate number exact match ---
if [ -n "$CORPORATE_NUMBER" ]; then
    RESULT=$(sqlite3 -separator '|' "$DB_PATH" "SELECT id, company_name FROM prospects WHERE corporate_number = '${CORPORATE_NUMBER}';")
    if [ -n "$RESULT" ]; then
        while IFS='|' read -r pid pname; do
            echo "EXACT_MATCH|${pid}|${pname}|法人番号一致: ${CORPORATE_NUMBER}"
            FOUND=1
        done <<< "$RESULT"
    fi
fi

# --- Stage 4: company_name exact match ---
if [ -n "$COMPANY_NAME" ]; then
    ESCAPED_NAME=$(echo "$COMPANY_NAME" | sed "s/'/''/g")
    RESULT=$(sqlite3 -separator '|' "$DB_PATH" "SELECT id, company_name FROM prospects WHERE company_name = '${ESCAPED_NAME}';")
    if [ -n "$RESULT" ]; then
        while IFS='|' read -r pid pname; do
            echo "EXACT_MATCH|${pid}|${pname}|企業名完全一致"
            FOUND=1
        done <<< "$RESULT"
    fi
fi

# --- Stage 5: website domain match ---
if [ -n "$WEBSITE_URL" ]; then
    # Extract domain: strip protocol, www., trailing path
    DOMAIN=$(echo "$WEBSITE_URL" | sed -E 's|^https?://||; s|^www\.||; s|/.*||')
    if [ -n "$DOMAIN" ]; then
        ESCAPED_DOMAIN=$(echo "$DOMAIN" | sed "s/'/''/g")
        # Match any URL containing this domain
        RESULT=$(sqlite3 -separator '|' "$DB_PATH" "SELECT id, company_name, website_url FROM prospects WHERE website_url IS NOT NULL AND REPLACE(REPLACE(REPLACE(website_url, 'https://', ''), 'http://', ''), 'www.', '') LIKE '${ESCAPED_DOMAIN}%';")
        if [ -n "$RESULT" ]; then
            while IFS='|' read -r pid pname purl; do
                echo "POSSIBLE_MATCH|${pid}|${pname}|ドメイン一致: ${DOMAIN}"
                FOUND=1
            done <<< "$RESULT"
        fi
    fi
fi

if [ "$FOUND" -eq 0 ]; then
    exit 1
fi

exit 0
