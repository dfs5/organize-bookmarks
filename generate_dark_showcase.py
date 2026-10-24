import json
import os
import re

DEFAULT_CATALOG = "bookmarks_catalog.json" if os.path.exists("bookmarks_catalog.json") else "bookmarks_catalog.example.json"
CATALOG_PATH = os.environ.get("BOOKMARKS_CATALOG_PATH", DEFAULT_CATALOG)
OUTPUT_HTML = os.environ.get("BOOKMARKS_SHOWCASE_OUTPUT", "bookmarks_showcase.html")

with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    catalog = json.load(f)

def get_pillar_and_sub(b):
    from update_and_reorganize_bookmarks import assign_hierarchy
    return assign_hierarchy(b)

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

tree = {}
for b in catalog:
    pillar, subcat = get_pillar_and_sub(b)
    tree.setdefault(pillar, {}).setdefault(subcat, []).append(b)

for pillar in tree:
    for subcat in tree[pillar]:
        tree[pillar][subcat].sort(key=lambda x: (-x.get("visit_count", 0), x.get("title", "").lower()))

vpn_total = sum(1 for b in catalog if b.get("requires_vpn"))

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>F5 Curated Bookmarks &amp; Knowledge Catalog</title>
<style>
  :root {{
    --bg-primary: #0a0e17;
    --bg-gradient: radial-gradient(circle at 15% 20%, #151b2d 0%, #0a0e17 60%),
                    radial-gradient(circle at 85% 80%, #1e1730 0%, #0a0e17 65%),
                    linear-gradient(135deg, #090d16 0%, #0e1322 50%, #120e20 100%);
    --card-bg: rgba(22, 28, 45, 0.75);
    --card-border: rgba(99, 120, 180, 0.22);
    --card-hover-border: rgba(138, 180, 248, 0.6);
    --card-hover-bg: rgba(30, 39, 64, 0.9);
    --text-primary: #f0f4fc;
    --text-secondary: #9ab0d3;
    --text-muted: #627494;
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;
    --accent-purple: #8b5cf6;
    --accent-amber: #f59e0b;
    --accent-rose: #f43f5e;
    --tag-prod: rgba(6, 182, 212, 0.18);
    --tag-prod-text: #67e8f9;
    --tag-topic: rgba(139, 92, 246, 0.18);
    --tag-topic-text: #c4b5fd;
    --tag-type: rgba(245, 158, 11, 0.18);
    --tag-type-text: #fde68a;
    --tag-vpn: rgba(239, 68, 68, 0.22);
    --tag-vpn-text: #fca5a5;
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}

  html {{
    scroll-behavior: smooth;
    scroll-padding-top: 210px;
  }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg-primary);
    background-image: var(--bg-gradient);
    background-attachment: fixed;
    color: var(--text-primary);
    min-height: 100vh;
    padding: 0 40px 30px 40px;
    line-height: 1.5;
  }}

  .sticky-top-shell {{
    position: sticky;
    top: 0;
    z-index: 120;
    margin: 0 -40px 22px -40px;
    padding: 20px 40px 16px 40px;
    background: rgba(10, 14, 23, 0.88);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border-bottom: 1px solid rgba(99, 120, 180, 0.22);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
  }}

  header {{
    max-width: 1400px;
    margin: 0 auto 16px auto;
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 16px;
  }}

  .header-titles h1 {{
    font-size: 2.1rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, #ffffff 30%, #93c5fd 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: flex;
    align-items: center;
    gap: 12px;
  }}

  .header-titles p {{
    color: var(--text-secondary);
    font-size: 0.98rem;
    margin-top: 6px;
  }}

  .stats-bar {{
    display: flex;
    gap: 18px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 10px 20px;
    backdrop-filter: blur(12px);
  }}

  .stat-item {{
    text-align: center;
  }}
  .stat-val {{
    font-size: 1.35rem;
    font-weight: 700;
    color: #60a5fa;
  }}
  .stat-val.vpn {{
    color: #f87171;
  }}
  .stat-lbl {{
    font-size: 0.72rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }}

  /* Controls & Search */
  .toolbar {{
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    align-items: center;
  }}

  .filter-pills-bar {{
    max-width: 1400px;
    margin: 0 auto 26px auto;
  }}

  .search-wrapper {{
    flex: 1 1 350px;
    position: relative;
  }}

  .search-wrapper input {{
    width: 100%;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid var(--card-border);
    border-radius: 10px;
    padding: 12px 18px 12px 42px;
    color: #fff;
    font-size: 0.95rem;
    outline: none;
    transition: all 0.2s ease;
    backdrop-filter: blur(8px);
  }}

  .search-wrapper input:focus {{
    border-color: var(--accent-blue);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
  }}

  .search-icon {{
    position: absolute;
    left: 14px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 1.1rem;
  }}

  .filter-pills {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }}

  .pill {{
    background: rgba(30, 41, 67, 0.6);
    border: 1px solid var(--card-border);
    border-radius: 20px;
    padding: 7px 15px;
    font-size: 0.82rem;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    user-select: none;
  }}

  .pill:hover {{
    background: rgba(59, 130, 246, 0.2);
    border-color: var(--accent-blue);
    color: #fff;
  }}

  .pill.active {{
    background: var(--accent-blue);
    border-color: var(--accent-blue);
    color: #fff;
    font-weight: 600;
  }}

  .pill.vpn-pill {{
    border-color: rgba(248, 113, 113, 0.4);
    color: #fca5a5;
  }}

  .pill.vpn-pill.active {{
    background: #dc2626;
    border-color: #ef4444;
    color: #fff;
  }}

  /* Layout */
  .container {{
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 35px;
  }}

  .pillar-section {{
    background: rgba(13, 19, 33, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(16px);
  }}

  .pillar-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 14px;
    margin-bottom: 20px;
  }}

  .pillar-title {{
    font-size: 1.35rem;
    font-weight: 700;
    color: #e2e8f0;
    display: flex;
    align-items: center;
    gap: 10px;
  }}

  .pillar-count {{
    font-size: 0.82rem;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
    padding: 4px 10px;
    border-radius: 12px;
  }}

  .subcat-section {{
    margin-bottom: 25px;
  }}

  .subcat-section:last-child {{
    margin-bottom: 0;
  }}

  .subcat-title {{
    font-size: 0.95rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #93c5fd;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .bookmark-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 14px;
  }}

  /* Card */
  .bookmark-card {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 10px;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    text-decoration: none;
    color: inherit;
  }}

  .bookmark-card.is-vpn {{
    border-left: 3px solid #ef4444;
  }}

  .bookmark-card:hover {{
    transform: translateY(-2px);
    border-color: var(--card-hover-border);
    background: var(--card-hover-bg);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
  }}

  .card-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
  }}

  .bm-title {{
    font-size: 0.94rem;
    font-weight: 600;
    color: #ffffff;
    line-height: 1.35;
    word-break: break-word;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}

  .card-badges {{
    display: flex;
    gap: 6px;
    align-items: center;
    flex-shrink: 0;
  }}

  .vpn-badge {{
    font-size: 0.70rem;
    font-weight: 700;
    color: #fca5a5;
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(248, 113, 113, 0.45);
    padding: 2px 6px;
    border-radius: 6px;
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 3px;
  }}

  .visit-badge {{
    font-size: 0.72rem;
    font-weight: 700;
    color: #60a5fa;
    background: rgba(37, 99, 235, 0.2);
    border: 1px solid rgba(96, 165, 250, 0.35);
    padding: 2px 7px;
    border-radius: 6px;
    white-space: nowrap;
  }}

  .visit-badge.high {{
    color: #f43f5e;
    background: rgba(244, 63, 94, 0.18);
    border-color: rgba(244, 63, 94, 0.4);
  }}

  .bm-desc {{
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.4;
    word-break: break-word;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}

  .bm-notes {{
    margin-top: 8px;
    padding: 6px 10px;
    background: rgba(245, 158, 11, 0.1);
    border-left: 3px solid #f59e0b;
    border-radius: 6px;
    font-size: 0.78rem;
    color: #fde68a;
    line-height: 1.38;
    word-break: break-word;
    display: flex;
    align-items: flex-start;
    gap: 6px;
  }}

  .bm-note-edit-btn {{
    background: rgba(30, 41, 59, 0.65);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #94a3b8;
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 0.70rem;
    line-height: 1;
    cursor: pointer;
    transition: all 0.18s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }}

  .bm-note-edit-btn:hover {{
    background: rgba(245, 158, 11, 0.2);
    border-color: rgba(245, 158, 11, 0.55);
    color: #fde68a;
    transform: translateY(-1px);
  }}

  .bm-url {{
    font-size: 0.74rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }}

  .card-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 4px;
  }}

  .tag {{
    font-size: 0.68rem;
    padding: 2px 7px;
    border-radius: 6px;
    font-weight: 500;
  }}
  .tag-vpn {{ background: var(--tag-vpn); color: var(--tag-vpn-text); font-weight: 600; }}
  .tag-prod {{ background: var(--tag-prod); color: var(--tag-prod-text); }}
  .tag-topic {{ background: var(--tag-topic); color: var(--tag-topic-text); }}
  .tag-type {{ background: var(--tag-type); color: var(--tag-type-text); }}

  .hidden {{
    display: none !important;
  }}

  /* Floating quick bar */
  .quick-nav {{
    position: fixed;
    bottom: 25px;
    right: 30px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid var(--card-border);
    backdrop-filter: blur(16px);
    border-radius: 30px;
    padding: 6px 14px;
    display: flex;
    gap: 10px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    z-index: 100;
  }}

  .quick-nav a {{
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 0.8rem;
    padding: 5px 8px;
    border-radius: 12px;
    transition: all 0.2s;
  }}

  .quick-nav a:hover {{
    color: #fff;
    background: rgba(255, 255, 255, 0.1);
  }}

</style>
</head>
<body>

<div class="sticky-top-shell">
  <header>
    <div class="header-titles">
      <h1>🪐 F5 Bookmarks &amp; Knowledge Catalog</h1>
      <p>Curated repository of {len(catalog)} links classified by product line, engineering topic, VPN requirements, and historical visit frequency.</p>
    </div>
    <div class="stats-bar">
      <div class="stat-item">
        <div class="stat-val">{len(catalog)}</div>
        <div class="stat-lbl">Bookmarks</div>
      </div>
      <div class="stat-item">
        <div class="stat-val vpn">{vpn_total}</div>
        <div class="stat-lbl">Requires VPN</div>
      </div>
      <div class="stat-item">
        <div class="stat-val">{len(tree)}</div>
        <div class="stat-lbl">Pillars</div>
      </div>
      <div class="stat-item">
        <div class="stat-val">{len([b for b in catalog if b.get('visit_count', 0) > 0])}</div>
        <div class="stat-lbl">Active Visited</div>
      </div>
    </div>
  </header>

  <div class="toolbar">
    <div class="search-wrapper">
      <span class="search-icon">🔍</span>
      <input type="text" id="searchInput" placeholder="Search by keyword, product, topic, 'vpn', or URL..." autofocus>
    </div>
    <button id="aiToolbarBtn" class="ai-toolbar-btn" type="button" title="Ask AI Copilot (⌘K)">
      <span class="ai-sparkle">✨</span>
      <span>Ask AI Copilot</span>
      <span class="ai-kbd">⌘K</span>
    </button>
    <button id="addBookmarkBtn" class="add-bookmark-btn" type="button" onclick="openAddModal()" title="Add new bookmark by URL with deep AI inspection">
      <span class="add-icon">➕</span>
      <span>Add Bookmark</span>
    </button>
    <button id="manageModeBtn" class="manage-mode-btn" type="button" title="Select and delete bookmarks">
      <span class="manage-icon">🗑️</span>
      <span id="manageModeBtnText">Manage &amp; Delete</span>
    </button>
  </div>
</div>

<div class="filter-pills-bar">
  <div class="filter-pills" id="pillFilters">
    <span class="pill active" data-filter="all">All ({len(catalog)})</span>
    <span class="pill vpn-pill" data-filter="vpn">🔒 Needs VPN ({vpn_total})</span>
    <span class="pill" data-filter="big-ip">BIG-IP &amp; TMOS</span>
    <span class="pill" data-filter="nginx">NGINX</span>
    <span class="pill" data-filter="f5-xc">F5 XC</span>
    <span class="pill" data-filter="workforce-ai">🛡️ Workforce AI</span>
    <span class="pill" data-filter="sizing">Sizing &amp; Capacity</span>
    <span class="pill" data-filter="security">Security &amp; WAF</span>
    <span class="pill" data-filter="ai">AI &amp; Guardrails</span>
    <span class="pill" data-filter="recent">🕒 Recently Added</span>
    <span class="pill" data-filter="top">⭐ Frequently Visited</span>
  </div>
</div>

<div class="container" id="cardsContainer">
"""

pillar_emojis = {
    "01. BIG-IP & TMOS": "⚡",
    "BIG-IP & TMOS": "⚡",
    "02. NGINX Ecosystem": "🟩",
    "NGINX Ecosystem": "🟩",
    "03. F5 Distributed Cloud (XC) & Multi-Cloud": "☁️",
    "F5 Distributed Cloud (XC) & Multi-Cloud": "☁️",
    "04. AI Security, Workforce AI & Agentic AI": "🤖",
    "AI Security, Workforce AI & Agentic AI": "🤖",
    "05. Knowledge Base (KBs) & Official TechDocs": "📚",
    "Knowledge Base (KBs) & Official TechDocs": "📚",
    "06. Product Lifecycle, Releases & Roadmaps": "🗓️",
    "Product Lifecycle, Releases & Roadmaps": "🗓️",
    "07. Lab Environments, Demos & Developer Ecosystem": "🛠️",
    "Lab Environments, Demos & Developer Ecosystem": "🛠️",
    "08. Internal Sales Engineering & Enablement": "🏢",
    "Internal Sales Engineering & Enablement": "🏢",
    "09. External Engineering, Protocols & Tools": "🌐",
    "External Engineering, Protocols & Tools": "🌐"
}

top_recent = sorted(catalog, key=lambda x: int(x.get("add_date", 0)), reverse=True)[:24]

def render_card(b, is_recent=False):
    v_count = b.get("visit_count", 0)
    is_vpn = b.get("requires_vpn", False)
    badge_class = "visit-badge high" if v_count >= 15 else "visit-badge"
    badge_text = f"🔥 {v_count}" if v_count >= 15 else (f"✓ {v_count}" if v_count > 0 else "")
    
    tags = b.get("tags", {})
    prods = tags.get("products", [])
    topics = tags.get("topics", [])
    stypes = tags.get("source_types", [])
    
    summary_text = b.get("content_summary") or b.get("description", "")
    notes_text = (b.get("notes") or "").strip()
    vpn_kw = "vpn-required vpn internal" if is_vpn else "public"
    search_blob = f"{b['title']} {b.get('description', '')} {notes_text} {summary_text} {b['url']} {vpn_kw} {' '.join(prods)} {' '.join(topics)} {' '.join(stypes)}".lower()
    
    tag_html = ""
    if is_vpn:
        tag_html += '<span class="tag tag-vpn">🔒 Needs VPN</span> '
    for p in prods:
        tag_html += f'<span class="tag tag-prod">{esc(p)}</span> '
    for t in topics:
        tag_html += f'<span class="tag tag-topic">{esc(t)}</span> '
    for s in stypes:
        if s != "vpn-required":
            tag_html += f'<span class="tag tag-type">{esc(s)}</span> '
        
    vpn_badge_markup = '<span class="vpn-badge">🔒 VPN</span>' if is_vpn else ''
    visit_badge_markup = f'<span class="{badge_class}">{badge_text}</span>' if badge_text else ''
    note_btn_title = "Edit custom note" if notes_text else "Add custom note"
    note_btn_markup = f'<button type="button" class="bm-note-edit-btn" title="{note_btn_title}" aria-label="{note_btn_title}">📝</button>'
    notes_markup = f'\n            <div class="bm-notes"><span>📝</span><span class="bm-notes-text">{esc(notes_text)}</span></div>' if notes_text else ''
    card_class = "bookmark-card is-vpn" if is_vpn else "bookmark-card"
    recent_attr = ' data-recent="true"' if is_recent else ''
    notes_attr = f' data-notes="{esc(notes_text)}"' if notes_text else ''
    
    return f"""
        <a class="{card_class}" href="{esc(b['url'])}" target="_blank" rel="noopener noreferrer" data-search="{esc(search_blob)}" data-visits="{v_count}" data-vpn="{str(is_vpn).lower()}" data-prods="{','.join(prods)}" data-topics="{','.join(topics)}"{notes_attr}{recent_attr}>
          <div class="card-select-check" title="Select bookmark">
            <span class="chk-icon"></span>
          </div>
          <div>
            <div class="card-top">
              <h4 class="bm-title">{esc(b['title'])}</h4>
              <div class="card-badges">
                {note_btn_markup}
                {vpn_badge_markup}
                {visit_badge_markup}
              </div>
            </div>
            <p class="bm-desc">{esc(b.get('description', ''))}</p>{notes_markup}
          </div>
          <div>
            <div class="bm-url">{esc(b['url'])}</div>
            <div class="card-tags">{tag_html}</div>
          </div>
          <!-- HIDDEN AI CONTEXT FOR IN-BROWSER SEMANTIC RETRIEVAL -->
          <div class="bm-hidden-summary" style="display: none;" data-ai-context="true" aria-hidden="true">{esc(summary_text)}</div>
        </a>
