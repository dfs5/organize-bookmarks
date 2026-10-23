---
name: bookmark-lookup
description: >-
  Search, filter, and inspect the user's curated bookmarks catalog by product,
  topic, source type, or historical visit frequency. Use whenever the user asks
  for links, bookmarks, articles, sizing tools, repositories, or references
  about any F5, NGINX, Cloud, or Security topic.
---

# Bookmark Lookup Skill

This skill allows Antigravity to quickly find bookmarks and links from the user's curated catalog (`bookmarks_catalog.json`) enriched with historical visit frequencies and multi-dimensional tags.

## When to Use This Skill
Activate this skill whenever the user asks:
- "Show me links/bookmarks about [topic]" (e.g., BIG-IP sizing, OAuth, NGINX Ingress, rSeries, CVEs)
- "What are my most used F5 links / bookmarks?"
- "Find the KB article for [issue/policy]"
- "Where is the sizing advisor / calculator?"
- "Show me repositories or internal tools for [topic]"

## How to Query Bookmarks

Use the local lookup utility:
```bash
python3 <WORKSPACE_DIR>/.agents/skills/bookmark-lookup/lookup.py "<search terms>" [options]
```

### Available Options:
- `--product <name>`: Filter by product tag:
  - `big-ip`: BIG-IP LTM, APM, ASM, GTM, TMOS
  - `rseries`: F5 rSeries appliances
  - `velos`: F5 VELOS chassis
  - `nginx`: NGINX Plus, Open Source, NGINX App Protect, NJS
  - `f5-xc`: F5 Distributed Cloud, WAAP, Multi-Cloud App Connect
  - `f5-workforce-ai-security`: F5 Workforce AI Security, SurePath AI, GenAI traffic flows & security
  - `public-cloud`: AWS, Azure, GCP, OpenShift (OCP)
  - `ai-workloads`: AI reference architectures, models, prompts
- `--topic <name>`: Filter by functional topic tag:
  - `sizing-capacity`: Sizing advisors, throughput limits, CPU core allocations, license tiers
  - `access-identity`: APM, SAML, OAuth, OIDC, Kerberos, VPN, Edge Client
  - `security-waf`: AWAF, ASM, DoS/DDoS protection, bot defense, SIRT advisories
  - `traffic-ssl`: LTM traffic management, SSL/TLS profiles, ciphers, ICAP
  - `dns-gtm`: DNS, GTM, Wide IPs
  - `releases-lifecycle`: Compatibility matrices, software release calendars, EOL/EOS policies
  - `automation-devops`: AS3, FAST, Declarative Onboarding, Terraform, REST APIs
  - `kubernetes-containers`: K8s, Ingress controllers, Gateway API, container networking
  - `programmability-irules`: iRules, NJS scripts, DevCentral snippets
- `--type <name>`: Filter by source type:
  - `kb-article`: Official F5 Knowledge Base articles (K-numbers)
  - `techdocs`: Clouddocs, TechDocs, official documentation portals
  - `github-repo`: GitHub and GitLab repositories
  - `devcentral`: DevCentral community articles and code
  - `dashboard`: Tableau dashboards, Salesforce, internal telemetry
  - `internal-portal`: ServiceNow employee portal, SharePoint, internal apps
  - `roadmap-ideas`: Aha! Ideas portal and product roadmaps
  - `sizing-tool`: Web calculators and Excel/online sizing tools
- `--min-visits <n>`: Show only links visited at least `n` times in browser history.
- `--limit <n>`: Maximum number of results to display (default: 25).
- `--json`: Output raw JSON for programmatic filtering.

## Bookmarks AI Agent Backend & HTTP API
The project includes a dedicated local AI Search & Copilot server in the `ai_agent_server/` directory (`ai_agent_server/ai_agent_server.py`) configured via [`ai_agent_server/ai_agent_server.conf`](../../../ai_agent_server/ai_agent_server.conf). It provides natural language understanding, zero-shot LLM intent extraction (local Ollama or Cloud Gemini), hybrid BM25 scoring, and deep page content verification.

### Managing the Server:
```bash
# Start in background (can be run from root or from ai_agent_server/)
./run_ai_server.sh

# Check status
./run_ai_server.sh --status

# Stop server
./run_ai_server.sh --stop

# Foreground debug mode
./run_ai_server.sh --fg
```

### Endpoints:
- `GET http://localhost:8765/api/status`: Health check, loaded bookmark count, and active LLM provider.
- `POST http://localhost:8765/api/chat`: Natural language search & AI synthesis.
  - Body: `{"query": "How do I size BIG-IP VE?", "filters": {"requires_vpn": false}}`
- `POST http://localhost:8765/api/search`: Direct structured BM25 lookup.
  - Body: `{"query": "workforce ai", "limit": 10}`
- `GET http://localhost:8765/bookmarks_showcase.html`: Interactive web showcase with embedded AI Copilot drawer (shortcut: `⌘K`).

## Handling Authentication & Restricted Pages
If the user asks to inspect or extract details from an internal link (e.g. SupportNet, Tableau, ServiceNow, Jira) that requires Single Sign-On (SSO) or VPN authentication:
1. Provide the direct URL to the user.
2. Note that authentication is needed and prompt the user to log in via their Chrome **`f5.com`** profile if they'd like you to fetch further details.

