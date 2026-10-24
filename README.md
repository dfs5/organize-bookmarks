# 🔖 Curated Bookmarks & AI Knowledge Base (`organize-bookmarks`)

A zero-dependency Python knowledge management, taxonomy curation, and hybrid AI search platform for organizing engineering bookmarks into an interactive dark-mode showcase (`bookmarks_showcase.html`) backed by a local AI Copilot server (`ai_agent_server.py`).

> **📽️ Project Presentation Deck**: Looking for a visual executive & architectural overview? Read the 11-slide presentation [**Taming the Bookmark Black Hole: Building a Local AI-Powered Bookmarks Intelligence Platform (`docs/taming-the-bookmark-black-hole-presentation.pdf`)**](docs/taming-the-bookmark-black-hole-presentation.pdf) covering the 1,000-bookmark problem, the 3-tier canonical data layer, live browser CDP ingestion (*"Look, Don't Scrape"*), the 3-stage hybrid BM25 + LLM retrieval funnel, and real-world system profiling insights.

---

## ✨ Key Capabilities

- **🏛️ 9-Pillar Strategic Taxonomy**: Automatically classifies and organizes bookmarks into a 2-level `[Pillar, Subcategory]` hierarchy with structured multi-dimensional tags (`products`, `topics`, `source_types`).
- **🎨 Interactive Dark Glassmorphism Showcase (`generate_dark_showcase.py`)**: Generates a single-file, responsive web application (`bookmarks_showcase.html`) featuring instant client-side filtering, pillar navigation, product scope chips, custom user notes, Add/Manage/Delete bookmark modals, and an integrated **Ask AI Copilot** drawer.
- **🤖 Zero-Dependency AI Agent Server (`ai_agent_server/ai_agent_server.py`)**: Pure Python standard-library `ThreadingHTTPServer` providing:
  - **Stage 1 — Intent Extraction**: Parses natural-language queries into structured product/topic/source filters via Google Vertex AI (`Gemini`), Gemini Developer API, local GPU `Ollama`, or a deterministic BM25/taxonomy heuristic fallback.
  - **Stage 2 — Hybrid BM25 + Taxonomy + Visit-Frequency Scoring**: Scores catalog entries across titles, descriptions, 150–250 word technical summaries, custom notes, and logarithmic browser visit counts.
  - **Stage 3 — Deep Content Verification & Grounded Synthesis**: Verifies candidate relevance against cached/extracted page content and generates a grounded technical answer citing `[1]`, `[2]`, etc.
- **🌐 Live Browser CDP Bookmark Ingestion**: Inspects newly added bookmarks via an active Chrome/Edge DevTools Protocol (CDP) session or `/browser` subagent payload—handling JavaScript SPAs, SSO sessions, and `#fragment` deep links—and updates the catalog + HTML outputs in a single step.
- **📊 Safe Browser History Visit Sync (`sync_edge_history_bookmarks.py`)**: Reads local Microsoft Edge and Google Chrome SQLite history databases (via temp copies to avoid file locks) to update `visit_count` rankings on existing curated bookmarks without injecting unverified history URLs.

---

## 📸 Visual Walkthrough & UI Screenshots

### 1. Interactive Dark Showcase Dashboard & Multi-Dimensional Filtering
![F5 Bookmarks & Knowledge Catalog Dashboard](docs/screenshot-showcase-dashboard.png)

The main dashboard (`bookmarks_showcase.html`) renders the entire curated catalog into a fast, zero-latency dark glassmorphism interface:
- **Live Catalog Telemetry Header**: Displays real-time counts for total verified bookmarks, VPN-gated internal resources (`Requires VPN`), the `9 Pillars` taxonomy, and `Active Visited` links synced from browser history.
- **Instant Search & Quick-Filter Pills**: Supports instant client-side filtering (`/` or `⌘K` to focus) combined with one-click filter chips for **Access Scope** (`Needs VPN`), **Core Product Ecosystems** (`BIG-IP & TMOS`, `NGINX`, `F5 XC`, `Workforce AI`), **High-Frequency Topics** (`Sizing & Capacity`, `Security & WAF`, `AI & Guardrails`), and **Activity** (`Recently Added`, `Frequently Visited`).
- **Rich Bookmark Cards**: Each card displays the domain favicon, cleaned title, concise 110–180 character description, custom user note badge (amber pill, e.g., `amadeus AI initiatives`), historical browser visit count badge (`18x`), VPN indicator, and color-coded **Product / Topic / Source Type** tags—while holding a 150–250 word technical summary under the hood for BM25 and AI search.
- **Floating Pillar Jump Bar**: Pinned at the bottom of the viewport for one-click navigation across all 9 canonical strategic pillars.

