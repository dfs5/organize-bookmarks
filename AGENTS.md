# 🧠 Project Rules & Compacted Index (`AGENTS.md`)

> **CRITICAL CONTEXT-PROTECTION RULES (READ FIRST)**
> This workspace contains multi-megabyte data files and generated HTML bundles that will immediately trigger session compaction if read directly.

## 1. Strict File Access & Context Guardrails

### ❌ NEVER Call `view_file` (Without Tight `StartLine`/`EndLine`) Or `cat`/`grep` Full Output On:
| File | Size | Safe Alternative |
| :--- | :--- | :--- |
| `bookmarks_showcase.html` | `4.0 MB` | **Generated output!** Edit [`generate_dark_showcase.py`](generate_dark_showcase.py) using line slices from the Code Map below, then run `python3 generate_dark_showcase.py`. |
| `favorites_product_frequency_organized.html` | `390 KB` | **Generated output!** Edit [`update_and_reorganize_bookmarks.py`](update_and_reorganize_bookmarks.py) and run it. |
| `bookmarks_catalog.json` | `2.0 MB` | Query via `python3 .agents/skills/bookmark-lookup/lookup.py "<query>"` or write a 5-line inline Python filter printing only matching indices/fields (always exclude `icon` base64 data!). |
| `ai_agent_server/bookmarks_verified_metadata.json` | `2.2 MB` | Inspect specific URL keys via inline Python (`json.load` + dict lookup). |
| `ai_agent_server/bookmarks_content_cache.json` | `1.2 MB` | Inspect specific URL keys via inline Python (`json.load` + dict lookup). |
| `archive/audits/*.json` & `archive/backups/*.json` | `0.5–4 MB` | Inspect via Python summary scripts; never dump raw JSON to stdout. |

### ✅ Mandatory Memory Workflow
1. **At the start of multi-step tasks**: Update the active session scratchpad using:
   ```bash
   python3 .agents/memory/memory_cli.py set-goal "<concise goal>"
   ```
2. **During work (after milestones or audits)**: Record verified findings, indices, or completed steps so they survive auto-compaction:
   ```bash
   python3 .agents/memory/memory_cli.py complete-step "<what was finished>"
   python3 .agents/memory/memory_cli.py add-note "<key finding / line numbers / URL count>"
   ```
3. **When finishing a major task**: Compact session learnings into long-term project memory (auto-updates the vector & FTS5 index):
   ```bash
   python3 .agents/memory/memory_cli.py compact --summary "<1-2 line milestone summary>"
   ```
4. **Semantic & Keyword Memory Search**: Before investigating historical rules, past audits, or code locations from scratch, search the indexed memory database (`.agents/memory/memory_index.sqlite`):
   ```bash
   python3 .agents/memory/memory_cli.py search "<query>" --top-k 4
   ```

