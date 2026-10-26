# 🛠️ AI Agent Server Maintenance & Operations Guide

This document contains maintenance commands, operational workflows, and troubleshooting procedures for the **Bookmarks AI Agent Server**.

---

## 📋 Table of Contents
1. [Service Lifecycle Management](#1-service-lifecycle-management)
2. [Configuration Maintenance](#2-configuration-maintenance)
3. [Health Checks & Verification](#3-health-checks--verification)
4. [Logs & Cache Management](#4-logs--cache-management)
5. [Model & Provider Switching](#5-model--provider-switching)
6. [Showcase & Catalog Sync](#6-showcase--catalog-sync)
7. [Troubleshooting & FAQ](#7-troubleshooting--faq)

---

## 1. Service Lifecycle Management

The service control script [`run_ai_server.sh`](../run_ai_server.sh) (or [`ai_agent_server/run_ai_server.sh`](run_ai_server.sh)) manages the background daemon.

### Start Server (Background Daemon)
Starts the server in the background on default port `8765`:
```bash
./run_ai_server.sh
```

### Stop Server
Terminates the running daemon safely using the stored PID:
```bash
./run_ai_server.sh --stop
```

### Restart Server (After Config/Code Changes)
Whenever you update `ai_agent_server.conf` or code:
```bash
./run_ai_server.sh --restart
```

### Check Service & Logging Status
Displays whether the process is alive, PID, port, active model, and traffic logging state:
```bash
./run_ai_server.sh --status
```

### Enable / Disable Communication Traffic Logging
Enable or disable logging of full communication content (frontend ↔ server & server ↔ LLM) on demand:
```bash
# Turn logging ON
./run_ai_server.sh --enable-logging

# Follow live communication traffic in real-time
./run_ai_server.sh --tail-log

# Check current logging status
./run_ai_server.sh --log-status

# Turn logging OFF
./run_ai_server.sh --disable-logging
```
*(See [Section 4: Communication Traffic Logging](#communication-traffic-logging-frontend--server--server--llm) for payload structure, headers, and security redaction details.)*

### Foreground / Live Debug Mode
Runs in the foreground with live console logs (press `Ctrl+C` to stop):
```bash
./run_ai_server.sh --fg
```

---

## 2. Configuration Maintenance

All server settings are isolated in [`ai_agent_server/ai_agent_server.conf`](ai_agent_server.conf).

### File Structure & Key Settings:
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8765
  },
  "llm": {
    "gemini": {
      "model": "Gemini 3.8 Flash (Medium)",
      "project_id": "<YOUR_GCP_PROJECT_ID>",
      "location": "global",
      "timeout_seconds": 10
    },
    "ollama": {
      "url": "http://127.0.0.1:11434",
      "preferred_model": "gemma3:4b",
      "timeout_seconds": 7
    }
  }
}
```

> [!TIP]
> After modifying `ai_agent_server.conf`, always execute `./run_ai_server.sh --stop && ./run_ai_server.sh` to apply changes.

---

## 3. Health Checks & Verification

### Status Endpoint
Inspect the active model, project ID, and catalog count:
```bash
curl -s http://localhost:8765/api/status | jq .
```
Expected response:
```json
{
  "status": "online",
  "server": "Bookmarks AI Project Agent",
  "port": 8765,
  "bookmarks_count": 990,
  "llm_backend": {
    "provider": "vertex",
    "details": "Google Vertex AI (Gemini 3.8 Flash (Medium)) [Project: <YOUR_GCP_PROJECT_ID>]"
  },
  "intent_engine": {
    "active": true,
    "model": "vertex/Gemini 3.8 Flash (Medium)",
    "type": "Google Vertex AI [Project: <YOUR_GCP_PROJECT_ID>]"
  }
}
```

### Test Intent Extraction & Search
```bash
curl -s -X POST http://localhost:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "i want to migarte iRules to XC platform."}' | jq .intent
```

### Test Generative Chat Synthesis
```bash
curl -s -X POST http://localhost:8765/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "how to size rseries for high throughput"}' | jq -r .reply
```

---

## 4. Logs & Cache Management

### Runtime Server Logs
The server logs operational requests, response codes, and errors to `ai_agent_server/ai_server.log`:
```bash
# Follow live server output
tail -f ai_agent_server/ai_server.log

# Clear server log
> ai_agent_server/ai_server.log
```

### Communication Traffic Logging (Frontend ↔ Server & Server ↔ LLM)
To inspect the complete content of communications between the showcase frontend and `ai_agent_server`, and between `ai_agent_server` and LLMs (Google Vertex AI, Gemini API, Ollama), communication traffic logging can be enabled **on demand via command**.

By default, writing to `ai_communication.log` is **disabled** to avoid disk churn and log growth.

```bash
# Enable traffic logging (works while server is running or when starting)
./run_ai_server.sh --enable-logging

# Follow live communication traffic in real-time
./run_ai_server.sh --tail-log

# Check logging status
./run_ai_server.sh --log-status

# Disable traffic logging when done
./run_ai_server.sh --disable-logging
```

#### What Gets Logged
- **Frontend ➔ AI Server (`🌐 [FRONTEND ➔ AI_SERVER]`)**: HTTP method, request path, headers, query parameters, and JSON payloads (search terms, chat prompts, bookmark additions).
- **AI Server ➔ LLM (`🤖 [AI_SERVER ➔ LLM]`)**: Target LLM provider (`vertex`, `gemini`, `ollama`), model identifier, endpoint URL, exact prompt payload, and generation parameters (temperature, max tokens).
- **LLM ➔ AI Server (`🧠 [LLM ➔ AI_SERVER]`)**: HTTP status code, round-trip latency in seconds, and raw output text / structured JSON candidates.
- **AI Server ➔ Frontend (`💻 [AI_SERVER ➔ FRONTEND]`)**: HTTP status code, processing duration, and response payload (intent analysis, verified bookmark results, AI synthesis).

#### Security & Redaction
Bearer tokens and API keys in URLs and HTTP headers are automatically redacted (e.g. `Bearer ya29.a...[REDACTED]`, `?key=[REDACTED]`) before writing to the log file. Periodic health check polling (`/api/status`) is filtered out by default to keep the log focused on actual search and LLM interactions.

### Page Body Content Cache
The server crawls and indexes live pages to verify that candidates match user intent before displaying them. Cached bodies are stored in `ai_agent_server/bookmarks_content_cache.json`.

```bash
# Check size of cached content
ls -lh ai_agent_server/bookmarks_content_cache.json

# Reset/rebuild content cache (forces fresh page inspection on subsequent searches)
rm -f ai_agent_server/bookmarks_content_cache.json
```

---

## 5. Model & Provider Switching

The agent cascades through available engines in this order:

1. **Google Vertex AI via Project ID (Primary)**:
   - Configured in `ai_agent_server.conf` (`project_id`, `location`, `model`).
   - Uses local Google Cloud ADC credentials.
2. **Google Gemini Developer API**:
   - Used if `GEMINI_API_KEY` is exported in the environment.
3. **Local GPU LLM (Ollama)**:
   - Active when Ollama is running (`ollama serve`). Model: `gemma3:4b`.
4. **Heuristic Verification Fallback**:
   - Zero-dependency BM25 keyword taxonomy + page body crawler when all LLMs are unreachable.

---

## 6. Showcase & Catalog Sync

### Rebuild Showcase UI
If [`bookmarks_catalog.json`](../bookmarks_catalog.json) is updated with new bookmarks:
```bash
python3 generate_dark_showcase.py
```
This regenerates [`bookmarks_showcase.html`](../bookmarks_showcase.html) with updated cards and search indices.

### Sync Browser History & Visits
To safely synchronize bookmark visit counts from Microsoft Edge and Google Chrome onto existing curated bookmarks (or inspect top unbookmarked candidates without modifying the catalog):
```bash
python3 sync_edge_history_bookmarks.py
python3 sync_edge_history_bookmarks.py --dry-run --show-candidates
```

### Single-URL & Bulk Bookmark Ingestion (CLI & REST API)
You can add individual bookmarks or bulk-import bookmark files (`.html` Netscape exports, Chrome/Edge `Bookmarks` JSON, `.json` catalog arrays, or `.txt`/`.md` URL lists) via the `+ Add Bookmark` modal in `bookmarks_showcase.html`, the CLI, or the REST API:

```bash
# CLI: Dry-run preview of a bulk bookmark file (lists new vs. already-curated URLs)
python3 ai_agent_server/ai_agent_server.py --import-file ~/Downloads/bookmarks.html --dry-run

# CLI: Import up to 25 new bookmarks with full inspection, taxonomy classification, and HTML rebuild
python3 ai_agent_server/ai_agent_server.py --import-file ~/Downloads/bookmarks.html --max-import 25 --notes "Q4 import"

# REST API: Dry-run bulk import preview via POST /api/bookmarks/import
curl -s -X POST http://localhost:8765/api/bookmarks/import \
  -H "Content-Type: application/json" \
  -d '{"content": "<DT><A HREF=\"https://docs.nginx.com/\">NGINX Docs</A>", "filename": "export.html", "dry_run": true}' | jq .
```

---

## 7. Troubleshooting & FAQ

### Port Conflict (`Address already in use`)
If port `8765` is busy:
```bash
# Find process on port 8765
lsof -i :8765

# Terminate process
kill -9 $(lsof -t -i :8765)

# Restart server
./run_ai_server.sh
```

### Google Cloud Token Expired or Not Found
Refresh your Application Default Credentials:
```bash
gcloud auth application-default login
```
The server will automatically detect and use the refreshed token without restarting.