---

### 2. Add Bookmark Modal with Deep AI & Live Browser Inspection
![Add Bookmark with Deep AI Inspection Modal](docs/screenshot-add-bookmark-modal.png)

Clicking **`+ Add Bookmark`** opens the live ingestion workflow backed by `POST /api/bookmarks/add` on the local AI Agent Server:
- **Look, Don't Scrape Inspection (`Inspect & Ingest`)**: Paste any documentation, KB article, GitHub repo, or internal portal URL. The server inspects the rendered DOM (via live Chrome/Edge CDP or `/browser` inspection), extracts headings and body content, and automatically synthesizes a clean title, 110–180 char description, 150–250 word technical summary, 9-pillar hierarchy placement, and multi-dimensional tags.
- **Custom User Notes**: Attach optional personal context or customer/project reminders (`Custom Notes`) that are persisted in `bookmarks_catalog.json`, displayed as amber badges on the card, and weighted heavily in BM25 & AI Copilot retrieval.
- **Automated Backup & Multi-Target Sync**: Every addition or deletion automatically snapshots `bookmarks_catalog.json` into `archive/backups/`, updates the local browser bookmarks profile (`Bookmarks`), and regenerates both `bookmarks_showcase.html` and the Netscape bookmark export (`favorites_product_frequency_organized.html`).

---

### 3. Bookmarks AI Copilot Drawer & Grounded Synthesis
![Bookmarks AI Copilot Drawer](docs/screenshot-ai-copilot-drawer.png)

Clicking **`Ask AI Copilot ⌘K`** opens the slide-out conversational search and synthesis drawer powered by `ai_agent_server.py`:
- **3-Stage Hybrid Retrieval & Grounded Answers**: When asking a natural-language question (such as `"big-ip sw update guidance"`), the server extracts structured intent, scores the catalog via BM25 + taxonomy + visit frequency, verifies full-text cache relevance (`must_mention` lexical guardrails), and generates a structured Markdown guide with inline citations (`K84205182`, `K5903`) and recommended action sequences.
- **Product Scope & Access Constraints**: Scope AI retrieval to specific portfolios using the top selector bar (`ADSP (All)`, `AISP (All AI)`, `BIG-IP`, `NGINX`, `F5 XC`) and toggle **`VPN Only`** or **`Frequently Visited (5+)`** to prioritize battle-tested engineering links.
- **Interactive Citation Cards**: Below the synthesized response, the Copilot renders the exact verified bookmark cards used to ground the answer, complete with **`Locate on page`** buttons that scroll and highlight the corresponding card directly in the main showcase grid.

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph DataLayer["Canonical Data Layer (Gitignored Locally, Sample Provided)"]
        Cat["bookmarks_catalog.json\n(or bookmarks_catalog.example.json)"]
        Meta["ai_agent_server/bookmarks_verified_metadata.json"]
        Cache["ai_agent_server/bookmarks_content_cache.json"]
    end

    subgraph BuildPipeline["Enrichment & Static Generation Pipeline"]
        Enrich["batch_enrich_all.py\n(Titles, Descriptions, 150-250w Summaries, Tags)"]
        Reorg["update_and_reorganize_bookmarks.py\n(9-Pillar Hierarchy & Netscape HTML Export)"]
        Gen["generate_dark_showcase.py\n(Builds bookmarks_showcase.html)"]
        Hist["sync_edge_history_bookmarks.py\n(Edge/Chrome SQLite Visit Sync)"]
    end

    subgraph Runtime["Interactive UI & Local AI Agent Server (Port 8765)"]
        UI["bookmarks_showcase.html\n(Filter Grid, Modals & Ask AI Drawer)"]
        Srv["ai_agent_server/ai_agent_server.py\n(BM25 + ContentInspector + LLMBridge)"]
        LLM["LLM Cascade:\n1. Google Vertex AI (ADC)\n2. Gemini API Key\n3. Local Ollama (gemma3:4b)\n4. Heuristic BM25 Fallback"]
    end

    Cat --> Enrich --> Reorg --> Gen --> UI
    Hist --> Cat
    Cat --> Srv
    Meta --> Srv
    Cache --> Srv
    UI <-->|"/api/search, /api/chat,\n/api/bookmarks/*"| Srv
    Srv <--> LLM
