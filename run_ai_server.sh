#!/bin/bash
# Forwarding script to ai_agent_server/run_ai_server.sh
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT_DIR/ai_agent_server/run_ai_server.sh" "$@"