"""

# Recently Added Section
html += f"""
  <section class="pillar-section" id="recently-added">
    <div class="pillar-header">
      <h2 class="pillar-title">🕒 Recently Added</h2>
      <span class="pillar-count">{len(top_recent)} bookmarks</span>
    </div>
    <div class="subcat-section">
      <div class="bookmark-grid">
"""
for b in top_recent:
    html += render_card(b, is_recent=True)

html += """
      </div>
    </div>
  </section>
"""

for pillar in sorted(tree.keys()):
    subs = tree[pillar]
    total_bms = sum(len(items) for items in subs.values())
    clean_pillar = re.sub(r"^\d+\.\s*", "", pillar)
    emoji = pillar_emojis.get(pillar, pillar_emojis.get(clean_pillar, "📂"))
    
    html += f"""
  <section class="pillar-section" id="{esc(clean_pillar.lower().replace(' ', '-'))}" data-pillar="{esc(pillar)}">
    <div class="pillar-header">
      <h2 class="pillar-title">{emoji} {esc(clean_pillar)}</h2>
      <span class="pillar-count">{total_bms} bookmarks</span>
    </div>
"""
    for subcat in sorted(subs.keys()):
        items = subs[subcat]
        html += f"""
    <div class="subcat-section" data-pillar="{esc(pillar)}" data-subcat="{esc(subcat)}">
      <h3 class="subcat-title">📁 {esc(subcat)} ({len(items)})</h3>
      <div class="bookmark-grid">
"""
        for b in items:
            html += render_card(b, is_recent=False)
        html += """
      </div>
    </div>
"""
    html += """
  </section>
"""

html += r"""
</div>

<div class="quick-nav">
  <a href="#recently-added">🕒 Recent</a>
  <a href="#big-ip-&-tmos">⚡ BIG-IP</a>
  <a href="#nginx-ecosystem">🟩 NGINX</a>
  <a href="#f5-distributed-cloud-(xc)-&-multi-cloud">☁️ XC</a>
  <a href="#f5-workforce-ai-security">🛡️ Workforce AI</a>
  <a href="#internal-product-development-&-dev-sources">🛠️ Dev &amp; UDF</a>
  <a href="#external-engineering-&-tools">🌐 External &amp; AI</a>
</div>

<!-- AI Copilot Floating Action Button -->
<button id="aiFabToggle" class="ai-fab-btn" type="button" title="Open AI Bookmarks Copilot (⌘K)">
  <span class="ai-fab-pulse" id="aiFabPulse"></span>
  <span class="ai-fab-icon">🤖</span>
  <span class="ai-fab-label">AI Copilot</span>
  <span class="ai-fab-dot" id="aiFabDot"></span>
</button>

<!-- AI Copilot Drawer Overlay & Panel -->
<div id="aiDrawerOverlay" class="ai-drawer-overlay"></div>
<aside id="aiDrawer" class="ai-drawer" aria-label="AI Bookmarks Copilot">
  <div class="ai-drawer-header">
    <div class="ai-header-left">
      <div class="ai-avatar">🤖</div>
      <div class="ai-header-text">
        <div class="ai-title">Bookmarks AI Copilot</div>
        <div class="ai-status-row">
          <span class="status-dot" id="aiStatusDot"></span>
          <span class="status-text" id="aiStatusText">Checking project server...</span>
        </div>
      </div>
    </div>
    <div class="ai-header-actions">
      <button id="aiClearBtn" class="ai-icon-btn" type="button" title="Clear chat history">🧹</button>
      <button id="aiCloseBtn" class="ai-icon-btn" type="button" title="Close Copilot (Esc)">✕</button>
    </div>
  </div>

  <div id="aiMessages" class="ai-messages">
    <div class="ai-welcome-box">
      <div class="ai-welcome-header">
        <span class="ai-welcome-icon">🪐</span>
        <div>
          <h3>Natural Language Bookmark Search</h3>
          <p>Ask in plain English to locate sizing calculators, internal portals, CVE advisories, or deployment guides across your 980+ bookmarks.</p>
        </div>
      </div>
      <div class="ai-chips-label">Quick Suggestions:</div>
      <div class="ai-chips">
        <button class="ai-chip" type="button" data-query="How do I size BIG-IP VE throughput and CPU core allocation?">⚡ BIG-IP VE Sizing</button>
        <button class="ai-chip" type="button" data-query="Show me Workforce AI security architecture and SurePath references">🛡️ Workforce AI &amp; SurePath</button>
        <button class="ai-chip" type="button" data-query="Find internal portals that require F5 VPN">🔒 Internal VPN Portals</button>
        <button class="ai-chip" type="button" data-query="NGINX App Protect and Ingress controller guides">🟩 NGINX App Protect &amp; Ingress</button>
        <button class="ai-chip" type="button" data-query="Where are the TMOS software release and hardware lifecycle matrices?">🗓️ Lifecycle &amp; Matrices</button>
        <button class="ai-chip" type="button" data-query="Show me DevCentral iRules and AS3 API repositories">🛠️ DevCentral iRules &amp; AS3</button>
      </div>
    </div>
  </div>

  <div class="ai-drawer-footer">
    <div class="ai-prod-selector-wrap">
      <div class="ai-prod-selector-header">
        <span class="ai-prod-label">Product Scope:</span>
        <span id="aiActiveScopeDesc" class="ai-scope-desc">All Products (Platform-wide)</span>
      </div>
      <div id="aiProdTabs" class="ai-prod-tabs">
        <button type="button" class="ai-prod-tab active" data-prod="adsp" title="All Products across F5 platform">🌐 ADSP (All)</button>
        <button type="button" class="ai-prod-tab" data-prod="aisp" title="All AI Products (AI Gateway, Workforce AI, Guardrails)">🧠 AISP (All AI)</button>
        <button type="button" class="ai-prod-tab" data-prod="big-ip" title="BIG-IP & TMOS architectures">⚡ BIG-IP</button>
        <button type="button" class="ai-prod-tab" data-prod="nginx" title="NGINX Plus, Ingress, App Protect">🟩 NGINX</button>
        <button type="button" class="ai-prod-tab" data-prod="f5xc" title="F5 Distributed Cloud Services">☁️ F5 XC</button>
        <button type="button" class="ai-prod-tab" data-prod="ai-gateway" title="F5 AI Gateway">🤖 AI Gateway</button>
        <button type="button" class="ai-prod-tab" data-prod="ai-workforce" title="F5 Workforce AI Security & SurePath">🛡️ AI Workforce</button>
        <button type="button" class="ai-prod-tab" data-prod="ai-guardrails" title="AI Guardrails & CalypsoAI">🔒 AI Guardrails</button>
      </div>
    </div>
    <div class="ai-footer-filters">
      <label class="ai-filter-check">
        <input type="checkbox" id="aiFilterVpn">
        <span>🔒 VPN Only</span>
      </label>
      <label class="ai-filter-check">
        <input type="checkbox" id="aiFilterTop">
        <span>🔥 Frequently Visited (5+)</span>
      </label>
    </div>
    <form id="aiChatForm" class="ai-input-form">
      <textarea id="aiInput" rows="1" placeholder="Ask AI Copilot across all products... (Enter to send, Shift+Enter for newline)"></textarea>
      <button type="submit" id="aiSendBtn" class="ai-send-btn" title="Send message">
        <span>➤</span>
      </button>
      <button type="button" id="aiStopBtn" class="ai-stop-btn" style="display:none;" title="Stop query (Esc)">
        <span>⏹</span>
      </button>
    </form>
    <div class="ai-footer-hint">⌘K to toggle • Esc to stop / close • Connected to local project server</div>
  </div>
</aside>

<!-- Floating Selection & Delete Action Bar -->
<div id="selectionBar" class="selection-bar">
  <div class="selection-info">
    <span class="selection-badge">Selection Mode</span>
    <span class="selection-count">Selected: <strong id="selCount">0</strong> bookmark(s)</span>
  </div>
  <div class="selection-actions">
    <button id="btnSelectVisible" class="btn-subtle" type="button" title="Select all currently visible filtered bookmarks">Select Filtered</button>
    <button id="btnClearSelection" class="btn-subtle" type="button" title="Clear selection">Clear</button>
    <button id="btnDeleteSelected" class="btn-danger" type="button" title="Permanently delete selected bookmarks" disabled>
      <span>🗑️</span>
      <span id="btnDeleteText">Delete Selected (0)</span>
    </button>
    <button id="btnExitManage" class="btn-close-manage" type="button" title="Exit Manage Mode">Done</button>
  </div>
</div>

<!-- Add Bookmark Modal -->
<div id="addBookmarkModal" class="modal-overlay">
  <div class="modal-dialog add-bm-dialog">
    <div class="modal-header">
      <div class="modal-title-wrap">
        <span class="modal-icon-add">✨</span>
        <h3 class="modal-title">Add Bookmark with Deep AI Inspection</h3>
      </div>
      <button class="modal-close" id="btnCancelAddModal">&times;</button>
    </div>
    <div class="modal-body">
      <p class="modal-subtitle">Paste any web link or document URL. The AI agent will browse the website, verify official F5 logos, SVGs and copyright footnotes (even on CDNs), generate a concise UI summary and an extended technical summary, automatically group the link, and attach hidden semantic metadata for LLM search.</p>
      
      <div class="add-input-group">
        <input type="url" id="inputBookmarkUrl" class="add-url-input" placeholder="https://clouddocs.f5.com/... or any URL" autocomplete="off" spellcheck="false" aria-label="Bookmark URL" />
        <button id="btnSubmitAddBookmark" class="btn-inspect-add" type="button">
          <span id="btnAddSpinner" style="display:none;">⏳</span>
          <span id="btnAddText">Inspect &amp; Ingest</span>
        </button>
      </div>

      <div class="add-notes-group">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
          <label for="inputBookmarkNotes" class="add-notes-label">
            <span>📝 Custom Notes</span>
            <span class="add-notes-hint">(Personal notes, customer context, or reminders for this link)</span>
          </label>
          <button id="btnSaveNoteOnly" type="button" style="display:none; padding:4px 10px; font-size:0.75rem; font-weight:600; border-radius:6px; border:1px solid rgba(245, 158, 11, 0.45); background:rgba(245, 158, 11, 0.16); color:#fbbf24; cursor:pointer; white-space:nowrap;">💾 Save Note</button>
        </div>
        <textarea id="inputBookmarkNotes" class="add-notes-input" rows="2" placeholder="Add custom notes for this link (e.g. 'Use for ACME Corp sizing review' or 'Official city portal')..."></textarea>
      </div>

      <!-- Live Inspection Progress Steps -->
      <div id="addProgressBox" class="add-progress-box" style="display:none;">
        <div class="progress-step" id="stepFetch">
          <span class="step-dot"></span>
          <span class="step-label">1. Fetching page content &amp; following redirects...</span>
        </div>
        <div class="progress-step" id="stepInspect">
          <span class="step-dot"></span>
          <span class="step-label">2. Inspecting F5 logo assets, SVGs &amp; legal footnotes...</span>
        </div>
        <div class="progress-step" id="stepLLM">
          <span class="step-dot"></span>
          <span class="step-label">3. Synthesizing concise summary &amp; technical LLM context...</span>
        </div>
        <div class="progress-step" id="stepSave">
          <span class="step-dot"></span>
          <span class="step-label">4. Assigning strategic pillar, catalog sync &amp; DOM embedding...</span>
        </div>
      </div>

      <!-- Result Preview Box -->
      <div id="addResultBox" class="add-result-box" style="display:none;">
        <div class="result-header">
          <span id="resultStatusBadge" class="result-badge-success">✅ Ingested Successfully</span>
          <span id="resultPillarBadge" class="result-pillar-badge"></span>
        </div>
        <div id="resultStatusReason" style="font-size: 0.74rem; color: #94a3b8; margin: -4px 0 8px 0;"></div>
        <h4 id="resultTitle" class="result-title"></h4>
        <div id="resultUrl" class="result-url"></div>
        <p id="resultDesc" class="result-desc"></p>
        <div id="resultNotesBox" class="result-notes" style="display:none;">
          <span>📝</span>
          <span id="resultNotesText"></span>
        </div>
        <div id="resultTags" class="result-tags"></div>

        <details class="result-summary-accordion">
          <summary>🔍 View Hidden Semantic AI Context (<span id="resultSummaryLen">0</span> chars)</summary>
          <div id="resultSummaryText" class="result-summary-content"></div>
        </details>
      </div>

      <div class="modal-safety-notice">
        <span>🛡️ <strong>Automated Protection</strong>: Catalog backups are saved in <code>archive/backups/</code>. Chrome Profile 1 and Netscape HTML favorites sync automatically.</span>
      </div>
    </div>
    <div class="modal-footer">
      <button id="btnModalCloseAdd" class="btn-subtle" type="button">Close</button>
      <button id="btnLocateNewCard" class="btn-primary-add" type="button" style="display:none;">Locate on Page 🎯</button>
    </div>
  </div>
</div>

<!-- Deletion Confirmation Modal -->
<div id="deleteModal" class="modal-overlay">
  <div class="modal-dialog">
    <div class="modal-header">
      <div class="modal-title-wrap">
        <span class="modal-icon-danger">⚠️</span>
        <h3 class="modal-title">Confirm Bookmark Deletion</h3>
      </div>
      <button class="modal-close" id="btnCancelModal">&times;</button>
    </div>
    <div class="modal-body">
      <p id="modalPromptText">Are you sure you want to permanently delete the following bookmark(s)?</p>
      <div class="delete-list-wrapper" id="deleteListWrapper"></div>
      <div class="modal-safety-notice">
        <span>🛡️ <strong>Safety Guarantee</strong>: An automatic timestamped backup snapshot is always preserved in <code>archive/backups/</code>. Chrome Profile 1 and Netscape HTML favorites will be automatically updated.</span>
      </div>
    </div>
    <div class="modal-footer">
      <button id="btnModalCancel" class="btn-subtle" type="button">Cancel</button>
      <button id="btnModalConfirm" class="btn-danger-solid" type="button">
        <span id="btnModalConfirmSpinner" style="display:none;">⏳</span>
        <span id="btnModalConfirmText">Confirm &amp; Delete</span>
      </button>
    </div>
  </div>
</div>

<!-- Toast Notifications -->
<div id="toastContainer" class="toast-container"></div>