```

---

## 🚀 Quickstart

### Prerequisites
- **Python 3.9+** (uses Python standard library only; **zero external `pip` packages required**)
- *(Optional)* **Google Cloud SDK (`gcloud`)** for Vertex AI authentication, a `GEMINI_API_KEY`, or local **Ollama** (`ollama serve`) for generative AI synthesis. Without an LLM configured, the server automatically operates in deterministic BM25 + heuristic synthesis mode.

### 1. Clone the Repository
```bash
git clone https://github.com/dfs5/organize-bookmarks.git
cd organize-bookmarks
```

### 2. Initialize Local Configuration & Catalog (Optional)
Out of the box, all scripts automatically fall back to [`bookmarks_catalog.example.json`](bookmarks_catalog.example.json) (18 curated public technical bookmarks across all 9 pillars) and [`ai_agent_server/ai_agent_server.conf.example`](ai_agent_server/ai_agent_server.conf.example).

To create your own local catalog and server configuration (which are `.gitignore`d so your private bookmarks and project IDs stay local):
```bash
cp bookmarks_catalog.example.json bookmarks_catalog.json
cp ai_agent_server/ai_agent_server.conf.example ai_agent_server/ai_agent_server.conf
```
If using Google Vertex AI, set your GCP Project ID in `ai_agent_server/ai_agent_server.conf` (under `llm.gemini.project_id`) or export `GOOGLE_CLOUD_PROJECT`:
```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
```

### 3. Build the Interactive Showcase HTML
```bash
python3 update_and_reorganize_bookmarks.py
python3 generate_dark_showcase.py
```
This generates:
- `bookmarks_showcase.html` — The interactive dark-theme web application.
- `favorites_product_frequency_organized.html` — Standard Netscape bookmark export importable into Chrome/Edge/Firefox.

### 4. Start the Local AI Agent Server
```bash
./run_ai_server.sh
./run_ai_server.sh --status
```
Open `bookmarks_showcase.html` in your browser to browse, filter, add/manage bookmarks, and query the **Ask AI Copilot** drawer (connected to `http://localhost:8765`).

---

## 🗂️ The 9 Canonical Strategic Pillars

| Pillar | Scope & Examples |
| :--- | :--- |
| **`01. BIG-IP & TMOS`** | LTM, APM, AWAF/ASM, DNS/GTM, iRules, F5OS-A (rSeries), F5OS-C (VELOS), iHealth, Hardware/VE Datasheets |
| **`02. NGINX Ecosystem`** | NGINX Open Source, NGINX Plus, NGINX One, NGINX App Protect (NAP), NGINX Ingress Controller, Gateway Fabric |
| **`03. F5 Distributed Cloud (XC) & Multi-Cloud`** | F5 XC Console, WAAP, Multi-Cloud Networking (MCN), DNS Load Balancer, CDN, Bot Defense, API Security |
| **`04. AI Security, Workforce AI & Agentic AI`** | F5 AI Gateway, AI Guardrails (CalypsoAI), Workforce AI Security (SurePath), Reference Architectures, Agentic AI |
| **`05. Knowledge Base (KBs) & Official TechDocs`** | MyF5 Knowledge Base (`K`-articles), CloudDocs, TechDocs, Product Manuals, Validated Architectures |
| **`06. Product Lifecycle, Releases & Roadmaps`** | Software Support Policies (`K5903`), Hardware/Software Compatibility Matrices (`K9476`), Release Notes, End-of-Life |
| **`07. Lab Environments, Demos & Developer Ecosystem`** | UDF Labs, Interactive Product Demos, GitHub Repositories, Terraform/Ansible/AS3 Automation, DevCentral Community |
| **`08. Internal Sales Engineering & Enablement`** | Solution Architectures, Industry Verticals, Sizing Tools, Competitive Enablement, Field Portals |
| **`09. External Engineering, Protocols & Tools`** | Kubernetes Docs, IETF RFCs, OWASP, TLS/SSL Utilities, Cloud Provider Documentation, Network/Security Tools |

