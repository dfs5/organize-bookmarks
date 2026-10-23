#!/bin/bash
# Standalone Edge history bookmark sync script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
/usr/bin/python3 sync_edge_history_bookmarks.py >> sync.log 2>&1
