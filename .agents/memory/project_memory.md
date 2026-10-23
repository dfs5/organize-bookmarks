# 🏛️ Compacted Project Memory (`organize-bookmarks`)

> **Purpose**: High-density, cross-session institutional memory for the `organize-bookmarks` project.
> **Budget**: Keep under `8 KB` (`~2,000 tokens`). Use `python3 .agents/memory/memory_cli.py compact` to roll session milestones into this file.

---

## 1. System Architecture & Pipeline Summary
- **Single Source of Truth**: [`bookmarks_catalog.json`](../../bookmarks_catalog.json) currently holds **720 verified, active bookmarks** (cleaned down from 758 after archiving 38 dead/broken-redirect bookmarks).
- **Enrichment & Verification Stores**:
  - [`ai_agent_server/bookmarks_verified_metadata.json`](../../ai_agent_server/bookmarks_verified_metadata.json): Ground-truth extracted page titles, headings, and metadata keyed by normalized URL.
  - [`ai_agent_server/bookmarks_content_cache.json`](../../ai_agent_server/bookmarks_content_cache.json): Live crawled page text cache used by `ContentInspector` for search candidate verification.
- **Rebuild Pipeline**:
  Whenever `bookmarks_catalog.json` or taxonomy rules change, run:
  1. `python3 batch_enrich_all.py` (if summaries, titles, or multi-dimensional tags need re-enrichment)
  2. `python3 update_and_reorganize_bookmarks.py` (re-applies hierarchy rules & exports `favorites_product_frequency_organized.html`)
  3. `python3 generate_dark_showcase.py` (rebuilds `bookmarks_showcase.html`)
  4. `./run_ai_server.sh --restart` (reloads in-memory `CatalogEngine` index on port `8765`)

---

## 2. Permanent Domain Rules & Edge Cases Learned
- **Root `ai_agent_server.py` vs `ai_agent_server/ai_agent_server.py`**:
  Both files exist (`128,144 bytes`). [`ai_agent_server/run_ai_server.sh`](../../ai_agent_server/run_ai_server.sh) runs `ai_agent_server/ai_agent_server.py`, and root `run_ai_server.sh` delegates to it. Keep them synchronized or edit `ai_agent_server/ai_agent_server.py` and copy to root.
- **DevCentral (`/t5/`) Legacy Redirect Traps**:
  Many legacy `community.f5.com/t5/...` URLs either return HTTP 404 or redirect to completely unrelated forum replies due to Khoros ID collisions. Always verify semantic title alignment between the bookmark's original title and the live destination `<title>` / `<h1>` before accepting a redirect.
- **MyF5 (`my.f5.com/manage/s/article/K...`) SPA Handling**:
  Direct HTTP fetches to `my.f5.com` return an Aura/LWR SPA shell unless inspected via browser or matched against `scratch/all_extracted_my_f5.json` / `bookmarks_verified_metadata.json`.
- **VPN / Internal SSO Classification (`requires_vpn: true`)**:
  Internal F5 hosts (`*.f5net.com`, `*.int.lineratesystems.com`, internal GitLab, SharePoint, ServiceNow, Salesforce, Tableau, Aha!, Confluence/Jira) require VPN/SSO. HTTP 403/401 on public cloud/Akamai/Cloudflare WAFs (e.g., `my.f5.com`, `scadahacker.com`, ` Gartner`) are bot-protection blocks, **not** dead links or VPN-only links.
- **Stale / Archived Bookmarks Audit Trail**:
  Archived bookmarks are stored in:
  - [`archive/audits/live_audit_results.json`](../../archive/audits/live_audit_results.json)
  - [`archive/audits/stale_bookmarks_results.json`](../../archive/audits/stale_bookmarks_results.json)
  - [`archive/audits/stale_bookmarks_review.html`](../../archive/audits/stale_bookmarks_review.html)

---