### 🌐 Mandatory `/browser` Rule for Adding & Inspecting Bookmarks
- **ALWAYS use the `/browser` subagent (`invoke_subagent` with `TypeName: "browser"`) whenever inspecting websites, adding new bookmarks, or inspecting newly added bookmarks.**
- **NEVER use a headless browser (`--headless`, `--dump-dom`, HeadlessChrome) or raw Python `urllib` HTTP fetches** when inspecting websites or adding bookmarks:
  1. **Company / Brand Core Business Discovery First**: When adding or enriching a bookmark on a company/brand domain, use the `/browser` subagent to first understand what the company/brand is about and what its **core business, industry vertical, products, and solutions** are (opening the root homepage or `/about` / `/solutions` / `/portfolio` pages under the same domain if the target subpage doesn't state it explicitly).
  2. **Target Page Inspection**: Next, open the actual target bookmark URL in the `/browser` subagent to extract the real rendered `<title>`, headings, and core page content (handling JS SPAs, Cloudflare/Imperva WAFs, and existing browser SSO sessions), and synthesize the `description` and `content_summary` so they explicitly connect the page's topic to the company's main business (e.g., for `amadeus.com/en/innovation/artificial-intelligence`, explicitly ground the AI initiatives in Amadeus's global travel & hospitality technology ecosystem).
  3. **Login / Authentication Wall Guardrail**: If `/browser` hits an SSO login screen (`Sign In`, Okta, Highspot, SharePoint/Microsoft login, APM policy logon, etc.) that cannot be bypassed automatically, **stop and ask the user to log in via the browser first** — NEVER save a bookmark with the title, description, summary, or tags of a login page.
  4. **Core Content Only**: Summarize only the core content of the target page framed within the company's core business context (never follow unrelated external links or include "Related Content" / sidebar noise; for link-collection KBs like "Recommended Actions", summarize the core link titles without following them).
  5. **One-Command Canonical Ingestion (`--ingest-url` & `--import-file`)**: Never write ad-hoc inline Python scripts to save bookmarks to `bookmarks_catalog.json` or `bookmarks_verified_metadata.json`. Instead, pass the `/browser` subagent payload (including `"company_context"`) directly to the canonical CLI helper (which validates schema, updates all 3 JSON stores, and regenerates both HTML files in one step):
     ```bash
     python3 ai_agent_server/ai_agent_server.py --ingest-url "<url>" --browser-json '<json>' --notes "<optional custom notes>"
     ```
     For bulk bookmark files (Netscape `.html` exports, Chrome/Edge `Bookmarks` JSON, `.json` catalog lists, or `.txt`/`.md` URL lists), use `--import-file` (always preview with `--dry-run` first) or `POST /api/bookmarks/import`:
     ```bash
     python3 ai_agent_server/ai_agent_server.py --import-file "<path>" --dry-run
     python3 ai_agent_server/ai_agent_server.py --import-file "<path>" --max-import 20 --notes "<optional batch notes>"
     ```
  6. **Pillar-to-Tag Alignment**: Verify in `/browser` that the newly added card in `bookmarks_showcase.html` has a clean title, complete grammatical description (110–180 chars, no mid-clause truncation), 150–250 word hidden summary reflecting the company's main business, and product/topic/source tags that strictly align with its assigned Strategic Pillar and Subcategory.

---

## 2. Canonical Data Schema & Taxonomy

### `bookmarks_catalog.json` (Initialized from `bookmarks_catalog.example.json` on Fresh Clones)
A JSON `list` of bookmark objects. Each item has:
- `url` (`str`), `previous_url` (`str`, optional): Canonical URL and pre-redirect/legacy URL.
- `title` (`str`), `description` (`str`), `content_summary` (`str`), `content_hash` (`str`).
- `notes` (`str`, optional): Custom user notes attached to the link (preserved across deduplication/enrichment, indexed in BM25/AI search, and displayed on showcase cards).
- `hierarchy` (`list[str]`): `[Pillar, Subcategory]` (2-level hierarchy).
- `tags` (`dict`): `{"products": [...], "topics": [...], "source_types": [...]}`.
- `visit_count` (`int`), `add_date` (`str`), `legacy_path` (`list[str]`).
- `requires_vpn` (`bool`), `is_official_f5` (`bool`).
- `icon` (`str`): Base64 data URI (**always strip/ignore when printing items in scripts**).

### 9 Canonical Pillars (`hierarchy[0]`)
1. `01. BIG-IP & TMOS`
2. `02. NGINX Ecosystem`
3. `03. F5 Distributed Cloud (XC) & Multi-Cloud`
4. `04. AI Security, Workforce AI & Agentic AI`
5. `05. Knowledge Base (KBs) & Official TechDocs`
6. `06. Product Lifecycle, Releases & Roadmaps`
7. `07. Lab Environments, Demos & Developer Ecosystem`
8. `08. Internal Sales Engineering & Enablement`
9. `09. External Engineering, Protocols & Tools`

---

## 3. Code Map (Use Exact Line Ranges with `view_file`)

### [`ai_agent_server/ai_agent_server.py`](ai_agent_server/ai_agent_server.py) (4,381 lines)
- `L35–L209`: Config loader (`load_config`), path resolution, Vertex AI model/endpoint helpers (`resolve_vertex_model`, `get_vertex_endpoint`).
- `L218–L416`: `CommunicationLogger` — traffic logging & token redaction (`ai_communication.log`).
- `L429–L552`: `send_llm_request` & `GoogleAuthHelper` (ADC token + Project ID resolution).
- `L567–L808`: `HtmlTextExtractor` & `ContentInspector` (`fetch_url`, `analyze_relevance`, `verify_candidates`).
- `L815–L1121`: `LLMIntentExtractor` (`extract`, `_extract_via_vertex`, `_extract_via_ollama`, `_extract_via_gemini`).
- `L1127–L1450`: `CatalogEngine` — BM25 index (`_build_index`), `_heuristic_extract_intent`, hybrid `search`.
- `L1455–L1735`: `LLMBridge` — AI chat synthesis (`generate_synthesis`, Vertex/Gemini/Ollama/Heuristic cascade).
- `L1741–L1855`: `WebPageContentExtractor` — HTML parser fallback.
- `L1858–L3350`: `BookmarkInspector` — `_discover_browser_ws_endpoint` (`L2062–L2107`), `_inspect_via_browser_ws` (`L2109–L2296`), `_discover_browser_cdp_port` (`L2298–L2354`), `_cdp_ws_eval` (`L2356–L2460`), `_inspect_via_macos_open_tab` (`L2462–L2539`), `_inspect_via_live_browser` (`L2541–L2673`), `fetch_page` (`L2675–L2885`), `detect_official_f5` (`L2887–L2913`), `inspect_and_enrich` (`L2915–L3061`), `ingest_and_persist` (`L3063–L3142`), `import_bookmarks_batch` (`L3144–L3350`).
- `L3357–L3565`: `parse_bookmarks_import_payload` (multi-format parser for Netscape HTML, Chrome/Edge JSON, catalog JSON, and URL lists).
- `L3569–L4381`: `AIAgentHandler` (`do_GET`, `do_POST` for `/api/search`, `/api/chat`, `/api/bookmarks/add`, `/api/bookmarks/import`, `/api/bookmarks/delete`) & `main` (`--ingest-url`, `--import-file` CLI + server entrypoint `L4280–L4381`).

### [`generate_dark_showcase.py`](generate_dark_showcase.py) (4,649 lines)
- `L1–L33`: Catalog load, `get_pillar_and_sub`, `esc`, HTML header start.
- `L34–L615`: Core CSS styles (dark theme, layout, cards, badges).
- `L616–L995`: `render_card(b, is_recent=False)` & Python template generation for pillars and Single/Bulk Add Bookmark modals (`#addErrorBox` persistent inline alert at `L955`).
- `L996–L2680`: AI Copilot drawer CSS, Bulk Import & persistent error banner CSS (`L1264–L1310`), Add/Delete modal markup, and static HTML structure.
- `L2681–L3015`: Client JS — `refreshCardsList`, `applyFilters`, `showToast` (`L2771–L2836`, manual popover with 25s error duration & pause-on-hover), `toggleManageMode`, `openDeleteModal`.
- `L3016–L3650`: Client JS — Add Bookmark modal (`showAddModalError` / `hideAddModalError` at `L3075–L3085`, `openAddModal`, `switchAddModalTab`, `submitNewBookmark`, `runBulkImport`, `injectNewCardIntoDOM`).
- `L3651–L4649`: Client JS — AI Copilot drawer, `selectProductScope`, `probeServer`, `appendMessage`, `locateCardOnPage`, `clientFallbackSearch`, `submitAiQuery`, and final write to `bookmarks_showcase.html`.

### Other Core Scripts
- [`update_and_reorganize_bookmarks.py`](update_and_reorganize_bookmarks.py) (`730 lines`): `clean_title` (`L39–L181`), `assign_hierarchy` (`L191–L400`), `is_valid_redirect` (`L410–L430`), `main` (`L446–L727`).
- [`batch_enrich_all.py`](batch_enrich_all.py) (`1,379 lines`): `clean_card_title` (`L88–L165`), `format_clean_description` (`L167–L239`), `extract_core_description` (`L241–L332`), `summarize_text` (`L335–L446`), `_generate_domain_summary_raw` (`L479–L982`), `enrich_tags` (`L984–L1144`), `main` (`L1146–L1376`).
- [`sync_edge_history_bookmarks.py`](sync_edge_history_bookmarks.py) (`285 lines`): Safely reads Edge/Chrome SQLite history to sync `visit_count` on existing curated bookmarks (and optionally list unbookmarked candidates via `--show-candidates`) without injecting unverified stubs.