---

## 🛠️ Common Operations & CLI Commands

### AI Agent Server Lifecycle
```bash
./run_ai_server.sh                   # Start background daemon on port 8765
./run_ai_server.sh --status          # Check server health, active LLM backend, and logging state
./run_ai_server.sh --restart         # Restart after config or catalog changes
./run_ai_server.sh --stop            # Stop background daemon
./run_ai_server.sh --enable-logging  # Enable full Frontend <-> Server <-> LLM traffic logging
./run_ai_server.sh --tail-log        # Follow live traffic in ai_agent_server/ai_communication.log
./run_ai_server.sh --disable-logging # Disable traffic logging
```

### Command-Line Bookmark Lookup
```bash
python3 .agents/skills/bookmark-lookup/lookup.py "rseries sizing"
python3 .agents/skills/bookmark-lookup/lookup.py --product f5-xc --topic security-waf
```

### Canonical CLI Bookmark Ingestion
```bash
python3 ai_agent_server/ai_agent_server.py \
  --ingest-url "https://docs.nginx.com/" \
  --browser-json '{"title":"F5 NGINX Product Documentation","h1":"F5 NGINX Documentation","meta_desc":"Official documentation for NGINX products.","company_context":"F5 NGINX application delivery and API security","body_text":"..."}' \
  --notes "Core NGINX documentation portal"
```

### Browser History Visit Sync
```bash
python3 sync_edge_history_bookmarks.py --dry-run --show-candidates
python3 sync_edge_history_bookmarks.py
```

---

## 📚 Documentation Index

- [**📽️ Project Presentation Deck (`docs/taming-the-bookmark-black-hole-presentation.pdf`)**](docs/taming-the-bookmark-black-hole-presentation.pdf) — 11-slide visual presentation: *"Taming the Bookmark Black Hole: Building a Local AI-Powered Bookmarks Intelligence Platform"* (problem statement, system blueprint, canonical data layer, live browser ingestion, 3-stage hybrid retrieval funnel, and log autopsy).
- [**Project Maintenance Guide (`MAINTENANCE.md`)**](MAINTENANCE.md) — Quick reference for server commands, showcase rebuilds, automated GitHub publishing (`./publish_update.sh`), and persistent session memory.
- [**AI Agent Server Maintenance Guide (`ai_agent_server/MAINTENANCE.md`)**](ai_agent_server/MAINTENANCE.md) — Deep dive into `ai_agent_server.conf`, health checks, LLM provider cascading, traffic logging, and troubleshooting.
- [**Agent Rules & Code Map (`AGENTS.md`)**](AGENTS.md) — Context guardrails, canonical data schema, `/browser` inspection workflow, and line-level code index.
- **Architecture & Workflow Deep Dives (`docs/`)**:
  - [**Complete Project Architecture (`docs/demo-bookmark-project-human-readable.md`)**](docs/demo-bookmark-project-human-readable.md) *(and [detailed reference](docs/demo-bookmark-project.md))*
  - [**Adding a Bookmark End-to-End Trace (`docs/demo-adding-bookmark-human-readable.md`)**](docs/demo-adding-bookmark-human-readable.md) *(and [detailed trace](docs/demo-adding-bookmark.md))*
  - [**Searching Bookmarks & AI Copilot Trace (`docs/demo-searching-bookmarks-human-readable.md`)**](docs/demo-searching-bookmarks-human-readable.md) *(and [detailed trace](docs/demo-searching-bookmarks.md))*
  - **UI Screenshots (`docs/`)**:
    - [`docs/screenshot-showcase-dashboard.png`](docs/screenshot-showcase-dashboard.png) — Main Dark Showcase Dashboard & Recently Added Grid
    - [`docs/screenshot-add-bookmark-modal.png`](docs/screenshot-add-bookmark-modal.png) — Add Bookmark with Deep AI Inspection Modal
    - [`docs/screenshot-ai-copilot-drawer.png`](docs/screenshot-ai-copilot-drawer.png) — Bookmarks AI Copilot Conversational Search Drawer
