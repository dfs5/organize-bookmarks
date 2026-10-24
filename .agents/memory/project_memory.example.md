# 🏛️ Compacted Project Memory (`organize-bookmarks`)

> **Purpose**: High-density, cross-session institutional memory for the `organize-bookmarks` project.
> **Budget**: Keep under `8 KB` (`~2,000 tokens`). Use `python3 .agents/memory/memory_cli.py compact` to roll session milestones into this file.

---

## 1. System Architecture & Pipeline Summary
- **Single Source of Truth**: [`bookmarks_catalog.json`](../../bookmarks_catalog.json) (bootstrapped from [`bookmarks_catalog.example.json`](../../bookmarks_catalog.example.json) on fresh clones) holds the active curated bookmark catalog.
- **Enrichment & Verification Stores** (created and updated automatically on demand):
  - `ai_agent_server/bookmarks_verified_metadata.json`: Ground-truth extracted page titles, headings, and metadata keyed by normalized URL.
  - `ai_agent_server/bookmarks_content_cache.json`: Live crawled page text cache used by `ContentInspector` for search candidate verification.
- **Rebuild Pipeline**:
  Whenever `bookmarks_catalog.json` or taxonomy rules change, run:
  1. `python3 batch_enrich_all.py` (if summaries, titles, or multi-dimensional tags need re-enrichment)
  2. `python3 update_and_reorganize_bookmarks.py` (re-applies hierarchy rules & exports `favorites_product_frequency_organized.html`)
  3. `python3 generate_dark_showcase.py` (rebuilds `bookmarks_showcase.html`)
  4. `./run_ai_server.sh --restart` (reloads in-memory `CatalogEngine` index on port `8765`)

---

## 2. Permanent Domain Rules & Edge Cases
- **DevCentral (`/t5/`) Legacy Redirect Traps**:
  Legacy `community.f5.com/t5/...` URLs may return HTTP 404 or redirect to unrelated forum replies due to Khoros ID collisions. Always verify semantic title alignment between the bookmark's original title and the live destination `<title>` / `<h1>` before accepting a redirect.
- **MyF5 (`my.f5.com/manage/s/article/K...`) SPA Handling**:
  Direct HTTP fetches to `my.f5.com` return an Aura/LWR SPA shell unless inspected via `/browser` or matched against `bookmarks_verified_metadata.json`.
- **VPN / Internal SSO Classification (`requires_vpn: true`)**:
  Internal hosts (e.g., `*.f5net.com`, internal GitLab, SharePoint, ServiceNow, Salesforce, Tableau, Aha!, Confluence/Jira) require VPN/SSO. HTTP 403/401 responses on public cloud/Akamai/Cloudflare/Imperva WAFs are bot-protection challenges, **not** dead links or VPN-only links.
- **Anchored URL (`#fragment`) Preservation**:
  Deep links with `#fragment` anchors (such as `#tenant-data` or `#overview`) represent distinct technical sections and must preserve their `#fragment` during inspection, metadata lookup, and deduplication.

---

## 3. Compacted Milestone History
- **v1.0.0 Baseline**: Initialized deployment with 9-Pillar taxonomy (`update_and_reorganize_bookmarks.py`), dark showcase generator (`generate_dark_showcase.py`), local AI Agent Server (`ai_agent_server/ai_agent_server.py`) supporting Vertex AI / Gemini API / Ollama / BM25 fallback, `/browser` CDP ingestion (`--ingest-url`), Edge/Chrome visit count sync (`sync_edge_history_bookmarks.py`), and two-tier persistent agent memory (`.agents/memory/`).