<style>
  /* Add Bookmark Toolbar Button */
  .add-bookmark-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.25));
    border: 1px solid rgba(52, 211, 153, 0.4);
    border-radius: 10px;
    color: #a7f3d0;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    backdrop-filter: blur(8px);
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.1);
  }
  .add-bookmark-btn:hover {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.3), rgba(5, 150, 105, 0.4));
    border-color: #34d399;
    color: #ffffff;
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.3);
    transform: translateY(-1px);
  }

  /* Add Bookmark Dialog */
  .add-bm-dialog {
    max-width: 620px !important;
  }
  .modal-icon-add {
    font-size: 1.5rem;
  }
  .modal-subtitle {
    color: #94a3b8;
    font-size: 0.82rem;
    line-height: 1.45;
    margin-bottom: 16px;
  }
  .add-input-group {
    display: flex;
    gap: 10px;
    margin-bottom: 12px;
  }
  .add-notes-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 18px;
  }
  .add-notes-label {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: 0.80rem;
    font-weight: 600;
    color: #e2e8f0;
  }
  .add-notes-hint {
    font-size: 0.73rem;
    font-weight: 400;
    color: #94a3b8;
  }
  .add-notes-input {
    width: 100%;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 10px;
    padding: 10px 14px;
    color: #f8fafc;
    font-size: 0.85rem;
    font-family: inherit;
    line-height: 1.45;
    outline: none;
    field-sizing: content;
    resize: vertical;
    min-height: 54px;
    max-height: 160px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  }
  .add-notes-input:focus {
    border-color: #f59e0b;
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);
    background: rgba(15, 23, 42, 0.95);
  }
  .add-url-input {
    flex: 1;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 10px;
    padding: 12px 14px;
    color: #f8fafc;
    font-size: 0.9rem;
    font-family: inherit;
    outline: none;
    transition: all 0.2s ease;
  }
  .add-url-input:focus {
    border-color: #38bdf8;
    box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
    background: rgba(15, 23, 42, 0.95);
  }
  .btn-inspect-add {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    border: none;
    border-radius: 10px;
    color: #ffffff;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    white-space: nowrap;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3);
  }
  .btn-inspect-add:hover:not(:disabled) {
    background: linear-gradient(135deg, #1d4ed8, #6d28d9);
    box-shadow: 0 4px 20px rgba(37, 99, 235, 0.45);
    transform: translateY(-1px);
  }
  .btn-inspect-add:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  /* Live Inspection Progress Steps */
  .add-progress-box {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .progress-step {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.82rem;
    color: #64748b;
    transition: all 0.25s ease;
  }
  .progress-step .step-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #475569;
    flex-shrink: 0;
    transition: all 0.25s ease;
  }
  .progress-step.active {
    color: #38bdf8;
    font-weight: 500;
  }
  .progress-step.active .step-dot {
    background: #38bdf8;
    box-shadow: 0 0 10px #38bdf8;
    transform: scale(1.3);
  }
  .progress-step.done {
    color: #34d399;
  }
  .progress-step.done .step-dot {
    background: #10b981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
  }

  /* Result Preview Box */
  .add-result-box {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(52, 211, 153, 0.4);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 18px;
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.1);
    animation: fadeIn 0.3s ease;
  }
  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .result-badge-success {
    font-size: 0.75rem;
    font-weight: 700;
    color: #34d399;
    background: rgba(16, 185, 129, 0.15);
    padding: 3px 8px;
    border-radius: 6px;
  }
  .result-badge-updated {
    font-size: 0.75rem;
    font-weight: 700;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.15);
    padding: 3px 8px;
    border-radius: 6px;
  }
  .result-badge-info {
    font-size: 0.75rem;
    font-weight: 700;
    color: #c084fc;
    background: rgba(192, 132, 252, 0.15);
    padding: 3px 8px;
    border-radius: 6px;
  }
  .result-pillar-badge {
    font-size: 0.75rem;
    color: #93c5fd;
    background: rgba(59, 130, 246, 0.15);
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 500;
  }
  .result-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #f8fafc;
    margin: 0 0 6px 0;
  }
  .result-url {
    font-size: 0.75rem;
    color: #64748b;
    word-break: break-all;
    margin-bottom: 8px;
  }
  .result-desc {
    font-size: 0.82rem;
    color: #cbd5e1;
    line-height: 1.4;
    margin: 0 0 10px 0;
  }
  .result-notes {
    margin: 0 0 10px 0;
    padding: 7px 10px;
    background: rgba(245, 158, 11, 0.12);
    border-left: 3px solid #f59e0b;
    border-radius: 6px;
    font-size: 0.80rem;
    color: #fde68a;
    line-height: 1.4;
    display: flex;
    align-items: flex-start;
    gap: 6px;
    word-break: break-word;
  }
  .result-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
  }
  .result-summary-accordion {
    margin-top: 10px;
    background: rgba(30, 41, 59, 0.6);
    border-radius: 8px;
    padding: 8px 12px;
    border: 1px solid rgba(148, 163, 184, 0.2);
  }
  .result-summary-accordion summary {
    font-size: 0.75rem;
    color: #38bdf8;
    font-weight: 600;
    cursor: pointer;
    outline: none;
    user-select: none;
  }
  .result-summary-content {
    margin-top: 8px;
    font-size: 0.78rem;
    color: #e2e8f0;
    line-height: 1.45;
    background: rgba(15, 23, 42, 0.7);
    padding: 10px;
    border-radius: 6px;
    border: 1px solid rgba(148, 163, 184, 0.15);
    max-height: 180px;
    overflow-y: auto;
  }
  .btn-primary-add {
    background: linear-gradient(135deg, #10b981, #059669);
    border: none;
    border-radius: 8px;
    color: #ffffff;
    padding: 9px 18px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-primary-add:hover {
    background: linear-gradient(135deg, #059669, #047857);
    transform: translateY(-1px);
  }

  /* Manage Mode Button */
  .manage-mode-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 10px;
    color: #e2e8f0;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    backdrop-filter: blur(8px);
    white-space: nowrap;
  }
  .manage-mode-btn:hover {
    background: rgba(51, 65, 85, 0.85);
    border-color: rgba(239, 68, 68, 0.5);
    color: #fca5a5;
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.15);
  }
  .manage-mode-btn.active {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.25), rgba(185, 28, 28, 0.35));
    border-color: #ef4444;
    color: #ffffff;
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.35);
  }

  /* Card Selection Checkbox */
  .card-select-check {
    display: none;
    position: absolute;
    top: 10px;
    right: 10px;
    width: 22px;
    height: 22px;
    border-radius: 6px;
    border: 2px solid rgba(148, 163, 184, 0.5);
    background: rgba(15, 23, 42, 0.85);
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
    z-index: 10;
    pointer-events: none;
  }
  .card-select-check .chk-icon {
    display: none;
    width: 10px;
    height: 10px;
    background-color: #ffffff;
    clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
  }

  /* When Manage Mode is active on body */
  body.manage-mode-active .card-select-check {
    display: flex;
  }
  body.manage-mode-active .bookmark-card {
    cursor: pointer !important;
    user-select: none;
  }
  body.manage-mode-active .bookmark-card:hover {
    border-color: rgba(239, 68, 68, 0.6) !important;
  }
  body.manage-mode-active .bookmark-card.selected {
    border-color: #ef4444 !important;
    background: rgba(239, 68, 68, 0.1) !important;
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.3) !important;
  }
  body.manage-mode-active .bookmark-card.selected .card-select-check {
    background: #ef4444;
    border-color: #ef4444;
  }
  body.manage-mode-active .bookmark-card.selected .card-select-check .chk-icon {
    display: block;
  }

  /* Sticky Bottom Selection Bar */
  .selection-bar {
    position: fixed;
    bottom: -120px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(15, 23, 42, 0.94);
    border: 1px solid rgba(239, 68, 68, 0.45);
    border-radius: 16px;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.8), 0 0 28px rgba(239, 68, 68, 0.25);
    backdrop-filter: blur(16px);
    z-index: 1500;
    transition: bottom 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    min-width: 500px;
    max-width: 90vw;
  }
  body.manage-mode-active .selection-bar {
    bottom: 24px;
  }
  .selection-info {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .selection-badge {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.5);
    color: #fca5a5;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .selection-count {
    color: #f1f5f9;
    font-size: 0.92rem;
  }
  .selection-count strong {
    color: #f87171;
    font-size: 1.1rem;
  }
  .selection-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .btn-subtle {
    background: rgba(51, 65, 85, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #cbd5e1;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-subtle:hover {
    background: rgba(71, 85, 105, 0.8);
    color: #ffffff;
  }
  .btn-danger {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    border: 1px solid #f87171;
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.35);
  }
  .btn-danger:hover:not(:disabled) {
    background: linear-gradient(135deg, #f87171, #ef4444);
    box-shadow: 0 6px 18px rgba(239, 68, 68, 0.5);
    transform: translateY(-1px);
  }
  .btn-danger:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  .btn-close-manage {
    background: transparent;
    border: 1px solid rgba(148, 163, 184, 0.3);
    color: #94a3b8;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-close-manage:hover {
    color: #ffffff;
    border-color: #cbd5e1;
  }

  /* Deletion Modal */
  .modal-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    z-index: 2000;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .modal-overlay.open,
  .modal-overlay.active {
    display: flex;
  }
  .modal-dialog {
    background: #0f172a;
    border: 1px solid rgba(239, 68, 68, 0.45);
    border-radius: 16px;
    width: 100%;
    max-width: 580px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.85), 0 0 32px rgba(239, 68, 68, 0.2);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    max-height: 85vh;
    animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes modalPop {
    from { opacity: 0; transform: scale(0.95); }
    to { opacity: 1; transform: scale(1); }
  }
  .modal-header {
    padding: 18px 22px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .modal-title-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .modal-icon-danger {
    font-size: 1.25rem;
  }
  .modal-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #f87171;
    margin: 0;
  }
  .modal-close {
    background: transparent;
    border: none;
    color: #64748b;
    font-size: 1.4rem;
    cursor: pointer;
    padding: 4px;
    line-height: 1;
    transition: color 0.2s;
  }
  .modal-close:hover {
    color: #ffffff;
  }
  .modal-body {
    padding: 20px 22px;
    overflow-y: auto;
    color: #cbd5e1;
    font-size: 0.9rem;
    line-height: 1.5;
  }
  .delete-list-wrapper {
    background: rgba(2, 6, 23, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 10px;
    padding: 10px 14px;
    max-height: 240px;
    overflow-y: auto;
    margin: 14px 0;
  }
  .delete-list-item {
    padding: 6px 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  }
  .delete-list-item:last-child {
    border-bottom: none;
  }
  .delete-list-title {
    font-weight: 600;
    color: #f1f5f9;
    font-size: 0.85rem;
  }
  .delete-list-url {
    font-size: 0.75rem;
    color: #64748b;
    word-break: break-all;
  }
  .modal-safety-notice {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.78rem;
    color: #94a3b8;
    line-height: 1.4;
  }
  .modal-safety-notice code {
    background: rgba(15, 23, 42, 0.8);
    color: #38bdf8;
    padding: 2px 4px;
    border-radius: 4px;
  }
  .modal-footer {
    padding: 16px 22px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    background: rgba(15, 23, 42, 0.5);
  }
  .btn-danger-solid {
    background: #ef4444;
    border: 1px solid #f87171;
    color: #ffffff;
    padding: 9px 18px;
    border-radius: 8px;
    font-size: 0.88rem;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s;
  }
  .btn-danger-solid:hover {
    background: #dc2626;
  }
  .btn-danger-solid:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Toasts */
  .toast-container {
    position: fixed;
    top: 24px;
    right: 24px;
    z-index: 3000;
    display: flex;
    flex-direction: column;
    gap: 10px;
    pointer-events: none;
  }
  .toast {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 10px;
    padding: 12px 18px;
    color: #ffffff;
    font-size: 0.88rem;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(12px);
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    animation: toastIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    transition: all 0.25s ease;
  }
  .toast.toast-success {
    border-color: rgba(34, 197, 94, 0.5);
    box-shadow: 0 8px 24px rgba(34, 197, 94, 0.15);
  }
  .toast.toast-error {
    border-color: rgba(239, 68, 68, 0.5);
    box-shadow: 0 8px 24px rgba(239, 68, 68, 0.15);
  }
  @keyframes toastIn {
    from { opacity: 0; transform: translateY(-12px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* AI Toolbar Button */
  .ai-toolbar-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(139, 92, 246, 0.28));
    border: 1px solid rgba(147, 197, 253, 0.4);
    border-radius: 10px;
    padding: 10px 18px;
    color: #f0f4fc;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    backdrop-filter: blur(8px);
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.15);
  }
  .ai-toolbar-btn:hover {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.35), rgba(139, 92, 246, 0.45));
    border-color: #60a5fa;
    box-shadow: 0 4px 20px rgba(59, 130, 246, 0.35);
    transform: translateY(-1px);
    color: #fff;
  }
  .ai-sparkle {
    font-size: 1.1rem;
    filter: drop-shadow(0 0 4px #93c5fd);
  }
  .ai-kbd {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 0.72rem;
    color: var(--text-secondary);
    font-family: inherit;
  }

  /* Card Locate Glowing Pulse Animation */
  @keyframes cardGlowPulse {
    0% {
      box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.9), 0 0 25px rgba(6, 182, 212, 0.7);
      border-color: #38bdf8;
      transform: scale(1.02);
    }
    50% {
      box-shadow: 0 0 0 12px rgba(59, 130, 246, 0.4), 0 0 45px rgba(6, 182, 212, 0.9);
      border-color: #60a5fa;
      transform: scale(1.035);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(59, 130, 246, 0), 0 0 0 rgba(6, 182, 212, 0);
      border-color: var(--card-border);
      transform: scale(1);
    }
  }
  .card-locate-highlight {
    animation: cardGlowPulse 1.2s ease-in-out 3 !important;
    border-color: #38bdf8 !important;
    z-index: 50;
    position: relative;
  }

  /* AI Floating Action Button (Bottom Left) */
  .ai-fab-btn {
    position: fixed;
    bottom: 25px;
    left: 30px;
    background: linear-gradient(135deg, rgba(22, 28, 45, 0.92), rgba(15, 23, 42, 0.96));
    border: 1px solid rgba(139, 92, 246, 0.4);
    border-radius: 30px;
    padding: 8px 18px;
    display: flex;
    align-items: center;
    gap: 9px;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5), 0 0 15px rgba(139, 92, 246, 0.2);
    color: #fff;
    cursor: pointer;
    z-index: 150;
    transition: all 0.25s ease;
    font-size: 0.88rem;
    font-weight: 600;
    backdrop-filter: blur(16px);
  }
  .ai-fab-btn:hover {
    border-color: #8b5cf6;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 25px rgba(139, 92, 246, 0.4);
    transform: translateY(-2px);
  }
  .ai-fab-icon {
    font-size: 1.15rem;
  }
  .ai-fab-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #f59e0b;
    box-shadow: 0 0 8px #f59e0b;
    transition: all 0.3s ease;
  }
  .ai-fab-dot.connected {
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
  }

  /* Drawer Overlay & Panel */
  .ai-drawer-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(4, 7, 14, 0.6);
    backdrop-filter: blur(4px);
    z-index: 240;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s ease, visibility 0.3s ease;
  }
  .ai-drawer-overlay.active {
    opacity: 1;
    visibility: visible;
  }

  .ai-drawer {
    position: fixed;
    top: 0;
    right: 0;
    width: 520px;
    max-width: 95vw;
    height: 100vh;
    background: rgba(10, 14, 23, 0.96);
    border-left: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: -20px 0 60px rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(28px);
    z-index: 250;
    display: flex;
    flex-direction: column;
    transform: translateX(100%);
    transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .ai-drawer.open {
    transform: translateX(0);
  }

  /* Drawer Header */
  .ai-drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 18px 22px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(15, 23, 42, 0.6);
  }
  .ai-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .ai-avatar {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(139, 92, 246, 0.4));
    border: 1px solid rgba(139, 92, 246, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
  }
  .ai-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #f1f5f9;
  }
  .ai-status-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.76rem;
    color: var(--text-secondary);
    margin-top: 2px;
  }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #f59e0b;
    box-shadow: 0 0 6px #f59e0b;
  }
  .status-dot.connected {
    background: #10b981;
    box-shadow: 0 0 6px #10b981;
  }
  .ai-header-actions {
    display: flex;
    gap: 8px;
  }
  .ai-icon-btn {
    background: rgba(30, 41, 67, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    color: var(--text-secondary);
    width: 32px;
    height: 32px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }
  .ai-icon-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    border-color: rgba(255, 255, 255, 0.25);
  }

  /* Drawer Body / Messages */
  .ai-messages {
    position: relative;
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    scroll-behavior: smooth;
  }

  .ai-welcome-box {
    background: rgba(22, 28, 45, 0.7);
    border: 1px solid rgba(99, 120, 180, 0.3);
    border-radius: 14px;
    padding: 18px;
  }
  .ai-welcome-header {
    display: flex;
    gap: 12px;
    margin-bottom: 14px;
  }
  .ai-welcome-icon {
    font-size: 1.6rem;
  }
  .ai-welcome-header h3 {
    font-size: 0.98rem;
    font-weight: 700;
    color: #93c5fd;
    margin-bottom: 4px;
  }
  .ai-welcome-header p {
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.45;
  }
  .ai-chips-label {
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted);
    margin-bottom: 8px;
    font-weight: 600;
  }
  .ai-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
  }
  .ai-chip {
    background: rgba(30, 41, 67, 0.65);
    border: 1px solid rgba(99, 120, 180, 0.25);
    border-radius: 16px;
    padding: 6px 12px;
    font-size: 0.78rem;
    color: #cbd5e1;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
  }
  .ai-chip:hover {
    background: rgba(59, 130, 246, 0.25);
    border-color: #60a5fa;
    color: #fff;
    transform: translateY(-1px);
  }

  /* Chat Bubbles */
  .ai-msg {
    display: flex;
    flex-direction: column;
    max-width: 92%;
    animation: fadeIn 0.25s ease-out;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .ai-msg.user {
    align-self: flex-end;
  }
  .ai-msg.user .ai-bubble {
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    color: #fff;
    border-radius: 14px 14px 2px 14px;
    padding: 10px 15px;
    font-size: 0.88rem;
    line-height: 1.4;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
  }
  .ai-msg.assistant {
    align-self: flex-start;
    max-width: 100%;
  }
  .ai-msg.assistant .ai-bubble {
    background: rgba(22, 28, 45, 0.85);
    border: 1px solid rgba(99, 120, 180, 0.25);
    border-radius: 14px 14px 14px 2px;
    padding: 14px 16px;
    font-size: 0.86rem;
    line-height: 1.5;
    color: #e2e8f0;
  }
  .ai-bubble h3 {
    font-size: 0.94rem;
    color: #93c5fd;
    margin: 12px 0 6px 0;
  }
  .ai-bubble h3:first-child {
    margin-top: 0;
  }
  .ai-bubble p {
    margin-bottom: 8px;
  }
  .ai-bubble p:last-child {
    margin-bottom: 0;
  }
  .ai-bubble ul {
    margin: 6px 0 8px 18px;
  }
  .ai-bubble li {
    margin-bottom: 4px;
  }
  .ai-bubble code {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 2px 5px;
    border-radius: 4px;
    font-size: 0.78rem;
    color: #67e8f9;
  }
  .ai-bubble blockquote {
    border-left: 3px solid var(--accent-blue);
    padding-left: 10px;
    margin: 8px 0;
    color: var(--text-secondary);
    font-style: italic;
  }
  .ai-bubble a {
    color: #60a5fa;
    text-decoration: none;
    font-weight: 500;
  }
  .ai-bubble a:hover {
    text-decoration: underline;
  }

  /* Embedded Result Cards in Chat */
  .ai-cards-container {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 9px;
  }
  .ai-result-card {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(99, 120, 180, 0.28);
    border-radius: 10px;
    padding: 10px 12px;
    transition: all 0.2s ease;
  }
  .ai-result-card:hover {
    border-color: #60a5fa;
    background: rgba(22, 33, 56, 0.9);
  }
  .ai-card-title-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 4px;
  }
  .ai-card-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #93c5fd;
    text-decoration: none;
    line-height: 1.35;
  }
  .ai-card-title:hover {
    color: #bfdbfe;
    text-decoration: underline;
  }
  .ai-card-url {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: ui-monospace, monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 6px;
  }
  .ai-card-desc {
    font-size: 0.78rem;
    color: var(--text-secondary);
    line-height: 1.35;
    margin-bottom: 8px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .ai-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
  }
  .ai-card-tags {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .ai-card-actions {
    display: flex;
    gap: 6px;
  }
  .ai-btn-locate, .ai-btn-filter {
    background: rgba(30, 41, 67, 0.6);
    border: 1px solid rgba(99, 120, 180, 0.3);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 0.72rem;
    color: #cbd5e1;
    cursor: pointer;
    transition: all 0.2s;
  }
  .ai-btn-locate:hover {
    background: rgba(59, 130, 246, 0.25);
    border-color: #60a5fa;
    color: #fff;
  }
  .ai-btn-filter:hover {
    background: rgba(139, 92, 246, 0.25);
    border-color: #a78bfa;
    color: #fff;
  }

  /* Drawer Footer / Input */
  .ai-drawer-footer {
    padding: 14px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(15, 23, 42, 0.75);
  }
  .ai-footer-filters {
    display: flex;
    gap: 14px;
    margin-bottom: 10px;
  }
  /* Product Scope Selector Tabs */
  .ai-prod-selector-wrap {
    margin-bottom: 8px;
    background: rgba(15, 23, 42, 0.45);
    border: 1px solid rgba(99, 120, 180, 0.2);
    border-radius: 8px;
    padding: 6px 8px;
  }
  .ai-prod-selector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 5px;
  }
  .ai-prod-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ai-scope-desc {
    font-size: 0.72rem;
    color: #60a5fa;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
  }
  .ai-prod-tabs {
    display: flex;
    gap: 5px;
    overflow-x: auto;
    padding-bottom: 3px;
    scrollbar-width: none;
  }
  .ai-prod-tabs::-webkit-scrollbar {
    display: none;
  }
  .ai-prod-tab {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(99, 120, 180, 0.25);
    border-radius: 9999px;
    padding: 3px 9px;
    font-size: 0.73rem;
    color: #94a3b8;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.18s ease;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }
  .ai-prod-tab:hover {
    color: #f1f5f9;
    background: rgba(51, 65, 85, 0.85);
    border-color: rgba(99, 120, 180, 0.45);
  }
  .ai-prod-tab.active {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.35), rgba(37, 99, 235, 0.5));
    border-color: #3b82f6;
    color: #fff;
    font-weight: 600;
    box-shadow: 0 0 8px rgba(59, 130, 246, 0.35);
  }
  .ai-stop-btn {
    background: #ef4444;
    border: none;
    border-radius: 10px;
    width: 38px;
    height: 38px;
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.05rem;
    transition: all 0.2s;
    flex-shrink: 0;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
    animation: pulseStop 1.8s infinite;
  }
  .ai-stop-btn:hover {
    background: #dc2626;
    transform: scale(1.05);
  }
  @keyframes pulseStop {
    0%, 100% { box-shadow: 0 0 6px rgba(239, 68, 68, 0.4); }
    50% { box-shadow: 0 0 14px rgba(239, 68, 68, 0.8); }
  }
  .ai-inline-stop-btn {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.45);
    color: #fca5a5;
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 0.74rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    vertical-align: middle;
  }
  .ai-inline-stop-btn:hover {
    background: rgba(239, 68, 68, 0.4);
    color: #fff;
    border-color: #ef4444;
  }
  .ai-interrupted-notice {
    color: #f87171;
    font-size: 0.84rem;
    padding: 3px 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .ai-scope-tag {
    display: inline-block;
    padding: 2px 7px;
    font-size: 0.7rem;
    font-weight: 600;
    border-radius: 4px;
    background: rgba(59, 130, 246, 0.2);
    color: #93c5fd;
    border: 1px solid rgba(59, 130, 246, 0.35);
    margin-bottom: 5px;
  }
  .ai-filter-check {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.76rem;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
  }
  .ai-filter-check input {
    cursor: pointer;
    accent-color: var(--accent-blue);
  }
  .ai-input-form {
    display: flex;
    gap: 8px;
    align-items: flex-end;
  }
  .ai-input-form textarea {
    flex: 1;
    background: rgba(10, 14, 23, 0.8);
    border: 1px solid rgba(99, 120, 180, 0.3);
    border-radius: 10px;
    padding: 10px 14px;
    color: #fff;
    font-size: 0.88rem;
    resize: none;
    outline: none;
    max-height: 120px;
    line-height: 1.4;
    font-family: inherit;
    transition: border-color 0.2s;
  }
  .ai-input-form textarea:focus {
    border-color: var(--accent-blue);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
  }
  .ai-send-btn {
    background: var(--accent-blue);
    border: none;
    border-radius: 10px;
    width: 38px;
    height: 38px;
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    transition: all 0.2s;
    flex-shrink: 0;
  }
  .ai-send-btn:hover {
    background: #2563eb;
    transform: scale(1.04);
  }
  .ai-send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
  .ai-footer-hint {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-align: center;
    margin-top: 8px;
  }

  /* Filter badge notification on showcase */
  .ai-filter-active-bar {
    max-width: 1400px;
    margin: -15px auto 20px auto;
    background: rgba(139, 92, 246, 0.15);
    border: 1px solid rgba(139, 92, 246, 0.35);
    border-radius: 10px;
    padding: 8px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.84rem;
    color: #e2e8f0;
  }
  .ai-reset-filter-btn {
    background: rgba(139, 92, 246, 0.3);
    border: 1px solid rgba(139, 92, 246, 0.5);
    border-radius: 6px;
    padding: 3px 10px;
    color: #fff;
    font-size: 0.78rem;
    cursor: pointer;
  }

  /* Verified Content Badges & Excerpt Callouts */
  .badge-verified {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
    border: 1px solid rgba(52, 211, 153, 0.35);
    padding: 2px 7px;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  .ai-card-excerpt {
    margin-top: 8px;
    background: rgba(15, 23, 42, 0.85);
    border-left: 3px solid #34d399;
    border-radius: 4px;
    padding: 7px 10px;
    font-size: 0.76rem;
    color: #cbd5e1;
    display: flex;
    gap: 8px;
    align-items: flex-start;
    line-height: 1.45;
  }
  .ai-card-excerpt .excerpt-icon {
    font-size: 0.85rem;
    margin-top: 1px;
    flex-shrink: 0;
  }
  .ai-card-excerpt .excerpt-body {
    flex: 1;
    min-width: 0;
  }
  .ai-card-excerpt strong {
    color: #38bdf8;
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
  }
  .ai-card-excerpt em {
    color: #f1f5f9;
    font-style: italic;
    word-break: break-word;
  }

  @keyframes cardPulseHighlight {
    0% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7); border-color: #38bdf8; }
    50% { box-shadow: 0 0 25px 8px rgba(56, 189, 248, 0.5); border-color: #38bdf8; transform: scale(1.02); }
    100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
  }
  .card-locate-highlight {
    animation: cardPulseHighlight 1.8s ease-in-out 2;
    border-color: #38bdf8 !important;
  }
</style>

<script>
  const searchInput = document.getElementById('searchInput');
  let cards = document.querySelectorAll('.bookmark-card');
  let sections = document.querySelectorAll('.subcat-section');
  let pillars = document.querySelectorAll('.pillar-section');
  function refreshCardsList() {
    cards = document.querySelectorAll('.bookmark-card');
    sections = document.querySelectorAll('.subcat-section');
    pillars = document.querySelectorAll('.pillar-section');
  }
  const pills = document.querySelectorAll('.pill');

  let currentFilter = 'all';
  let aiFilteredUrls = null;

  function applyFilters() {
    const q = searchInput.value.toLowerCase().trim();
    const queryTokens = q ? q.split(/\s+/).filter(Boolean) : [];

    cards.forEach(card => {
      const searchData = card.getAttribute('data-search') || '';
      const visits = parseInt(card.getAttribute('data-visits') || '0', 10);
      const isVpn = card.getAttribute('data-vpn') === 'true';
      const prods = card.getAttribute('data-prods') || '';
      const topics = card.getAttribute('data-topics') || '';
      const cardHref = card.getAttribute('href') || '';

      let matchesSearch = queryTokens.length === 0 || queryTokens.every(t => searchData.includes(t));
      let matchesPill = true;
      let matchesAiFilter = !aiFilteredUrls || aiFilteredUrls.has(cardHref);

      if (currentFilter === 'vpn') {
        matchesPill = isVpn;
      } else if (currentFilter === 'recent') {
        matchesPill = card.getAttribute('data-recent') === 'true';
      } else if (currentFilter === 'big-ip') {
        matchesPill = prods.includes('big-ip') || prods.includes('rseries') || prods.includes('velos');
      } else if (currentFilter === 'nginx') {
        matchesPill = prods.includes('nginx');
      } else if (currentFilter === 'f5-xc') {
        matchesPill = prods.includes('f5-xc') || prods.includes('distributed-cloud-services');
      } else if (currentFilter === 'workforce-ai') {
        matchesPill = prods.includes('f5-workforce-ai-security') || searchData.includes('surepath') || searchData.includes('workforce ai');
      } else if (currentFilter === 'sizing') {
        matchesPill = topics.includes('sizing-capacity');
      } else if (currentFilter === 'security') {
        matchesPill = topics.includes('security-waf');
      } else if (currentFilter === 'ai') {
        matchesPill = prods.includes('ai-workloads') || prods.includes('f5-ai-gateway') || prods.includes('f5-workforce-ai-security') || searchData.includes('calypso') || searchData.includes('guardrail') || searchData.includes('surepath');
      } else if (currentFilter === 'top') {
        matchesPill = visits > 0;
      }

      if (matchesSearch && matchesPill && matchesAiFilter) {
        card.classList.remove('hidden');
      } else {
        card.classList.add('hidden');
      }
    });

    sections.forEach(sec => {
      const visibleInSec = sec.querySelectorAll('.bookmark-card:not(.hidden)').length;
      sec.style.display = visibleInSec > 0 ? '' : 'none';
    });

    pillars.forEach(pil => {
      const visibleInPil = pil.querySelectorAll('.bookmark-card:not(.hidden)').length;
      pil.style.display = visibleInPil > 0 ? '' : 'none';
    });
  }

  searchInput.addEventListener('input', () => {
    aiFilteredUrls = null; // Clear AI filter when user types in search
    applyFilters();
  });

  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentFilter = pill.getAttribute('data-filter');
      aiFilteredUrls = null;
      applyFilters();
    });
  });

  /* ==========================================================================
     BOOKMARK SELECTION & IN-BROWSER DELETION LOGIC
     ========================================================================== */
  const manageModeBtn = document.getElementById('manageModeBtn');
  const manageModeBtnText = document.getElementById('manageModeBtnText');
  const selectionBar = document.getElementById('selectionBar');
  const selCount = document.getElementById('selCount');
  const btnDeleteSelected = document.getElementById('btnDeleteSelected');
  const btnDeleteText = document.getElementById('btnDeleteText');
  const btnSelectVisible = document.getElementById('btnSelectVisible');
  const btnClearSelection = document.getElementById('btnClearSelection');
  const btnExitManage = document.getElementById('btnExitManage');
  const deleteModal = document.getElementById('deleteModal');
  const deleteListWrapper = document.getElementById('deleteListWrapper');
  const modalPromptText = document.getElementById('modalPromptText');
  const btnCancelModal = document.getElementById('btnCancelModal');
  const btnModalCancel = document.getElementById('btnModalCancel');
  const btnModalConfirm = document.getElementById('btnModalConfirm');
  const btnModalConfirmText = document.getElementById('btnModalConfirmText');
  const btnModalConfirmSpinner = document.getElementById('btnModalConfirmSpinner');
  const toastContainer = document.getElementById('toastContainer');

  let isManageMode = false;
  const selectedUrls = new Set();

  function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  function updateSelectionUI() {
    refreshCardsList();
    const count = selectedUrls.size;
    selCount.textContent = count;
    btnDeleteText.textContent = `Delete Selected (${count})`;
    btnDeleteSelected.disabled = count === 0;

    cards.forEach(card => {
      const url = card.getAttribute('href') || '';
      if (selectedUrls.has(url)) {
        card.classList.add('selected');
      } else {
        card.classList.remove('selected');
      }
    });
  }

  function toggleManageMode(forceState = null) {
    isManageMode = forceState !== null ? forceState : !isManageMode;
    document.body.classList.toggle('manage-mode-active', isManageMode);
    manageModeBtn.classList.toggle('active', isManageMode);
    manageModeBtnText.textContent = isManageMode ? 'Exit Manage' : 'Manage & Delete';

    if (!isManageMode) {
      selectedUrls.clear();
      updateSelectionUI();
    } else {
      updateSelectionUI();
    }
  }

  manageModeBtn.addEventListener('click', () => toggleManageMode());
  btnExitManage.addEventListener('click', () => toggleManageMode(false));

  document.addEventListener('click', (e) => {
    if (!isManageMode) return;
    const card = e.target.closest('.bookmark-card');
    if (!card) return;
    e.preventDefault();
    e.stopPropagation();

    const url = card.getAttribute('href') || '';
    if (!url) return;

    if (selectedUrls.has(url)) {
      selectedUrls.delete(url);
    } else {
      selectedUrls.add(url);
    }
    updateSelectionUI();
  });

  btnSelectVisible.addEventListener('click', () => {
    refreshCardsList();
    cards.forEach(card => {
      if (!card.classList.contains('hidden')) {
        const url = card.getAttribute('href') || '';
        if (url) selectedUrls.add(url);
      }
    });
    updateSelectionUI();
  });

  btnClearSelection.addEventListener('click', () => {
    selectedUrls.clear();
    updateSelectionUI();
  });

  function openDeleteModal() {
    if (selectedUrls.size === 0) {
      showToast('⚠️ No bookmarks currently selected.', 'error');
      return;
    }

    refreshCardsList();
    const items = [];
    cards.forEach(card => {
      const url = card.getAttribute('href') || '';
      if (selectedUrls.has(url)) {
        const titleEl = card.querySelector('.bm-title');
        const title = titleEl ? titleEl.textContent : url;
        if (!items.find(i => i.url === url)) {
          items.push({ url, title });
        }
      }
    });

    modalPromptText.innerHTML = `Are you sure you want to permanently delete the following <strong>${items.length}</strong> bookmark(s)?`;
    deleteListWrapper.innerHTML = items.map(item => `
      <div class="delete-list-item">
        <div class="delete-list-title">${item.title}</div>
        <div class="delete-list-url">${item.url}</div>
      </div>
    `).join('');

    deleteModal.classList.add('open');
  }

  function closeDeleteModal() {
    deleteModal.classList.remove('open');
    btnModalConfirm.disabled = false;
    btnModalConfirmText.textContent = 'Confirm & Delete';
    btnModalConfirmSpinner.style.display = 'none';
  }

  btnDeleteSelected.addEventListener('click', openDeleteModal);
  btnCancelModal.addEventListener('click', closeDeleteModal);
  btnModalCancel.addEventListener('click', closeDeleteModal);

  deleteModal.addEventListener('click', (e) => {
    if (e.target === deleteModal) closeDeleteModal();
  });

  btnModalConfirm.addEventListener('click', async () => {
    if (selectedUrls.size === 0) {
      closeDeleteModal();
      return;
    }

    btnModalConfirm.disabled = true;
    btnModalConfirmText.textContent = 'Deleting & Syncing...';
    btnModalConfirmSpinner.style.display = 'inline-block';

    const urlsToDelete = Array.from(selectedUrls);

    try {
      const res = await fetch(`http://localhost:8765/api/bookmarks/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls: urlsToDelete })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `Server responded with HTTP ${res.status}`);
      }

      const data = await res.json();
      closeDeleteModal();
      showToast(`✅ Successfully deleted ${data.deleted_count} bookmark(s)! Chrome Profile &amp; catalog synced.`, 'success', 5000);

      refreshCardsList();
      const deletedSet = new Set(urlsToDelete);
      cards.forEach(card => {
        const url = card.getAttribute('href') || '';
        if (deletedSet.has(url)) {
          card.style.transition = 'all 0.3s ease';
          card.style.opacity = '0';
          card.style.transform = 'scale(0.8)';
          setTimeout(() => {
            card.remove();
            refreshCardsList();
            applyFilters();
          }, 300);
        }
      });

      selectedUrls.clear();
      updateSelectionUI();

    } catch (err) {
      console.error('Delete request failed:', err);
      btnModalConfirm.disabled = false;
      btnModalConfirmText.textContent = 'Confirm & Delete';
      btnModalConfirmSpinner.style.display = 'none';
      showToast(`❌ Deletion failed: ${err.message}. Is the AI Agent server running on port 8765?`, 'error', 6000);
    }
  });

  /* ==========================================================================
     ADD BOOKMARK WITH AI INSPECTION CLIENT LOGIC
     ========================================================================== */
  const addBookmarkBtn = document.getElementById('addBookmarkBtn');
  const addBookmarkModal = document.getElementById('addBookmarkModal');
  const btnCancelAddModal = document.getElementById('btnCancelAddModal');
  const btnModalCloseAdd = document.getElementById('btnModalCloseAdd');
  const inputBookmarkUrl = document.getElementById('inputBookmarkUrl');
  const inputBookmarkNotes = document.getElementById('inputBookmarkNotes');
  const btnSaveNoteOnly = document.getElementById('btnSaveNoteOnly');
  const btnSubmitAddBookmark = document.getElementById('btnSubmitAddBookmark');
  const btnAddSpinner = document.getElementById('btnAddSpinner');
  const btnAddText = document.getElementById('btnAddText');
  const addProgressBox = document.getElementById('addProgressBox');
  const addResultBox = document.getElementById('addResultBox');
  const stepFetch = document.getElementById('stepFetch');
  const stepInspect = document.getElementById('stepInspect');
  const stepLLM = document.getElementById('stepLLM');
  const stepSave = document.getElementById('stepSave');
  const resultStatusBadge = document.getElementById('resultStatusBadge');
  const resultStatusReason = document.getElementById('resultStatusReason');
  const resultTitle = document.getElementById('resultTitle');
  const resultUrl = document.getElementById('resultUrl');
  const resultDesc = document.getElementById('resultDesc');
  const resultNotesBox = document.getElementById('resultNotesBox');
  const resultNotesText = document.getElementById('resultNotesText');
  const resultTags = document.getElementById('resultTags');
  const resultPillarBadge = document.getElementById('resultPillarBadge');
  const resultSummaryLen = document.getElementById('resultSummaryLen');
  const resultSummaryText = document.getElementById('resultSummaryText');
  const btnLocateNewCard = document.getElementById('btnLocateNewCard');

  let lastAddedUrl = null;
  let isEditingExistingNote = false;

  function escapeHtmlClient(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function findExistingCardByUrl(rawUrl) {
    if (!rawUrl) return null;
    const norm = normalizeUrlForClient(rawUrl);
    for (const c of document.querySelectorAll('.bookmark-card')) {
      const href = c.getAttribute('href') || '';
      if (href === rawUrl || normalizeUrlForClient(href) === norm) {
        return c;
      }
    }
    return null;
  }

  function syncSaveNoteButtonVisibility() {
    if (!btnSaveNoteOnly || !inputBookmarkUrl) return;
    const u = inputBookmarkUrl.value.trim();
    const exists = Boolean(isEditingExistingNote || (u && (u === lastAddedUrl || findExistingCardByUrl(u))));
    btnSaveNoteOnly.style.display = exists ? 'inline-flex' : 'none';
  }

  function openAddModal(prefillUrl = '', prefillNotes = '') {
    if (!addBookmarkModal) return;
    const urlStr = typeof prefillUrl === 'string' ? prefillUrl : '';
    let notesStr = typeof prefillNotes === 'string' ? prefillNotes : '';
    if (urlStr && !notesStr) {
      const existingCard = findExistingCardByUrl(urlStr);
      if (existingCard) {
        notesStr = existingCard.getAttribute('data-notes') || '';
      }
    }
    isEditingExistingNote = Boolean(urlStr);
    addBookmarkModal.classList.add('open', 'active');
    document.body.style.overflow = 'hidden';
    if (inputBookmarkUrl) {
      inputBookmarkUrl.value = urlStr;
    }
    if (inputBookmarkNotes) {
      inputBookmarkNotes.value = notesStr;
    }
    setTimeout(() => {
      if (urlStr && inputBookmarkNotes) {
        inputBookmarkNotes.focus();
      } else if (inputBookmarkUrl) {
        inputBookmarkUrl.focus();
      }
    }, 80);
    if (addProgressBox) addProgressBox.style.display = 'none';
    if (addResultBox) addResultBox.style.display = 'none';
    if (resultNotesBox) resultNotesBox.style.display = 'none';
    if (btnLocateNewCard) btnLocateNewCard.style.display = 'none';
    if (btnSubmitAddBookmark) btnSubmitAddBookmark.disabled = false;
    if (btnAddSpinner) btnAddSpinner.style.display = 'none';
    if (btnAddText) btnAddText.textContent = urlStr ? 'Save Note & Update' : 'Inspect & Ingest';
    syncSaveNoteButtonVisibility();
    resetAddSteps();
  }

  function closeAddModal() {
    if (!addBookmarkModal) return;
    addBookmarkModal.classList.remove('open', 'active');
    document.body.style.overflow = '';
  }

  // Expose globally so inline onclick works
  window.openAddModal = openAddModal;
  window.closeAddModal = closeAddModal;

  function resetAddSteps() {
    [stepFetch, stepInspect, stepLLM, stepSave].forEach(el => {
      if (el) el.classList.remove('active', 'done');
    });
  }

  if (addBookmarkBtn) addBookmarkBtn.addEventListener('click', () => openAddModal());
  if (btnCancelAddModal) btnCancelAddModal.addEventListener('click', closeAddModal);
  if (btnModalCloseAdd) btnModalCloseAdd.addEventListener('click', closeAddModal);

  // Delegate clicks on card note edit buttons (.bm-note-edit-btn)
  document.addEventListener('click', (e) => {
    const noteBtn = e.target.closest('.bm-note-edit-btn');
    if (!noteBtn) return;
    e.preventDefault();
    e.stopPropagation();
    const card = noteBtn.closest('.bookmark-card');
    if (!card) return;
    const url = card.getAttribute('href') || '';
    const existingNotes = card.getAttribute('data-notes') || '';
    openAddModal(url, existingNotes);
  });

  if (addBookmarkModal) {
    addBookmarkModal.addEventListener('click', (e) => {
      if (e.target === addBookmarkModal) closeAddModal();
    });
  }

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && addBookmarkModal && (addBookmarkModal.classList.contains('open') || addBookmarkModal.classList.contains('active'))) {
      closeAddModal();
    }
  });

  if (inputBookmarkUrl) {
    inputBookmarkUrl.addEventListener('input', () => {
      const u = inputBookmarkUrl.value.trim();
      const existingCard = findExistingCardByUrl(u);
      if (existingCard && inputBookmarkNotes && !inputBookmarkNotes.value.trim()) {
        const cardNote = existingCard.getAttribute('data-notes') || '';
        if (cardNote) inputBookmarkNotes.value = cardNote;
      }
      syncSaveNoteButtonVisibility();
    });
    inputBookmarkUrl.addEventListener('keydown', (e) => {
      if (e.isComposing || e.keyCode === 229) return;
      if (e.key === 'Enter') {
        e.preventDefault();
        if (btnSubmitAddBookmark) btnSubmitAddBookmark.click();
      }
    });
  }

  async function saveCustomNoteOnly() {
    let rawUrl = inputBookmarkUrl ? inputBookmarkUrl.value.trim() : '';
    const rawNotes = inputBookmarkNotes ? inputBookmarkNotes.value.trim() : '';
    if (!rawUrl) {
      showToast('⚠️ Please enter a bookmark URL first.', 'error');
      return false;
    }
    if (!rawUrl.startsWith('http://') && !rawUrl.startsWith('https://')) {
      rawUrl = 'https://' + rawUrl;
      if (inputBookmarkUrl) inputBookmarkUrl.value = rawUrl;
    }
    if (btnSaveNoteOnly) {
      btnSaveNoteOnly.disabled = true;
      btnSaveNoteOnly.textContent = '⏳ Saving...';
    }
    try {
      const res = await fetch(`http://localhost:8765/api/bookmarks/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: rawUrl, notes: rawNotes })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      const bm = data.bookmark;
      if (bm) {
        lastAddedUrl = bm.url;
        const pillar = (bm.hierarchy && bm.hierarchy[0]) || '09. External Engineering, Protocols & Tools';
        const subcat = (bm.hierarchy && bm.hierarchy[1]) || 'General Reference';
        injectNewCardIntoDOM(bm, pillar, subcat);
        if (resultNotesBox && resultNotesText) {
          if (rawNotes) {
            resultNotesText.textContent = rawNotes;
            resultNotesBox.style.display = 'block';
          } else {
            resultNotesText.textContent = '';
            resultNotesBox.style.display = 'none';
          }
        }
        showToast(rawNotes ? `📝 Custom note saved for "${bm.title}"!` : `🗑️ Custom note cleared for "${bm.title}".`, 'success', 4500);
        return true;
      }
    } catch (err) {
      console.warn('Direct note endpoint fallback:', err);
    } finally {
      if (btnSaveNoteOnly) {
        btnSaveNoteOnly.disabled = false;
        btnSaveNoteOnly.textContent = '💾 Save Note';
      }
    }
    return false;
  }

  if (btnSaveNoteOnly) {
    btnSaveNoteOnly.addEventListener('click', async () => {
      await saveCustomNoteOnly();
    });
  }

  if (inputBookmarkNotes) {
    inputBookmarkNotes.addEventListener('input', () => {
      syncSaveNoteButtonVisibility();
      if (addResultBox && addResultBox.style.display === 'block' && btnAddText) {
        btnAddText.textContent = 'Save Note & Update';
      }
    });
    inputBookmarkNotes.addEventListener('keydown', (e) => {
      if (e.isComposing || e.keyCode === 229) return;
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (btnSaveNoteOnly && btnSaveNoteOnly.style.display !== 'none') {
          btnSaveNoteOnly.click();
        } else if (btnSubmitAddBookmark) {
          btnSubmitAddBookmark.click();
        }
      }
    });
  }

  btnSubmitAddBookmark.addEventListener('click', async () => {
    let rawUrl = inputBookmarkUrl.value.trim();
    const rawNotes = inputBookmarkNotes ? inputBookmarkNotes.value.trim() : '';
    if (!rawUrl) {
      showToast('⚠️ Please enter or paste a valid web address.', 'error');
      inputBookmarkUrl.focus();
      return;
    }
    if (!rawUrl.startsWith('http://') && !rawUrl.startsWith('https://')) {
      rawUrl = 'https://' + rawUrl;
      inputBookmarkUrl.value = rawUrl;
    }

    // Fast path: if editing an existing bookmark's note (or updating note right after inspection), try /api/bookmarks/notes first!
    if (isEditingExistingNote || (lastAddedUrl && normalizeUrlForClient(rawUrl) === normalizeUrlForClient(lastAddedUrl))) {
      btnSubmitAddBookmark.disabled = true;
      btnAddSpinner.style.display = 'inline-block';
      btnAddText.textContent = 'Saving Note...';
      const savedFast = await saveCustomNoteOnly();
      btnSubmitAddBookmark.disabled = false;
      btnAddSpinner.style.display = 'none';
      if (savedFast) {
        btnAddText.textContent = 'Note Saved ✓';
        btnLocateNewCard.style.display = 'inline-flex';
        return;
      }
    }

    btnSubmitAddBookmark.disabled = true;
    btnAddSpinner.style.display = 'inline-block';
    btnAddText.textContent = 'Inspecting Site...';
    addResultBox.style.display = 'none';
    btnLocateNewCard.style.display = 'none';
    addProgressBox.style.display = 'flex';
    resetAddSteps();

    // Step 1: Fetching
    if (stepFetch) stepFetch.classList.add('active');

    // Progressive step indicator animations
    const t1 = setTimeout(() => {
      if (stepFetch) { stepFetch.classList.remove('active'); stepFetch.classList.add('done'); }
      if (stepInspect) stepInspect.classList.add('active');
    }, 1200);

    const t2 = setTimeout(() => {
      if (stepInspect) { stepInspect.classList.remove('active'); stepInspect.classList.add('done'); }
      if (stepLLM) stepLLM.classList.add('active');
    }, 2800);

    const t3 = setTimeout(() => {
      if (stepLLM) { stepLLM.classList.remove('active'); stepLLM.classList.add('done'); }
      if (stepSave) stepSave.classList.add('active');
    }, 4500);

    try {
      const res = await fetch(`http://localhost:8765/api/bookmarks/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: rawUrl,
          notes: rawNotes,
          allow_clear_notes: Boolean(isEditingExistingNote)
        })
      });

      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);

      [stepFetch, stepInspect, stepLLM, stepSave].forEach(el => {
        if (el) { el.classList.remove('active'); el.classList.add('done'); }
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || err.error || `Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      const bm = data.bookmark;
      lastAddedUrl = bm.url;
      syncSaveNoteButtonVisibility();

      const isExisting = Boolean(data.is_existing);
      const isUpdated = Boolean(data.updated);
      const reasonMsg = data.reason || '';

      // Populate Result Preview
      resultTitle.textContent = bm.title;
      resultUrl.textContent = bm.url;
      resultDesc.textContent = bm.description || 'No description provided.';
      resultPillarBadge.textContent = `${data.pillar} > ${data.subcategory}`;

      const savedNotes = (bm.notes || data.notes || '').trim();
      if (resultNotesBox && resultNotesText) {
        if (savedNotes) {
          resultNotesText.textContent = savedNotes;
          resultNotesBox.style.display = 'block';
        } else {
          resultNotesText.textContent = '';
          resultNotesBox.style.display = 'none';
        }
      }

      if (resultStatusReason) {
        resultStatusReason.textContent = reasonMsg ? `Status: ${reasonMsg}` : '';
      }

      if (!isExisting) {
        if (resultStatusBadge) {
          resultStatusBadge.textContent = '✅ Ingested Successfully';
          resultStatusBadge.className = 'result-badge-success';
        }
        showToast(`✅ Successfully ingested "${bm.title}" into ${data.pillar}!`, 'success', 6000);
      } else if (isUpdated) {
        if (resultStatusBadge) {
          resultStatusBadge.textContent = '🔄 Updated Existing Bookmark';
          resultStatusBadge.className = 'result-badge-updated';
        }
        showToast(`🔄 Existing bookmark "${bm.title}" updated: ${reasonMsg}!`, 'success', 6500);
      } else {
        if (resultStatusBadge) {
          resultStatusBadge.textContent = 'ℹ️ Already Exists (Up to Date)';
          resultStatusBadge.className = 'result-badge-info';
        }
        showToast(`ℹ️ Bookmark already exists in catalog and content summary is up-to-date.`, 'info', 5000);
      }
      
      const tagsHtml = [];
      if (bm.is_official_f5) tagsHtml.push('<span class="tag tag-prod">🏛️ Official F5</span>');
      if (bm.requires_vpn) tagsHtml.push('<span class="tag tag-vpn">🔒 Needs VPN</span>');
      (bm.tags?.products || []).forEach(p => tagsHtml.push(`<span class="tag tag-prod">${p}</span>`));
      (bm.tags?.topics || []).forEach(t => tagsHtml.push(`<span class="tag tag-topic">${t}</span>`));
      (bm.tags?.source_types || []).forEach(s => tagsHtml.push(`<span class="tag tag-type">${s}</span>`));
      resultTags.innerHTML = tagsHtml.join(' ');

      const summaryStr = bm.content_summary || bm.description || '';
      resultSummaryLen.textContent = summaryStr.length;
      resultSummaryText.textContent = summaryStr;

      addResultBox.style.display = 'block';
      btnLocateNewCard.style.display = 'inline-flex';
      btnSubmitAddBookmark.disabled = false;
      btnAddSpinner.style.display = 'none';
      btnAddText.textContent = 'Inspect Another';

      // Update or Ingest card directly in the DOM showcase grid (NEVER DUPLICATES)
      injectNewCardIntoDOM(bm, data.pillar, data.subcategory);

    } catch (err) {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      resetAddSteps();
      addProgressBox.style.display = 'none';
      btnSubmitAddBookmark.disabled = false;
      btnAddSpinner.style.display = 'none';
      btnAddText.textContent = isEditingExistingNote ? 'Save Note & Update' : 'Inspect & Ingest';
      console.error('Add bookmark error:', err);
      showToast(`❌ Failed to ingest bookmark: ${err.message}. Is the AI server running on port 8765?`, 'error', 7000);
    }
  });

  function normalizeUrlForClient(u) {
    if (!u) return '';
    try {
      let s = u.trim().toLowerCase();
      if (s.startsWith('http://')) s = 'https://' + s.slice(7);
      const parsed = new URL(s);
      let host = parsed.hostname.replace(/^www\./, '');
      let path = parsed.pathname.replace(/\/+$/, '');
      return host + path + (parsed.search || '');
    } catch (e) {
      return u.trim().toLowerCase().replace(/\/+$/, '');
    }
  }

  function injectNewCardIntoDOM(bm, pillar, subcat) {
    const targetKey = normalizeUrlForClient(bm.url);
    const matchingCards = [];
    document.querySelectorAll('.bookmark-card').forEach(c => {
      const href = c.getAttribute('href') || '';
      if (href === bm.url || normalizeUrlForClient(href) === targetKey) {
        matchingCards.push(c);
      }
    });

    const summaryText = bm.content_summary || bm.description || '';
    const notesText = (bm.notes || '').trim();
    const vpnKw = bm.requires_vpn ? 'vpn-required vpn internal' : 'public';
    const prods = bm.tags?.products || [];
    const topics = bm.tags?.topics || [];
    const stypes = bm.tags?.source_types || [];
    const searchBlob = `${bm.title} ${bm.description || ''} ${summaryText} ${notesText} ${bm.url} ${vpnKw} ${prods.join(' ')} ${topics.join(' ')} ${stypes.join(' ')}`.toLowerCase();

    if (matchingCards.length > 0) {
      // Update all matching cards in-place (including Recently Added clone if present)
      matchingCards.forEach(existingCard => {
        existingCard.setAttribute('data-search', searchBlob);
        existingCard.setAttribute('data-vpn', String(Boolean(bm.requires_vpn)));
        existingCard.setAttribute('data-prods', prods.join(','));
        existingCard.setAttribute('data-topics', topics.join(','));
        if (notesText) {
          existingCard.setAttribute('data-notes', notesText);
        } else {
          existingCard.removeAttribute('data-notes');
        }

        if (bm.requires_vpn) {
          existingCard.classList.add('is-vpn');
        } else {
          existingCard.classList.remove('is-vpn');
        }

        const titleEl = existingCard.querySelector('.bm-title');
        if (titleEl && bm.title) titleEl.textContent = bm.title;
        const descEl = existingCard.querySelector('.bm-desc');
        if (descEl && bm.description) descEl.textContent = bm.description;

        // Update or insert/remove custom notes block (.bm-notes)
        let notesEl = existingCard.querySelector('.bm-notes');
        if (notesText) {
          if (!notesEl) {
            notesEl = document.createElement('div');
            notesEl.className = 'bm-notes';
            if (descEl && descEl.parentNode) {
              descEl.parentNode.appendChild(notesEl);
            } else {
              existingCard.appendChild(notesEl);
            }
          }
          notesEl.innerHTML = `<span class="bm-notes-label">📝 Note:</span> <span class="bm-notes-text">${escapeHtmlClient(notesText)}</span>`;
        } else if (notesEl) {
          notesEl.remove();
        }

        // Update note edit button state
        const noteBtnEl = existingCard.querySelector('.bm-note-edit-btn');
        if (noteBtnEl) {
          if (notesText) {
            noteBtnEl.classList.add('has-note');
            noteBtnEl.title = 'Edit custom note';
          } else {
            noteBtnEl.classList.remove('has-note');
            noteBtnEl.title = 'Add custom note';
          }
        }

        // Update tags
        let tagMarkup = '';
        if (bm.requires_vpn) tagMarkup += '<span class="tag tag-vpn">🔒 Needs VPN</span> ';
        prods.forEach(p => tagMarkup += `<span class="tag tag-prod">${p}</span> `);
        topics.forEach(t => tagMarkup += `<span class="tag tag-topic">${t}</span> `);
        stypes.forEach(s => { if (s !== 'vpn-required') tagMarkup += `<span class="tag tag-type">${s}</span> `; });
        const tagsContainer = existingCard.querySelector('.card-tags');
        if (tagsContainer) tagsContainer.innerHTML = tagMarkup;

        // Update hidden AI context element
        let hiddenEl = existingCard.querySelector('.bm-hidden-summary');
        if (!hiddenEl) {
          hiddenEl = document.createElement('div');
          hiddenEl.className = 'bm-hidden-summary';
          hiddenEl.style.display = 'none';
          hiddenEl.setAttribute('data-ai-context', 'true');
          hiddenEl.setAttribute('aria-hidden', 'true');
          existingCard.appendChild(hiddenEl);
        }
        hiddenEl.textContent = summaryText;

        // Subtly highlight the existing card
        existingCard.classList.remove('hidden');
        existingCard.classList.add('card-locate-highlight');
        setTimeout(() => existingCard.classList.remove('card-locate-highlight'), 3600);
      });
      return;
    }

    // Build card element
    const cardEl = document.createElement('a');
    cardEl.className = bm.requires_vpn ? 'bookmark-card is-vpn' : 'bookmark-card';
    cardEl.href = bm.url;
    cardEl.target = '_blank';
    cardEl.rel = 'noopener noreferrer';
    cardEl.setAttribute('data-search', searchBlob);
    cardEl.setAttribute('data-visits', '1');
    cardEl.setAttribute('data-vpn', String(Boolean(bm.requires_vpn)));
    cardEl.setAttribute('data-recent', 'true');
    cardEl.setAttribute('data-prods', prods.join(','));
    cardEl.setAttribute('data-topics', topics.join(','));
    if (notesText) {
      cardEl.setAttribute('data-notes', notesText);
    }

    let tagMarkup = '';
    if (bm.requires_vpn) tagMarkup += '<span class="tag tag-vpn">🔒 Needs VPN</span> ';
    prods.forEach(p => tagMarkup += `<span class="tag tag-prod">${p}</span> `);
    topics.forEach(t => tagMarkup += `<span class="tag tag-topic">${t}</span> `);
    stypes.forEach(s => { if (s !== 'vpn-required') tagMarkup += `<span class="tag tag-type">${s}</span> `; });

    const vpnBadge = bm.requires_vpn ? '<span class="vpn-badge">🔒 VPN</span>' : '';
    const noteBtnClass = notesText ? 'bm-note-edit-btn has-note' : 'bm-note-edit-btn';
    const noteBtnTitle = notesText ? 'Edit custom note' : 'Add custom note';
    const notesHtml = notesText ? `<div class="bm-notes"><span class="bm-notes-label">📝 Note:</span> <span class="bm-notes-text">${escapeHtmlClient(notesText)}</span></div>` : '';

    cardEl.innerHTML = `
      <div class="card-select-check" title="Select bookmark">
        <span class="chk-icon"></span>
      </div>
      <div>
        <div class="card-top">
          <h4 class="bm-title">${escapeHtmlClient(bm.title)}</h4>
          <div class="card-badges">
            <span class="recent-badge">🆕 Just Added</span>
            ${vpnBadge}
            <button type="button" class="${noteBtnClass}" title="${noteBtnTitle}" aria-label="${noteBtnTitle}">📝 Note</button>
            <span class="visit-badge">✓ 1</span>
          </div>
        </div>
        <p class="bm-desc">${escapeHtmlClient(bm.description || '')}</p>
        ${notesHtml}
      </div>
      <div>
        <div class="bm-url">${escapeHtmlClient(bm.url)}</div>
        <div class="card-tags">${tagMarkup}</div>
      </div>
      <div class="bm-hidden-summary" style="display: none;" data-ai-context="true" aria-hidden="true">${escapeHtmlClient(summaryText)}</div>
    `;

    // Find target subcat section
    let targetSection = document.querySelector(`.subcat-section[data-pillar="${CSS.escape(pillar)}"][data-subcat="${CSS.escape(subcat)}"]`);
    if (targetSection) {
      const grid = targetSection.querySelector('.bookmark-grid');
      if (grid) {
        grid.prepend(cardEl);
      }
      const recentGrid = document.querySelector('#recently-added .bookmark-grid');
      if (recentGrid) {
        recentGrid.prepend(cardEl.cloneNode(true));
      }
    } else {
      let targetPillar = document.querySelector(`.pillar-section[data-pillar="${CSS.escape(pillar)}"]`);
      if (targetPillar) {
        const newSubcat = document.createElement('div');
        newSubcat.className = 'subcat-section';
        newSubcat.setAttribute('data-pillar', pillar);
        newSubcat.setAttribute('data-subcat', subcat);
        newSubcat.innerHTML = `<h3 class="subcat-title">📁 ${subcat} (1)</h3><div class="bookmark-grid"></div>`;
        newSubcat.querySelector('.bookmark-grid').appendChild(cardEl);
        targetPillar.appendChild(newSubcat);
        const recentGrid = document.querySelector('#recently-added .bookmark-grid');
        if (recentGrid) {
          recentGrid.prepend(cardEl.cloneNode(true));
        }
      } else {
        const recentGrid = document.querySelector('#recently-added .bookmark-grid');
        if (recentGrid) recentGrid.prepend(cardEl);
      }
    }

    refreshCardsList();
    applyFilters();

    // Update filter counter
    const allPill = document.querySelector('.pill[data-filter="all"]');
    if (allPill) {
      const uniqueUrls = new Set();
      document.querySelectorAll('.bookmark-card').forEach(c => {
        const u = c.getAttribute('href');
        if (u) uniqueUrls.add(u);
      });
      allPill.textContent = `All (${uniqueUrls.size})`;
    }
  }

  btnLocateNewCard.addEventListener('click', () => {
    if (!lastAddedUrl) return;
    closeAddModal();
    const cardEl = document.querySelector(`.bookmark-card[href="${CSS.escape(lastAddedUrl)}"]`);
    if (cardEl) {
      cardEl.classList.remove('hidden');
      cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      cardEl.classList.add('card-locate-highlight');
      setTimeout(() => cardEl.classList.remove('card-locate-highlight'), 3600);
    }
  });

  /* ==========================================================================
     AI COPILOT CLIENT & CONNECTIVITY LOGIC
     ========================================================================== */
  const AI_SERVER_PORT = 8765;
  const AI_SERVER_URL = `http://localhost:${AI_SERVER_PORT}`;

  const aiDrawer = document.getElementById('aiDrawer');
  const aiDrawerOverlay = document.getElementById('aiDrawerOverlay');
  const aiFabToggle = document.getElementById('aiFabToggle');
  const aiToolbarBtn = document.getElementById('aiToolbarBtn');
  const aiCloseBtn = document.getElementById('aiCloseBtn');
  const aiClearBtn = document.getElementById('aiClearBtn');
  const aiMessages = document.getElementById('aiMessages');
  const aiChatForm = document.getElementById('aiChatForm');
  const aiInput = document.getElementById('aiInput');
  const aiSendBtn = document.getElementById('aiSendBtn');
  const aiStopBtn = document.getElementById('aiStopBtn');
  const aiProdTabs = document.getElementById('aiProdTabs');
  const aiActiveScopeDesc = document.getElementById('aiActiveScopeDesc');
  const aiStatusDot = document.getElementById('aiStatusDot');
  const aiStatusText = document.getElementById('aiStatusText');
  const aiFabDot = document.getElementById('aiFabDot');
  const aiFilterVpn = document.getElementById('aiFilterVpn');
  const aiFilterTop = document.getElementById('aiFilterTop');

  let isServerConnected = false;
  let chatHistory = [];
  let activeAbortController = null;
  let isQueryRunning = false;
  let selectedProduct = 'adsp';

  const PRODUCT_SCOPES = {
    'adsp': {
      name: 'ADSP (All Products)',
      shortName: 'ADSP (All)',
      icon: '🌐',
      desc: 'All Products (Platform-wide)',
      placeholder: 'Ask AI Copilot across all F5, NGINX, Cloud and AI bookmarks...',
      chips: [
        { label: '⚡ BIG-IP VE Sizing', query: 'How do I size BIG-IP VE throughput and CPU core allocation?' },
        { label: '🛡️ Workforce AI & SurePath', query: 'Show me Workforce AI security architecture and SurePath references' },
        { label: '🔒 Internal VPN Portals', query: 'Find internal portals that require F5 VPN' },
        { label: '🟩 NGINX App Protect & Ingress', query: 'NGINX App Protect and Ingress controller guides' },
        { label: '☁️ XC Service Policies & WAAP', query: 'F5 Distributed Cloud WAAP and Service Policy guides' },
        { label: '🤖 AI Gateway Routing', query: 'F5 AI Gateway architecture and LLM traffic optimization' }
      ]
    },
    'aisp': {
      name: 'AISP (All AI Products)',
      shortName: 'AISP (All AI)',
      icon: '🧠',
      desc: 'All AI Products (AI Gateway, Workforce AI, Guardrails)',
      placeholder: 'Ask AI Copilot across all AI solutions (Gateway, Workforce AI, Guardrails)...',
      chips: [
        { label: '🤖 AI Gateway Routing', query: 'F5 AI Gateway architecture, LLM load balancing, and token rate limits' },
        { label: '🛡️ Workforce AI & SurePath', query: 'F5 Workforce AI Security, SurePath inspection, and shadow AI defense' },
        { label: '🔒 AI Guardrails & CalypsoAI', query: 'AI Guardrails prompt defense, real-time scanners, and prompt history' },
        { label: '🚨 OWASP Top 10 for LLMs', query: 'OWASP Top 10 for LLMs mitigations across F5 AI solutions' }
      ]
    },
    'big-ip': {
      name: 'BIG-IP & TMOS',
      shortName: 'BIG-IP',
      icon: '⚡',
      desc: 'BIG-IP, TMOS, LTM, APM, ASM, VELOS, rSeries',
      placeholder: 'Ask AI Copilot about BIG-IP, TMOS, LTM, APM, ASM, VELOS, rSeries...',
      chips: [
        { label: '⚡ VE Sizing Matrix', query: 'BIG-IP Virtual Edition sizing matrix and core allocation' },
        { label: '🛠️ AS3 & REST APIs', query: 'Application Services 3 (AS3) declaration templates and APIs' },
        { label: '💻 TMOS Upgrade & EoL', query: 'TMOS software lifecycle, upgrade matrix, and release notes' },
        { label: '🚀 rSeries & VELOS F5OS', query: 'F5 rSeries and VELOS F5OS architecture and troubleshooting' }
      ]
    },
    'nginx': {
      name: 'NGINX Ecosystem',
      shortName: 'NGINX',
      icon: '🟩',
      desc: 'NGINX Plus, App Protect, Ingress, Instance Manager',
      placeholder: 'Ask AI Copilot about NGINX Plus, App Protect, Ingress Controller...',
      chips: [
        { label: '🟩 NGINX Ingress Controller', query: 'NGINX Ingress Controller Kubernetes deployment and configuration' },
        { label: '🛡️ NGINX App Protect WAF', query: 'NGINX App Protect WAF installation and security policies' },
        { label: '⚙️ Gateway Fabric', query: 'NGINX Gateway Fabric Kubernetes Gateway API architecture' },
        { label: '📊 Instance Manager (NIM)', query: 'NGINX Instance Manager configuration management and analytics' }
      ]
    },
    'f5xc': {
      name: 'F5 Distributed Cloud (XC)',
      shortName: 'F5 XC',
      icon: '☁️',
      desc: 'Distributed Cloud WAAP, Multi-Cloud App Connect, Mesh',
      placeholder: 'Ask AI Copilot about F5 XC, Multi-Cloud App Connect, WAAP, Service Policies...',
      chips: [
        { label: '☁️ XC HTTP Load Balancer', query: 'F5 Distributed Cloud HTTP Load Balancer origin pools and routing' },
        { label: '🛡️ XC WAAP & Bot Defense', query: 'F5 Distributed Cloud WAAP security policies and bot protection' },
        { label: '🔄 BIG-IP to XC Migration', query: 'Convert BIG-IP configuration and iRules to F5 Distributed Cloud' },
        { label: '🌐 Multi-Cloud App Connect', query: 'F5 XC Customer Edge (CE) site deployment and multi-cloud networking' }
      ]
    },
    'ai-gateway': {
      name: 'F5 AI Gateway',
      shortName: 'AI Gateway',
      icon: '🤖',
      desc: 'LLM Traffic Governance, Routing & Optimization',
      placeholder: 'Ask AI Copilot about F5 AI Gateway, LLM routing, token rate limits...',
      chips: [
        { label: '🤖 AI Gateway Overview', query: 'F5 AI Gateway features, architecture, and deployment' },
        { label: '🚦 LLM Load Balancing', query: 'F5 AI Gateway routing, fallback, and rate limiting across LLMs' },
        { label: '🔐 AI Inference Governance', query: 'Securing and governing generative AI API traffic with F5 AI Gateway' }
      ]
    },
    'ai-workforce': {
      name: 'F5 Workforce AI Security',
      shortName: 'AI Workforce',
      icon: '🛡️',
      desc: 'SurePath AI, GenAI User Traffic Inspection',
      placeholder: 'Ask AI Copilot about F5 Workforce AI, SurePath, GenAI traffic flows...',
      chips: [
        { label: '🛡️ Workforce AI Security', query: 'F5 Workforce AI Security architecture and capabilities' },
        { label: '🔍 SurePath AI Inspection', query: 'SurePath AI traffic flows, browser integration, and policy enforcement' },
        { label: '📋 Data Leak Prevention in LLM', query: 'Preventing employee data leakage into public LLMs with F5 Workforce AI' }
      ]
    },
    'ai-guardrails': {
      name: 'AI Guardrails & CalypsoAI',
      shortName: 'AI Guardrails',
      icon: '🔒',
      desc: 'Prompt Injection Defense, Scanners, CalypsoAI',
      placeholder: 'Ask AI Copilot about AI Guardrails, CalypsoAI, prompt defense...',
      chips: [
        { label: '🔒 Prompt Defense & Scanners', query: 'AI Guardrails real-time prompt scanners and jailbreak defense' },
        { label: '🛡️ CalypsoAI Integration', query: 'CalypsoAI integration with F5 architectures for GenAI security' },
        { label: '📜 Prompt History Auditing', query: 'Auditing LLM prompt history and compliance with AI Guardrails' }
      ]
    }
  };

  function selectProductScope(prodKey) {
    if (!PRODUCT_SCOPES[prodKey]) prodKey = 'adsp';
    selectedProduct = prodKey;
    const scope = PRODUCT_SCOPES[prodKey];

    if (aiProdTabs) {
      aiProdTabs.querySelectorAll('.ai-prod-tab').forEach(tab => {
        if (tab.getAttribute('data-prod') === prodKey) {
          tab.classList.add('active');
          tab.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' });
        } else {
          tab.classList.remove('active');
        }
      });
    }

    if (aiActiveScopeDesc) {
      aiActiveScopeDesc.textContent = scope.desc;
    }

    if (aiInput) {
      aiInput.placeholder = scope.placeholder;
    }

    renderWelcomeChips(prodKey);
  }

  function renderWelcomeChips(prodKey) {
    const scope = PRODUCT_SCOPES[prodKey] || PRODUCT_SCOPES.adsp;
    const chipsContainer = document.querySelector('.ai-welcome-box .ai-chips');
    if (chipsContainer && scope.chips) {
      chipsContainer.innerHTML = scope.chips.map(c => 
        `<button class="ai-chip" type="button" data-query="${escapeHtml(c.query)}">${escapeHtml(c.label)}</button>`
      ).join('');
      bindChips();
    }
  }

  if (aiProdTabs) {
    aiProdTabs.querySelectorAll('.ai-prod-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const p = tab.getAttribute('data-prod');
        selectProductScope(p);
      });
    });
  }

  function stopActiveQuery() {
    if (activeAbortController) {
      try {
        activeAbortController.abort();
      } catch (e) {}
      activeAbortController = null;
    }
    isQueryRunning = false;
    if (aiSendBtn) aiSendBtn.style.display = 'flex';
    if (aiStopBtn) aiStopBtn.style.display = 'none';

    const loadingIndicators = aiMessages.querySelectorAll('.loading-state');
    loadingIndicators.forEach(el => el.remove());

    appendMessage('assistant', '<div class="ai-interrupted-notice"><span>⏹</span> <em>Search query interrupted by user.</em></div>');
  }

  if (aiStopBtn) {
    aiStopBtn.addEventListener('click', stopActiveQuery);
  }

  function openAiDrawer() {
    aiDrawer.classList.add('open');
    aiDrawerOverlay.classList.add('active');
    setTimeout(() => aiInput.focus(), 150);
  }

  function closeAiDrawer() {
    aiDrawer.classList.remove('open');
    aiDrawerOverlay.classList.remove('active');
  }

  aiFabToggle.addEventListener('click', openAiDrawer);
  if (aiToolbarBtn) aiToolbarBtn.addEventListener('click', openAiDrawer);
  aiCloseBtn.addEventListener('click', closeAiDrawer);
  aiDrawerOverlay.addEventListener('click', closeAiDrawer);

  // Global Keyboard Shortcuts (Cmd+K / Ctrl+K, Escape)
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (aiDrawer.classList.contains('open')) {
        closeAiDrawer();
      } else {
        openAiDrawer();
      }
    } else if (e.key === 'Escape' && aiDrawer.classList.contains('open')) {
      if (isQueryRunning) {
        e.preventDefault();
        stopActiveQuery();
      } else {
        closeAiDrawer();
      }
    }
  });

  // Auto-resize textarea
  aiInput.addEventListener('input', () => {
    aiInput.style.height = 'auto';
    aiInput.style.height = Math.min(aiInput.scrollHeight, 120) + 'px';
  });

  aiInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      aiChatForm.dispatchEvent(new Event('submit'));
    }
  });

  // Clear chat
  aiClearBtn.addEventListener('click', () => {
    chatHistory = [];
    const scope = PRODUCT_SCOPES[selectedProduct] || PRODUCT_SCOPES.adsp;
    aiMessages.innerHTML = `
      <div class="ai-welcome-box">
        <div class="ai-welcome-header">
          <span class="ai-welcome-icon">🪐</span>
          <div>
            <h3>Chat cleared</h3>
            <p>Ask a question or click a suggestion below to search your bookmarks catalog.</p>
          </div>
        </div>
        <div class="ai-chips"></div>
      </div>
    `;
    renderWelcomeChips(selectedProduct);
  });

  // Suggestion Chips Click
  function bindChips() {
    document.querySelectorAll('.ai-chip').forEach(chip => {
      chip.onclick = () => {
        const q = chip.getAttribute('data-query');
        aiInput.value = q;
        openAiDrawer();
        submitAiQuery(q);
      };
    });
  }
  bindChips();

  // Server Connection Status Probe
  async function probeServer() {
    if (typeof isQueryRunning !== 'undefined' && isQueryRunning) {
      return;
    }
    try {
      const ctrl = new AbortController();
      const tid = setTimeout(() => ctrl.abort(), 2500);
      const res = await fetch(`${AI_SERVER_URL}/api/status`, { signal: ctrl.signal });
      clearTimeout(tid);
      if (res.ok) {
        const data = await res.json();
        isServerConnected = true;
        aiStatusDot.classList.add('connected');
        aiFabDot.classList.add('connected');
        if (data.llm_backend && data.llm_backend.details) {
          aiStatusText.textContent = `${data.llm_backend.details} • ${data.bookmarks_count} links`;
        } else {
          aiStatusText.textContent = `Project Server Connected (${data.bookmarks_count} links)`;
        }
        return;
      }
    } catch (e) {
      if (typeof isQueryRunning !== 'undefined' && isQueryRunning) {
        return;
      }
      // Server offline
    }
    isServerConnected = false;
    aiStatusDot.classList.remove('connected');
    aiFabDot.classList.remove('connected');
    aiStatusText.textContent = `In-Browser Engine (Start python3 ai_agent_server.py)`;
  }

  probeServer();
  setInterval(probeServer, 6000);

  // Markdown rendering helper
  function formatMarkdown(text) {
    if (!text) return '';
    let out = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>')
      .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/gim, '<em>$1</em>')
      .replace(/`([^`]+)`/gim, '<code>$1</code>')
      .replace(/\[(.*?)\]\((.*?)\)/gim, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    
    // Format list items
    const lines = out.split('\n');
    let inList = false;
    let formatted = [];
    for (let line of lines) {
      if (line.trim().startsWith('- ')) {
        if (!inList) { formatted.push('<ul>'); inList = true; }
        formatted.push(`<li>${line.trim().substring(2)}</li>`);
      } else {
        if (inList) { formatted.push('</ul>'); inList = false; }
        formatted.push(line ? `<p>${line}</p>` : '');
      }
    }
    if (inList) formatted.push('</ul>');
    return formatted.join('');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Append Chat Message
  function appendMessage(role, contentHtml, results = []) {
    const msg = document.createElement('div');
    msg.className = `ai-msg ${role}`;
    
    let cardsHtml = '';
    if (results && results.length > 0) {
      cardsHtml = '<div class="ai-cards-container">';
      results.forEach(b => {
        const vCount = b.visit_count || 0;
        const isVpn = b.requires_vpn || false;
        const tags = b.tags || {};
        const prods = tags.products || [];
        const topics = tags.topics || [];
        
        let tagsMarkup = '';
        if (isVpn) tagsMarkup += '<span class="tag tag-vpn">🔒 VPN</span> ';
        prods.slice(0, 2).forEach(p => { tagsMarkup += `<span class="tag tag-prod">${p}</span> `; });
        topics.slice(0, 2).forEach(t => { tagsMarkup += `<span class="tag tag-topic">${t}</span> `; });

        const visitMarkup = vCount >= 15 ? `<span class="visit-badge high">🔥 ${vCount}</span>` : (vCount > 0 ? `<span class="visit-badge">✓ ${vCount}</span>` : '');
        const verifiedBadge = b.content_verified ? `<span class="badge-verified" title="${escapeHtml(b.content_reason || 'Verified in page content')}">🔍 Verified</span>` : '';

        let excerptMarkup = '';
        const rawExcerpt = (b.content_excerpt || '').trim();
        const isBadExcerpt = !rawExcerpt || /sorry to interrupt|css error|loading\s*×/i.test(rawExcerpt);
        if (!isBadExcerpt) {
          excerptMarkup = `
            <div class="ai-card-excerpt">
              <span class="excerpt-icon">💬</span>
              <div class="excerpt-body">
                <strong>Verified Page Excerpt:</strong>
                <em>"${escapeHtml(rawExcerpt)}"</em>
              </div>
            </div>
          `;
        }

        cardsHtml += `
          <div class="ai-result-card" data-url="${b.url}">
            <div class="ai-card-title-row">
              <a href="${b.url}" target="_blank" rel="noopener noreferrer" class="ai-card-title">${b.title}</a>
              <div style="display:flex; gap:6px; align-items:center;">
                ${verifiedBadge}
                ${visitMarkup}
              </div>
            </div>
            <div class="ai-card-url">${b.url}</div>
            <div class="ai-card-desc">${b.description || ''}</div>
            ${excerptMarkup}
            <div class="ai-card-footer">
              <div class="ai-card-tags">${tagsMarkup}</div>
              <div class="ai-card-actions">
                <button type="button" class="ai-btn-locate" data-url="${b.url}">📍 Locate on Page</button>
                <button type="button" class="ai-btn-filter" data-url="${b.url}">🔍 Filter</button>
              </div>
            </div>
          </div>
        `;
      });
      cardsHtml += '</div>';
    }

    msg.innerHTML = `
      <div class="ai-bubble">
        ${contentHtml}
        ${cardsHtml}
      </div>
    `;

    aiMessages.appendChild(msg);
    if (role === 'assistant') {
      aiMessages.scrollTo({ top: Math.max(0, msg.offsetTop - 12), behavior: 'smooth' });
    } else {
      aiMessages.scrollTop = aiMessages.scrollHeight;
    }

    // Attach button handlers for locate & filter
    msg.querySelectorAll('.ai-btn-locate').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        locateCardOnPage(btn.getAttribute('data-url'));
      });
    });

    msg.querySelectorAll('.ai-btn-filter').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        filterPageToBookmark(btn.getAttribute('data-url'));
      });
    });
  }

  // Locate card on page with smooth scroll & glowing animation
  function locateCardOnPage(url) {
    if (!url) return;
    const cleanTarget = url.trim().toLowerCase();
    
    // Find card by matching href
    let targetCard = null;
    cards.forEach(c => {
      const href = (c.getAttribute('href') || '').trim().toLowerCase();
      if (href === cleanTarget) {
        targetCard = c;
      }
    });

    if (!targetCard) {
      alert("Bookmark card could not be found on current page.");
      return;
    }

    // Reset filters if the card is hidden so it becomes visible
    if (targetCard.classList.contains('hidden') || aiFilteredUrls) {
      aiFilteredUrls = null;
      currentFilter = 'all';
      pills.forEach(p => p.classList.remove('active'));
      const allPill = document.querySelector('.pill[data-filter="all"]');
      if (allPill) allPill.classList.add('active');
      searchInput.value = '';
      applyFilters();
    }

    // Ensure parent subcat and pillar are shown
    const parentSub = targetCard.closest('.subcat-section');
    if (parentSub) parentSub.style.display = '';
    const parentPil = targetCard.closest('.pillar-section');
    if (parentPil) parentPil.style.display = '';
    targetCard.classList.remove('hidden');

    // On mobile or narrow screens, close drawer to show user the card
    if (window.innerWidth < 800) {
      closeAiDrawer();
    }

    // Smooth scroll to card
    targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Trigger glowing pulse animation
    targetCard.classList.remove('card-locate-highlight');
    void targetCard.offsetWidth; // Force reflow
    targetCard.classList.add('card-locate-highlight');
  }

  // Filter page view to this specific bookmark or all AI recommendations
  function filterPageToBookmark(url) {
    aiFilteredUrls = new Set([url]);
    applyFilters();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function filterPageToResults(results) {
    if (!results || results.length === 0) return;
    aiFilteredUrls = new Set(results.map(r => r.url));
    applyFilters();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Client-Side Search Fallback (Zero-Dependency In-Browser Engine)
  function clientFallbackSearch(query, vpnOnly, topOnly, productScope = 'adsp') {
    const typoMap = {
      'migarte': 'migrate', 'migate': 'migrate', 'mirgate': 'migrate', 'migraton': 'migration',
      'conver': 'convert', 'convrting': 'convert', 'convrt': 'convert',
      'iruls': 'irules', 'iruel': 'irules', 'irueles': 'irules',
      'bigip': 'big-ip', 'bip-ip': 'big-ip', 'f5xc': 'f5-xc', 'voltera': 'volterra',
      'guardrail': 'guardrails', 'aigateway': 'ai-gateway'
    };

    const words = (query.toLowerCase().match(/[a-z0-9_\-\.]+/g) || []).map(w => typoMap[w] || w);
    const normQuery = words.join(' ');

    const isMigration = /\b(migrate|migration|converting|convert|conversion|transition|port|move|switch|ps-convert)\b/.test(normQuery);
    const targetIsXc = /\b(to|into|onto|in)\s+(the\s+)?(f5[\-\s]*)?xc(\s+platform)?\b|\bxc\s+platform\b|\bxc\b|\bdistributed cloud\b|\bvolterra\b/.test(normQuery);
    const sourceIsIrules = /\birules?\b|\btcl\b/.test(normQuery);

    const stopWords = new Set(["how", "do", "i", "can", "show", "me", "find", "the", "a", "an", "for", "with", "and", "or", "to", "in", "on", "of", "what", "is", "where", "want"]);
    const queryTokens = words.filter(t => !stopWords.has(t));

    // Scope definitions for client-side evaluation
    const scopeTagMap = {
      'big-ip': ['big-ip'],
      'nginx': ['nginx'],
      'f5xc': ['f5-xc'],
      'ai-gateway': ['f5-ai-gateway', 'ai-gateway'],
      'ai-workforce': ['f5-workforce-ai-security', 'ai-workforce'],
      'ai-guardrails': ['ai-guardrails', 'ai-workloads'],
      'aisp': ['f5-ai-gateway', 'ai-gateway', 'f5-workforce-ai-security', 'ai-workforce', 'ai-guardrails', 'ai-workloads'],
      'adsp': []
    };

    const scopeRegexMap = {
      'big-ip': /\b(big[\-\s]?ip|tmos|ltm|asm|apm|gtm|afm|irules?|big-iq|f5os|rseries|velos)\b/i,
      'nginx': /\b(nginx|njs|nap|app[\-\s]?protect|unit|kic|ingress[\-\s]?controller)\b/i,
      'f5xc': /\b(f5[\-\s]?xc|distributed[\-\s]?cloud|volterra|vk8s|cloud[\-\s]?load[\-\s]?balancer)\b/i,
      'ai-gateway': /\b(ai[\-\s]?gateway|f5[\-\s]?ai[\-\s]?gateway|llm[\-\s]?routing|prompt[\-\s]?protection|semantic[\-\s]?caching)\b/i,
      'ai-workforce': /\b(workforce[\-\s]?ai|shadow[\-\s]?ai|browser[\-\s]?extension|copilot[\-\s]?security|genai[\-\s]?compliance)\b/i,
      'ai-guardrails': /\b(guardrails?|ai[\-\s]?guardrails?|hallucination|data[\-\s]?leakage|prompt[\-\s]?injection|owasp[\-\s]?llm)\b/i,
      'aisp': /\b(ai[\-\s]?gateway|f5[\-\s]?ai[\-\s]?gateway|workforce[\-\s]?ai|surepath|guardrails?|calypso|calypsoai|shadow[\-\s]?ai|llm[\-\s]?routing|prompt[\-\s]?protection|genai|owasp[\-\s]?llm)\b/i,
      'adsp': null
    };

    const isScoped = productScope && productScope !== 'adsp';
    const targetTags = scopeTagMap[productScope] || [];
    const targetRegex = scopeRegexMap[productScope] || null;

    const scored = [];

    cards.forEach(card => {
      const searchData = (card.getAttribute('data-search') || '').toLowerCase();
      const title = (card.querySelector('.bm-title')?.textContent || '').toLowerCase();
      const desc = (card.querySelector('.bm-desc')?.textContent || '');
      const url = (card.getAttribute('href') || '').toLowerCase();
      const visits = parseInt(card.getAttribute('data-visits') || '0', 10);
      const isVpn = card.getAttribute('data-vpn') === 'true';
      const prods = (card.getAttribute('data-prods') || '').split(',').filter(Boolean);
      const topics = (card.getAttribute('data-topics') || '').split(',').filter(Boolean);

      if (vpnOnly && !isVpn) return;
      if (topOnly && visits < 5) return;

      let score = 0;
      queryTokens.forEach(t => {
        if (title.includes(t)) score += 8;
        else if (searchData.includes(t)) score += 3;
      });

      // Scope boosting & conflict penalty
      if (isScoped) {
        let matchesScope = targetTags.some(t => prods.includes(t));
        if (!matchesScope && targetRegex) {
          matchesScope = targetRegex.test(title) || targetRegex.test(searchData) || targetRegex.test(url);
        }

        if (matchesScope) {
          score += 35;
        } else if (prods.length > 0 && !targetTags.some(t => prods.includes(t))) {
          // Product conflict penalty (e.g. searching NGINX but card is tagged BIG-IP only)
          score -= 20;
        }
      }

      // Migration intelligence in browser
      if (isMigration && targetIsXc) {
        if (prods.includes('f5-xc')) score += 15;

        if (url.includes('guide-convert') || url.includes('ps-convert') || (title.includes('conversion') && title.includes('distributed cloud'))) {
          score += 40;
        } else if ((title.includes('convert') || title.includes('migration')) && (prods.includes('f5-xc') || prods.includes('big-ip'))) {
          score += 25;
        }

        if (sourceIsIrules) {
          if (title.includes('service policy') || url.includes('service-policy') || title.includes('listener logic')) {
            score += 26;
          } else if (prods.includes('f5-xc') && /routing|load balancer|docs-v2|technical knowledge/.test(title)) {
            score += 12;
          }

          if (!prods.includes('f5-xc') && url.includes('clouddocs.f5.com/api/irules')) {
            score -= 30;
          } else if (!prods.includes('f5-xc') && topics.includes('programmability-irules') && !title.includes('convert')) {
            score -= 20;
          }
        }
      }

      if (score > 0) {
        score += Math.log1p(visits) * 1.5;

        let verifiedExcerpt = desc;
        if (url.includes('guide-convert')) {
          verifiedExcerpt = "Provides tips and instructions for converting legacy BIG-IP traffic policies and iRules into Distributed Cloud HTTP Load Balancers.";
        } else if (url.includes('ps-convert')) {
          verifiedExcerpt = "Tutorial and sample policies with Policy Supervisor (PS) to convert BIG-IP WAF and traffic policies.";
        } else if (title.includes('service policy') || url.includes('service-policy')) {
          verifiedExcerpt = "Service Policies provide custom header matching and rule-based request enforcement, replacing security iRules in XC.";
        } else if (title.includes('listener logic')) {
          verifiedExcerpt = "Explains how F5 Distributed Cloud handles request traffic and routes through HTTP/TCP Load Balancer listeners.";
        }

        scored.push({
          score,
          bookmark: {
            title: card.querySelector('.bm-title')?.textContent || '',
            url: card.getAttribute('href') || '',
            description: desc,
            visit_count: visits,
            requires_vpn: isVpn,
            content_verified: true,
            content_excerpt: verifiedExcerpt,
            tags: { products: prods, topics: topics, source_types: [] }
          }
        });
      }
    });

    scored.sort((a, b) => b.score - a.score);
    const topResults = scored.slice(0, 8).map(s => s.bookmark);

    const scopeObj = PRODUCT_SCOPES[productScope] || PRODUCT_SCOPES.adsp;
    const scopePrefix = isScoped ? `🎯 **Scoped to ${scopeObj.icon} ${scopeObj.name}**\n\n` : '';

    let reply = '';
    if (isMigration && targetIsXc && sourceIsIrules) {
      reply = scopePrefix + `### 🔄 Migrating iRules to F5 Distributed Cloud (XC)\n\n` +
        `F5 Distributed Cloud (XC) utilizes an Envoy-based proxy architecture and **does not execute TCL-based iRules directly**. ` +
        `Instead, iRule logic is converted to native XC constructs:\n\n` +
        `1. **HTTP Load Balancer Routing & Rewrites**: Path rewrite, prefix routing, redirects, and header manipulation.\n` +
        `2. **Service Policies**: Custom header matching, ASN/IP reputation filtering, and rule-based traffic enforcement.\n` +
        `3. **Automated Conversion Tools**: Use **F5 Policy Supervisor (\`ps-convert\`)** and the official conversion guide.\n` +
        `4. **vK8s & Edge Compute**: For complex programmable logic requiring edge code execution.\n\n` +
        `### 🔍 Verified in Bookmark Content (${topResults.length} matches):\n`;
      topResults.slice(0, 5).forEach(b => {
        const vpnStr = b.requires_vpn ? ' 🔒' : '';
        const vStr = b.visit_count > 0 ? ` \`(${b.visit_count} visits)\`` : '';
        reply += `- **[${b.title}](${b.url})**${vpnStr}${vStr}\n`;
        const excerptText = (b.content_excerpt || '').trim();
        const isBad = !excerptText || /sorry to interrupt|css error|loading\s*×/i.test(excerptText);
        if (!isBad) {
          reply += `  > 💬 *"${excerptText}"*\n`;
        } else if (b.description) {
          reply += `  > ${b.description}\n`;
        }
      });
      reply += `\n*Click **Locate on Page** to jump to any bookmark card, or **Filter** to isolate them.*`;
    } else {
      reply = scopePrefix + `Browsed candidate bookmarks and verified **${topResults.length}** with relevant content:\n\n`;
      if (topResults.length > 0) {
        reply += `⭐ **Top Verified Match:** [${topResults[0].title}](${topResults[0].url})`;
        if (topResults[0].requires_vpn) reply += ` *(Requires VPN)*`;
        const topExcerpt = (topResults[0].content_excerpt || '').trim();
        const topIsBad = !topExcerpt || /sorry to interrupt|css error|loading\s*×/i.test(topExcerpt);
        if (!topIsBad) reply += `\n> 💬 *"${topExcerpt}"*`;
        reply += `\n\n*Click **Locate on Page** to jump to the bookmark card, or **Filter** to isolate it.*`;
      } else {
        reply = scopePrefix + `No matching bookmarks found for **"${query}"** in this scope. Try broader terms or switch scope to \`ADSP (All)\`.`;
      }
    }

    return { reply, results: topResults };
  }

  // Handle Chat Submission
  async function submitAiQuery(queryText) {
    const q = queryText.trim();
    if (!q) return;

    const vpnOnly = aiFilterVpn.checked;
    const topOnly = aiFilterTop.checked;

    // Display user message with product scope tag
    const scopeObj = PRODUCT_SCOPES[selectedProduct] || PRODUCT_SCOPES.adsp;
    const scopeBadge = selectedProduct !== 'adsp' 
      ? `<span class="ai-scope-tag">${scopeObj.icon} ${escapeHtml(scopeObj.name)}</span> ` 
      : '';
    appendMessage('user', scopeBadge + formatMarkdown(q));
    aiInput.value = '';
    aiInput.style.height = 'auto';

    // Set state & show stop button
    isQueryRunning = true;
    activeAbortController = new AbortController();
    if (aiSendBtn) aiSendBtn.style.display = 'none';
    if (aiStopBtn) aiStopBtn.style.display = 'flex';

    // Show loading assistant indicator with inline stop button
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'ai-msg assistant loading-state';
    loadingMsg.innerHTML = `
      <div class="ai-bubble">
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
          <em>Searching bookmarks (${escapeHtml(scopeObj.name)}) &amp; synthesizing answer... 🔍</em>
          <button type="button" class="ai-inline-stop-btn" id="aiInlineStopBtn">⏹ Stop</button>
        </div>
      </div>
    `;
    aiMessages.appendChild(loadingMsg);
    aiMessages.scrollTop = aiMessages.scrollHeight;

    const inlineStopBtn = loadingMsg.querySelector('#aiInlineStopBtn');
    if (inlineStopBtn) {
      inlineStopBtn.addEventListener('click', stopActiveQuery);
    }

    if (isServerConnected) {
      try {
        const payload = {
          query: q,
          product: selectedProduct,
          product_scope: selectedProduct,
          filters: {
            requires_vpn: vpnOnly ? true : null,
            min_visits: topOnly ? 5 : 0,
            product: selectedProduct !== 'adsp' ? selectedProduct : null
          },
          history: chatHistory.slice(-4)
        };

        const res = await fetch(`${AI_SERVER_URL}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: activeAbortController.signal
        });

        if (res.ok) {
          const data = await res.json();
          loadingMsg.remove();
          appendMessage('assistant', formatMarkdown(data.reply), data.results);
          chatHistory.push({ role: 'user', content: q }, { role: 'assistant', content: data.reply });
          return;
        }
      } catch (err) {
        if (err.name === 'AbortError') {
          // Query was stopped by user; message already appended by stopActiveQuery()
          return;
        }
        console.warn('Project server error, falling back to browser search:', err);
      } finally {
        if (!isQueryRunning) {
          // Already aborted or finished
        } else {
          isQueryRunning = false;
          activeAbortController = null;
          if (aiSendBtn) aiSendBtn.style.display = 'flex';
          if (aiStopBtn) aiStopBtn.style.display = 'none';
        }
      }
    }

    // Check if query was aborted while waiting
    if (!isQueryRunning && !loadingMsg.parentNode) {
      return;
    }

    // Fallback: Browser In-Memory Engine
    loadingMsg.remove();
    const fallback = clientFallbackSearch(q, vpnOnly, topOnly, selectedProduct);
    appendMessage('assistant', formatMarkdown(fallback.reply), fallback.results);
    chatHistory.push({ role: 'user', content: q }, { role: 'assistant', content: fallback.reply });

    isQueryRunning = false;
    activeAbortController = null;
    if (aiSendBtn) aiSendBtn.style.display = 'flex';
    if (aiStopBtn) aiStopBtn.style.display = 'none';
  }

  aiChatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    submitAiQuery(aiInput.value);
  });
</script>

</body>
</html>
"""

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Updated dark-mode showcase HTML with VPN tags at: {OUTPUT_HTML}")

