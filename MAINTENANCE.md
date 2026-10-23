# 📚 Project Maintenance & Operations Guide

Quick links to project maintenance guides:
- 🤖 [**AI Agent Server Maintenance Guide**](ai_agent_server/MAINTENANCE.md): Start/stop commands, configuration changes, Vertex AI / Gemini setup, logs, and troubleshooting.

---

## ⚡ Quick Reference Commands

### AI Agent Server
```bash
# Start background server
./run_ai_server.sh

# Check status & active model & logging state
./run_ai_server.sh --status

# Stop server
./run_ai_server.sh --stop

# Restart server (after config changes in ai_agent_server/ai_agent_server.conf)
./run_ai_server.sh --restart

# --- Communication Traffic Logging (Frontend ↔ Server & Server ↔ LLM) ---
# Enable traffic logging on-demand
./run_ai_server.sh --enable-logging

# Follow live traffic in real-time
./run_ai_server.sh --tail-log

# Check logging status & file location
./run_ai_server.sh --log-status

# Disable traffic logging when done
./run_ai_server.sh --disable-logging
```

### Showcase & Bookmarks Catalog
```bash
# Rebuild the interactive dark showcase web app
python3 generate_dark_showcase.py

# Sync Edge/Chrome browser visit counts on existing curated bookmarks (and optionally list top unbookmarked candidates)
python3 sync_edge_history_bookmarks.py
python3 sync_edge_history_bookmarks.py --dry-run --show-candidates
```

### Persistent Session & Project Memory
```bash
# Inspect current in-session state & compacted project memory size
python3 .agents/memory/memory_cli.py status

# Set active session goal (survives auto-compaction via PreInvocation hook)
python3 .agents/memory/memory_cli.py set-goal "Your task description"

# Record a completed step or working note
python3 .agents/memory/memory_cli.py complete-step "Finished step"
python3 .agents/memory/memory_cli.py add-note "Key finding or line range"

# Semantic + FTS5 BM25 search across all indexed memory & maintenance docs
python3 .agents/memory/memory_cli.py search "DevCentral redirect rules" --top-k 4

# Force re-index all memory/maintenance markdown chunks & embeddings
python3 .agents/memory/memory_cli.py index --force

# Roll session milestones into .agents/memory/project_memory.md and reset scratchpad
python3 .agents/memory/memory_cli.py compact --summary "Summary of completed work"
```

