#!/bin/bash
# ==============================================================================
# run_ai_server.sh - Manage the local Bookmarks AI Agent server
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/.ai_server.pid"
LOG_FILE="$DIR/ai_server.log"
CONF_FILE="$DIR/ai_agent_server.conf"
if [ ! -f "$CONF_FILE" ] && [ -f "$DIR/ai_agent_server.conf.example" ]; then
  CONF_FILE="$DIR/ai_agent_server.conf.example"
fi
COMM_LOG_FILE="$DIR/ai_communication.log"

cd "$DIR" || exit 1

# Extract port from conf if possible, default to 8765
PORT=$(grep -E '"port"' "$CONF_FILE" 2>/dev/null | head -n1 | tr -dc '0-9')
PORT=${PORT:-8765}

# Helper to check if server is listening on port
is_server_running() {
  local p_pid
  p_pid=$(lsof -ti :$PORT 2>/dev/null)
  [ -n "$p_pid" ]
}

case "$1" in
  --help|-h)
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Server Management:"
    echo "  (no args)           Start AI Agent server in background (or report if running)"
    echo "  --fg                Start AI Agent server in foreground"
    echo "  --stop              Stop running AI Agent server"
    echo "  --restart           Restart running AI Agent server"
    echo "  --status            Show status of AI Agent server & logging"
    echo ""
    echo "Traffic Logging (Frontend <-> Server & Server <-> LLM):"
    echo "  --enable-logging    Enable communication content logging"
    echo "  --disable-logging   Disable communication content logging"
    echo "  --log-status        Show current traffic logging status & config"
    echo "  --tail-log          Follow the communication traffic log in real-time"
    echo ""
    exit 0
    ;;

  --stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping AI Agent server (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Server stopped."
        exit 0
      fi
    fi
    PORT_PID=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PORT_PID" ]; then
      echo "Killing process on port $PORT (PID: $PORT_PID)..."
      kill "$PORT_PID"
      rm -f "$PID_FILE"
      echo "Server stopped."
    else
      echo "AI Agent server is not running."
    fi
    ;;

  --status)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        echo "🟢 AI Agent server is running (PID: $PID) on http://localhost:$PORT"
      fi
    elif is_server_running; then
      PORT_PID=$(lsof -ti :$PORT 2>/dev/null)
      echo "🟢 AI Agent server is active on port $PORT (PID: $PORT_PID)"
    else
      echo "⚪ AI Agent server is stopped."
      exit 0
    fi
    if is_server_running; then
      LOG_JSON=$(curl -s "http://localhost:$PORT/api/logging" 2>/dev/null)
      if [ -n "$LOG_JSON" ]; then
        LOG_ENABLED=$(echo "$LOG_JSON" | grep -o '"enabled":\s*true' || true)
        if [ -n "$LOG_ENABLED" ]; then
          echo "📜 Traffic Logging: 🟢 ENABLED ($COMM_LOG_FILE)"
        else
          echo "📜 Traffic Logging: ⚪ DISABLED"
        fi
      fi
    fi
    ;;

  --enable-logging|--log-on)
    if is_server_running; then
      echo "Sending runtime enable command to AI Agent server on port $PORT..."
      RESP=$(curl -s -X POST "http://localhost:$PORT/api/logging" \
        -H "Content-Type: application/json" \
        -d '{"enabled": true}')
      echo "✅ $RESP"
      echo "📜 Traffic log file: $COMM_LOG_FILE"
      echo "💡 Run '$0 --tail-log' to watch live traffic."
    else
      echo "Server is not running. Starting server with traffic logging enabled..."
      nohup python3 "$DIR/ai_agent_server.py" --enable-logging > "$LOG_FILE" 2>&1 &
      NEW_PID=$!
      echo $NEW_PID > "$PID_FILE"
      sleep 1
      if kill -0 "$NEW_PID" 2>/dev/null; then
        echo "✅ Server started with logging ENABLED! PID: $NEW_PID"
        echo "📜 Traffic log: $COMM_LOG_FILE"
      else
        echo "❌ Server failed to start. Check $LOG_FILE"
        exit 1
      fi
    fi
    ;;

  --disable-logging|--log-off)
    if is_server_running; then
      echo "Sending runtime disable command to AI Agent server on port $PORT..."
      RESP=$(curl -s -X POST "http://localhost:$PORT/api/logging" \
        -H "Content-Type: application/json" \
        -d '{"enabled": false}')
      echo "🛑 $RESP"
    else
      echo "AI Agent server is not currently running."
    fi
    ;;

  --log-status)
    if is_server_running; then
      curl -s "http://localhost:$PORT/api/logging"
      echo ""
    else
      echo "Server is not running. Checking configuration in $CONF_FILE..."
      grep -A 5 '"logging"' "$CONF_FILE" || echo "No logging block in config."
    fi
    ;;

  --tail-log|--view-log)
    if [ ! -f "$COMM_LOG_FILE" ]; then
      touch "$COMM_LOG_FILE"
    fi
    echo "Watching traffic log: $COMM_LOG_FILE (Press Ctrl+C to exit)..."
    exec tail -n 50 -f "$COMM_LOG_FILE"
    ;;

  --restart)
    echo "Restarting AI Agent server..."
    "$0" --stop
    sleep 1
    shift
    exec "$0" "$@"
    ;;

  --fg)
    echo "Starting AI Agent server in foreground..."
    shift
    exec python3 "$DIR/ai_agent_server.py" "$@"
    ;;

  *)
    PORT_PID=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PORT_PID" ]; then
      echo "🟢 AI Agent server is already running on http://localhost:$PORT (PID: $PORT_PID)"
      echo "💡 To toggle traffic logging: $0 --enable-logging | --disable-logging"
      exit 0
    fi

    echo "🚀 Starting AI Agent server in background on port $PORT..."
    nohup python3 "$DIR/ai_agent_server.py" "$@" > "$LOG_FILE" 2>&1 &
    NEW_PID=$!
    echo $NEW_PID > "$PID_FILE"
    sleep 1

    if kill -0 "$NEW_PID" 2>/dev/null; then
      echo "✅ Server started successfully! PID: $NEW_PID"
      echo "🌐 Open showcase: http://localhost:$PORT/bookmarks_showcase.html"
      echo "📜 Server log: $LOG_FILE"
      echo "⚙️  Config file: $CONF_FILE"
      echo "💡 Enable traffic logging anytime with: $0 --enable-logging"
    else
      echo "❌ Server failed to start. Check $LOG_FILE:"
      cat "$LOG_FILE"
      exit 1
    fi
    ;;
esac