## 3. Compacted Milestone History
- **2026-10-12 → 2026-10-15**: Built 9-pillar taxonomy, dark showcase UI (`generate_dark_showcase.py`), Edge browser history visit sync (`sync_edge_history_bookmarks.py`), and local AI Agent Server (`ai_agent_server.py`) with Vertex AI (`Gemini 3.8 Flash (Medium)`), Gemini API, Ollama (`gemma3:4b`), and BM25 fallback.
- **2026-10-16 (Morning/Afternoon)**: Executed deep live URL & content alignment audit across all 758 bookmarks (`scratch/deep_live_audit.py`, `scratch/archive_dead_bookmarks.py`). Identified and archived 38 dead/mismatched bookmarks (5 HTTP 404s, 12 broken DevCentral redirects, 21 soft-404/decommissioned pages), leaving 720 healthy bookmarks. Regenerated `bookmarks_showcase.html`, `favorites_product_frequency_organized.html`, and `stale_bookmarks_review.html`.
- **2026-10-16 (Memory Architecture)**: Implemented two-tier persistent memory (`AGENTS.md`, `.agents/memory/`, and `.agents/hooks.json`) to prevent context bloat and preserve working state across auto-compactions.
- **2026-10-16**: Archived 38 dead/404/broken-redirect bookmarks (including DevCentral ta-p/283740), populated live webpage content cache (409+ pages including Discourse <noscript> unwrap & MyF5 KBs), and enforced live HTTP 422 dead-page rejection & archiving in BookmarkInspector.
- **2026-10-16**: Re-investigated all 85 stale bookmarks via /browser, restored 7 valid browser-accessible bookmarks to bookmarks_catalog.json (727 active), cleaned stale_bookmarks_review.html to 76 confirmed dead links, and hardened scripts against unauthenticated urllib false-404s on SSO/SaaS portals.
- **2026-10-16**: Enforced mandatory /browser subagent workflow for adding new bookmarks in AGENTS.md and project memory.
- **2026-10-16**: Fixed Cisco network_performance_metrics.html and external bookmark hierarchy/tag rules in update_and_reorganize_bookmarks.py and batch_enrich_all.py; verified in browser.
- **2026-10-16**: Removed urllib scraping from BookmarkInspector in ai_agent_server.py and enforced /browser-only inspection when adding new bookmarks.
- **2026-10-17**: Deduplicated 29 Tier 1 exact-URL clusters (727 -> 696 bookmarks), restored overwritten visit_counts from pre-cleanup backup, and added exact-URL deduplication guardrails to pipeline scripts.
- **2026-10-17**: Integrated live /browser CDP inspection into BookmarkInspector, fixed non-redirected URL false-positive 422 rejection, and ingested https://help.ai.f5.com/en/ under Pillar 04 -> F5 Workforce AI Security & SurePath.
- **2026-10-17**: Fixed live /browser CDP inspection in BookmarkInspector (ps auxww, navigation-resilient CDP JS polling, non-hanging headless fallback, and None-safe string stripping) and ingested https://www.f5.com/products/distributed-cloud-services/cdn into the 696-bookmark catalog.
- **2026-10-17**: Added canonical BookmarkInspector.ingest_and_persist (--ingest-url CLI), updated AGENTS.md line map to match current 3,222-line ai_agent_server.py and 1,379-line batch_enrich_all.py, and fixed memory_cli.py compact to clear stale working notes.
- **2026-10-17**: Fixed Manage & Delete checkbox selection for dynamically added bookmarks via document event delegation in generate_dark_showcase.py, stripped Chrome #:~:text= scroll fragments in clean_bookmark_url, and cleaned form dropdown noise in live browser inspection.
- **2026-10-17**: Verified and fixed anchored URL (#fragment) inspection in ai_agent_server.py and batch_enrich_all.py: stopped _lookup_verified_entry from stripping #fragments to match parent URLs, enhanced _inspect_via_live_browser to extract #hash DOM sections, and enriched #tenant-data (index 697) via /browser with the full r2600-r12900 rSeries tenant sizing table.
- **2026-10-17**: Verified that https://www.muenchen.de/en/home was added using live /browser inspection (inspected_via: '/browser', 2,101 chars in bookmarks_content_cache.json, reusing the open browser tab via CDP) and polished its card description.
- **2026-10-17**: Made the top header and search/action toolbar section (.sticky-top-shell) sticky at top: 0 with frosted-glass backdrop-filter and scroll-padding-top: 210px in generate_dark_showcase.py and bookmarks_showcase.html.
- **2026-10-17**: Added custom notes support (--notes / --update-notes CLI, POST /api/bookmarks/add & /api/bookmarks/notes, BM25/LLM indexing, and Add Bookmark UI modal + card note badge/editor)
- **2026-10-17**: Fixed custom notes in live browser server + UI, added Cloudflare bot-challenge rejection and LLM fallback to BookmarkInspector, and repaired https://frankfurt.de/ metadata.
- **2026-10-17**: Added mandatory /browser company/brand core business discovery (_discover_company_context) + Imperva WAF challenge detection to BookmarkInspector and AGENTS.md, and re-enriched https://amadeus.com/en/innovation/artificial-intelligence under Pillar 04 with full Amadeus global travel & hospitality ecosystem context.
- **2026-10-17**: Removed all headless browser (--headless=new, --dump-dom) and raw urllib website fetching from ai_agent_server.py; enforced strict /browser subagent-only website inspection across codebase and AGENTS.md.
- **2026-10-17**: Audited all 702 bookmarks for /browser inspection coverage, inspected and enriched all 7 missing/recently added bookmarks (Phoenix Innovations, HOFFMANN.AI, LDBV IT-DLZ, Amadeus AI, F5OS-A 2.0.0 Tenant Data, Gartner AI App Security, and K73819494) with company core-business context, fixed external domain summary padding in batch_enrich_all.py, and updated all 3 JSON stores and HTML outputs.
- **2026-10-23**: Enabled AI Agent Server traffic logging, analyzed live bookmark ingestion of K000163695 (FE-POST-3970, 4.363s total: 3.64s live CDP browser extraction, 21ms heuristic enrichment, 0.68s store persistence & HTML rebuild), and documented findings in demo-adding-bookmark.md.
- **2026-10-23**: Inspected runtime logs for adding a bookmark (FE-POST-3970 -> demo-adding-bookmark.md) and searching via Ask AI Copilot (FE-POST-4037 / LLM-4038 / LLM-4039 -> demo-searching-bookmarks.md), documenting the 3-stage Vertex AI + BM25 + ContentInspector pipeline and 4 architectural findings.
- **2026-10-23**: Created demo-bookmark-project.md documenting the complete architecture, 3-store data layer, 9-pillar taxonomy, build/enrichment scripts, AI Agent Server, agent memory/hooks, and 6 operational workflows.
- **2026-10-23**: Refactored sync_edge_history_bookmarks.py into a safe Edge/Chrome SQLite visit-count synchronizer + candidate reporter (--dry-run, --show-candidates) that calls update_and_reorganize_bookmarks.py + generate_dark_showcase.py without injecting uncurated bookmarks, and retired tag_vpn_and_reexport.py to archive/legacy_scripts/.
- **2026-10-23**: Fixed ContentInspector stale cache overwrite bug, stripped _tokens/icon/content_summary bloat from /api/chat (reducing payload ~90%), upgraded AIAgentServer to ThreadingHTTPServer with RLock, and repaired 4 cross-contaminated MyF5 KB articles (K17160, K86112227, K8986, K84554955).
- **2026-10-24**: Prepared v1.0.0 GitHub release: added README.md, .gitignore, bookmarks_catalog.example.json (18 public items), ai_agent_server.conf.example, portable path fallbacks, and sanitized all tracked code and docs.
