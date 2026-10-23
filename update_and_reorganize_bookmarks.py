#!/usr/bin/env python3
"""
update_and_reorganize_bookmarks.py
-----------------------------------
Applies findings from the live audit & content crawl:
1. Prunes dead, defunct, moved, and useless bookmarks (including the 'WE'VE MOVED' Highspot CMS stub).
2. Updates canonical URLs for verified redirects (e.g. support.f5.com -> my.f5.com).
3. Cleans titles, decodes HTML entities, and replaces raw URL titles with human-readable labels.
4. Categorizes bookmarks into modern, content-driven 9 Strategic Pillars.
5. Exports new favorites_product_frequency_organized.html (Netscape format) and updates bookmarks_catalog.json.
6. Regenerates bookmarks_showcase.html and attempts Chrome Profile 1 sync.
"""

import os
import json
import time
import shutil
import re
import html
from urllib.parse import urlparse

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(WORKSPACE, "bookmarks_catalog.json")
LIVE_AUDIT_PATH = os.path.join(WORKSPACE, "archive", "audits", "live_audit_results.json")
STALE_AUDIT_PATH = os.path.join(WORKSPACE, "archive", "audits", "stale_bookmarks_results.json")
OUTPUT_HTML = os.path.join(WORKSPACE, "favorites_product_frequency_organized.html")
CHROME_P1_BM = os.path.expanduser("~/Library/Application Support/Google/Chrome/Profile 1/Bookmarks")
CHROME_P1_BAK = os.path.join(WORKSPACE, "archive", "backups", "Profile1_Bookmarks.bak")

def load_data():
    cat_path = CATALOG_PATH if os.path.exists(CATALOG_PATH) else os.path.join(WORKSPACE, "bookmarks_catalog.example.json")
    with open(cat_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    live_audit = []
    if os.path.exists(LIVE_AUDIT_PATH):
        with open(LIVE_AUDIT_PATH, "r", encoding="utf-8") as f:
            live_audit = json.load(f)
    stale_audit = []
    if os.path.exists(STALE_AUDIT_PATH):
        with open(STALE_AUDIT_PATH, "r", encoding="utf-8") as f:
            stale_audit = json.load(f)
    return catalog, live_audit, stale_audit

def clean_title(title, url):
    if not title:
        title = url
    
    t = html.unescape(title).strip()
    
    # Strip leading notification badges like "(33) " or "(118) " from YouTube/LinkedIn
    t = re.sub(r"^\(\d+\)\s*", "", t)

    # Strip common trailing branding suffixes
    t = re.sub(r"\s*\|\s*DevCentral\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+DevCentral\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\|\s*LinkedIn\s*$", "", t, flags=re.IGNORECASE)

    # Specific known raw URLs, SSO stubs, or ugly titles
    if "sites/salesandmktg/sales/ADC and App Services Marketing/SitePages/F5-rSeries.aspx" in url or t.startswith("https://f5.sharepoint.com/sites/salesandmktg/sales/ADC and App Services Marketing"):
        return "F5 rSeries Next-Gen Hardware - Field Hub & Collateral"
    if "csp/article/K13845" in url or url.endswith("/K13845") or t == "https://support.f5.com/csp/article/K13845":
        return "K13845: Overview of Supported BIG-IP Upgrade Paths and Planning Reference"
    if "csp/article/K16307" in url or ("K16307" in url and t.startswith("https://")):
        return "K16307: Troubleshooting BIG-IQ Device Discovery Failures"
    if "csp/article/K04452074" in url or ("K04452074" in url and t.startswith("https://")):
        return "K04452074: Overview of Using the BIG-IQ System Authentication Token"
    if "userinfo.profile" in url:
        return "Google Identity OAuth 2.0 Scope Reference: userinfo.profile"
    if "ffive/login-saml.htmld" in url and "authgwy" not in url:
        return "Workday Employee Portal (F5 SAML SSO Login)"
    if "wday/authgwy/ffive/login-saml.htmld" in url:
        return "Workday Authentication Gateway (F5 SSO)"
    if "weblogin.f5net.com/sso/login.php" in url and "devkeygenerator" in url:
        return "F5 Internal Dev Key Generator (SSO Login)"
    if "launcher.myapps.microsoft.com/api/signin/" in url:
        m = re.search(r"signin/([0-9a-f\-]+)", url, flags=re.IGNORECASE)
        app_id = m.group(1)[:8] if m else "SSO"
        if t.lower() in ("continue", "f5 single sign-on", "sign in to your account", "my apps") or t.startswith("http"):
            return f"Microsoft MyApps Enterprise SSO Application ({app_id})"
    if "myapplications.microsoft.com" in url and t.lower() in ("my apps", "continue", "f5 single sign-on", "sign in to your account"):
        return "Microsoft MyApps Corporate Application Portal"
    if url.rstrip("/") == "https://account.f5.com/myf5" and t.lower() in ("f5", "myf5"):
        return "MyF5 Account & Subscription Management Portal"
    if "7f2c6714-11a8-4eac-99c1-8e8bbc1cf4a6" in url.lower() and t.lower() == "resolver":
        return "Systems Engineering Resolver & Escalation Guide"
    if "eqhqng6jvahdo0n_oj-pqpybuqiiqwihyurygyagt5cm-g" in url.lower() and t.lower() == "dach":
        return "DACH Channel Sales Hub & Partner Matrix"
    if "big-ip-virtual-editions-datasheet.pdf" in url.lower():
        return "BIG-IP Virtual Editions Datasheet"
    if "docs.docker.com/engine/reference/run" in url.lower() and (t.startswith("|") or len(t) < 10):
        return "Docker Run Command Reference"
    if url.rstrip("/") == "https://github.com/nginx" and t.lower() == "nginx":
        return "NGINX Official GitHub Organization"
    if url.rstrip("/") == "https://github.com/nginxinc" and t.lower() in ("nginx, inc.", "nginxinc"):
        return "NGINX Inc. Official GitHub Repositories"
    if url.rstrip("/") == "https://github.com/F5Networks" and t.lower() == "f5 networks":
        return "F5 Networks Official GitHub Organization"
    if url.rstrip("/") == "https://www.youtube.com/@F5_inc":
        return "F5, Inc. Official YouTube Channel"
    if url.rstrip("/") in ("http://httpbin.org", "https://httpbin.org") and t in ("httpbin.org", "http://httpbin.org"):
        return "HTTPBin: HTTP Request & Response Testing Service"
    if "httpbin.org/headers" in url:
        return "HTTPBin: Request Headers Inspector"
    if "www.linguee.de" in url and "431 Request" in t:
        return "Linguee: German-English Dictionary & Translation"
    if "DriveHQ Cloud File Server" in t:
        return "DriveHQ Cloud WebDAV & FTP Enterprise Storage"
    if url.rstrip("/") == "https://docs.cloud.f5.com/docs-v2":
        return "Home | F5 Distributed Cloud Tech Docs"
    if url.rstrip("/") == "https://my.f5.com/manage/s":
        return "MyF5 - Support, Cases & Knowledge Base Portal"
    if url.rstrip("/") == "https://clouddocs.f5.com":
        return "F5 Cloud Docs Portal"
    if url.rstrip("/") == "https://clouddocs.f5.com/api/icontrol-rest":
        return "iControl REST API Reference & User Guide"
    if "community.f5.com/t/lightboard-lessons-big-ip-life-of-a-packet/68296" in url:
        return "Lightboard Lessons: BIG-IP Life of a Packet"
    if "community.f5.com/t/f5-distributed-cloud-ce-high-availability-options-a-comparative-exploration/74585" in url:
        return "F5 Distributed Cloud – CE High Availability Options: A Comparative Exploration"
    if "ips-domains.txt" in url:
        return "F5 Distributed Cloud Network Reference: IPs and Domains"
    if "ips-domains.json" in url:
        return "F5 Distributed Cloud Network Reference: IPs and Domains (JSON)"
    if "support.f5net.com/v2" in url and t.lower().startswith("support.f5net.com"):
        return "F5 Internal Support Portal v2 (support.f5net.com)"
    if "demo.nginx.com/api/6/ssl" in url and t.lower().startswith("demo.nginx.com"):
        return "NGINX Plus Live Activity Monitoring REST API v6: SSL Statistics"
    if "docs.aws.amazon.com/awsec2/latest/userguide/using-eni.html" in url.lower() and t.lower() == "limits":
        return "Elastic Network Interfaces (ENI) in Amazon EC2 — Limits & Specifications"
    if "clouddocs.f5.com/products/insight/latest/product_overview" in url.lower() and t.lower() == "overview":
        return "F5 Telemetry Insights Product Overview"
    if "www.f5.com/search?q=f5+insight" in url.lower() and t.lower() == "search":
        return "F5 Technical Search: F5 Insight Across TechDocs, MyF5 & DevCentral"
    if "my.f5.com/manage/s/global-search" in url.lower() and t.lower() == "search":
        return "MyF5 Global Knowledge Base & Support Search"
    if "atlas.f5-dx.com/use-cases" in url.lower():
        return "F5 Digital Experience (DX) Atlas: Use Cases"
    if url.lower().rstrip("/") == "https://atlas.f5-dx.com":
        return "F5 Digital Experience (DX) Atlas Portal"
    if "app.vivun.com/dashboard/list/opportunities" in url.lower():
        return "Vivun Hero: SE Opportunities Dashboard"
    if "app.vivun.com/dashboard/funnel" in url.lower():
        return "Vivun Hero: SE Presales Funnel Dashboard"
    if "vertexaisearch.cloud.google/home/cid/229009fb" in url.lower() and t.lower() == "agents":
        return "Google Cloud Vertex AI Search: Enterprise AI Agents"
    if "f5inc.aha.io/shared/5476b9c1a24590d565e29bd191af8ffa" in url.lower():
        return "BIG-IP TMOS LTM/SSL/VE - 22.1 Candidates | Aha!"
    if "f5bigip.ideas.aha.io" in url.lower():
        return "BIG-IP Ideas Portal | Aha!"
    if "nginx.ideas.aha.io" in url.lower():
        return "Modern Apps and AI Delivery & Security Product Ideas | Aha!"
    if "console.ves.volterra.io/login/start" in url.lower():
        return "F5 Distributed Cloud Console — Tenant Login"
    if "app.heyhack.com" in url.lower():
        return "F5 Web App Scanning (formerly Heyhack) Portal"
    if "ptt.pl.pdsea.f5net.com" in url.lower():
        return "F5 Performance Testing Tool (PTT) Portal"
    if "lg.ring.nlnog.net" in url.lower():
        return "NLNOG Ring Looking Glass — BGP Routing Table Lookup"
    if "network_performance_metrics.html" in url.lower():
        return "Bandwidth, Packets Per Second, and Other Network Performance Metrics"
    if "aws-resource-init.html" in url.lower():
        return "AWS::CloudFormation::Init - AWS CloudFormation"
    if "brightcloud.com" in url.lower():
        return "Security Services | Webroot BrightCloud"
    if "websense-web-filter-security" in url.lower():
        return "Forcepoint Web Security"
    if url.lower().rstrip("/") in ("https://help.ai.f5.com/en", "https://help.ai.f5.com"):
        return "F5 Workforce AI Security Help Center"

    # Clean raw document filenames (.pptx, .docx, .xlsx, .pdf, .txt, .json)
    if re.search(r"\.(pptx|docx|xlsx|pdf|txt|json)$", t, flags=re.IGNORECASE):
        t = re.sub(r"\.(pptx|docx|xlsx|pdf|txt|json)$", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^\d{8}_", "", t)
        t = t.replace("_", " ").strip()
        if t.lower() == "sp-f5-edge-2-0":
            t = "Service Provider F5 Edge 2.0 Architecture"

    # Replace "Article: K12345 - " with "K12345: "
    t = re.sub(r"^Article:\s*(K\d+)\s*[-–:]\s*", r"\1: ", t, flags=re.IGNORECASE)
    
    # Trim repetitive trailing documentation strings
    if " — Unofficial - F5 Certification Exam Prep Material documentation" in t:
        t = t.replace(" — Unofficial - F5 Certification Exam Prep Material documentation", "")
    
    return t

def is_vpn_url(url, legacy_path_str=""):
    try:
        netloc = urlparse(url).netloc.lower()
        return "f5net.com" in netloc
    except Exception:
        return "f5net.com" in url.lower()


def assign_hierarchy(bm, force=False):
    url = bm["url"].lower()
    title = bm["title"].lower()
    desc = (bm.get("description") or "").lower()
    notes = (bm.get("notes") or "").lower()
    leg = [p.lower() for p in bm.get("legacy_path", [])]
    leg_str = " > ".join(leg)
    full = f"{url} {title} {desc} {notes} {leg_str}"

    # Always fix known misclassifications even when hierarchy exists
    if any(k in url for k in ["lightning.force.com", "salesforce.com", "tryopine.com", "vivun.com"]):
        return ("08. Internal Sales Engineering & Enablement", "Presales Plays, Opine & Salesforce")
    if "jira.f5net.com" in url:
        return ("08. Internal Sales Engineering & Enablement", "Internal SharePoint & Engineering Hubs")
    if "account.f5.com/myf5" in url or "secure.f5.com/infopage" in url or any(k in url for k in [
        "f5.com/company/contact", "f5.com/trials", "f5.com/company/certifications",
        "f5.com/company/trust-center", "f5.com/company/policies", "f5.com/search"
    ]):
        return ("05. Knowledge Base (KBs) & Official TechDocs", "F5 Support, Licensing & Account Portals")
    if "f5.com/attack" in url:
        return ("05. Knowledge Base (KBs) & Official TechDocs", "Security Advisories & Hardened Releases")
    if "release-cadence-security-notifications" in url:
        return ("06. Product Lifecycle, Releases & Roadmaps", "BIG-IP & F5OS Software Release Matrices")
    if "f5bigiq-setupguide.readthedocs.io" in url:
        return ("01. BIG-IP & TMOS", "Central Management (BIG-IQ)")
    if "clouddocs.f5.com/training/community/f5cert/html/class7" in url:
        return ("01. BIG-IP & TMOS", "LTM, Traffic & SSL/TLS")
    if "f5_bigip_tmos_control_plane" in url:
        return ("01. BIG-IP & TMOS", "TMOS Administration & Diagnostics (iHealth)")
    if "se+team+dach%2fvelos" in url:
        return ("01. BIG-IP & TMOS", "Next-Gen Hardware (rSeries & VELOS)")
    if any(k in full for k in ["f5ai.pd.f5net.com", "lifearchitect", "whylabs"]):
        return ("04. AI Security, Workforce AI & Agentic AI", "LLM Models, Assistants & Tools")
    if any(k in url for k in ["amadeus.com/en/innovation/artificial-intelligence", "/innovation/artificial-intelligence", "hoffmann.ai", "phoenix.tech/phoenix-innovations"]) or "ai initiatives" in notes:
        return ("04. AI Security, Workforce AI & Agentic AI", "Enterprise Agentic AI & Antigravity")
    if any(k in url for k in ["reference-architectures/ai-overview", "reference-architecture/ai", "frontier-ai-defense", "the-f5-executive-collective/engage"]):
        return ("04. AI Security, Workforce AI & Agentic AI", "AI Gateway & AI Security Platform")
    if any(k in url for k in ["f5.com/solutions/web-app-and-api-protection", "explore-f5-api-discovery-and-security-essentials", "app.heyhack.com"]):
        return ("03. F5 Distributed Cloud (XC) & Multi-Cloud", "XC WAAP & API Security")
    if "console.ves.volterra.io/login/start" in url:
        return ("03. F5 Distributed Cloud (XC) & Multi-Cloud", "XC Console & SaaS Services")
    if "aha.io" in url:
        return ("06. Product Lifecycle, Releases & Roadmaps", "Product Roadmaps & Ideas")
    if "ptt.pl.pdsea.f5net.com" in url:
        return ("08. Internal Sales Engineering & Enablement", "Presales Plays, Opine & Salesforce")
    if any(k in url for k in ["lg.ring.nlnog.net", "bgp.he.net/report/peers"]):
        return ("09. External Engineering, Protocols & Tools", "Online Utilities, Decoders & Network Tools")
    if any(k in url for k in ["network_performance_metrics.html", "aws-resource-init.html", "tools.ietf.org/html/rfc3507"]):
        return ("09. External Engineering, Protocols & Tools", "Industry Standards & Technical References")
    if any(k in url for k in ["brightcloud.com", "forcepoint.com/product/content-security"]):
        return ("09. External Engineering, Protocols & Tools", "Security Research, CVEs & Threat Intel")
    if any(k in url for k in ["microservices.io", "kubernetes.io/docs/tasks/administer-cluster/namespaces", "gateway-api.sigs.k8s.io", "gateway-api-inference-extension.sigs.k8s.io"]):
        return ("09. External Engineering, Protocols & Tools", "Kubernetes, Containers & Cloud Native")
    if url.rstrip("/") == "https://www.f5.com/resources/demos" or "f5-digital-customer-engagement-center.readthedocs.io" in url:
        return ("07. Lab Environments, Demos & Developer Ecosystem", "UDF Lab Environments & Demos")
    if any(k in url for k in ["atlas.f5-dx.com", "f5.com/industries/", "f5.com/products/compare", "f5.com/products/f5-application-delivery-and-security-platform"]) or url.rstrip("/") == "https://www.f5.com":
        return ("08. Internal Sales Engineering & Enablement", "Field Enablement, Uberdecks & Highspot")

    if not force and "hierarchy" in bm and isinstance(bm["hierarchy"], (list, tuple)) and len(bm["hierarchy"]) == 2 and bm["hierarchy"][0]:
        return tuple(bm["hierarchy"])
    
    # ----------------------------------------------------
    # PILLAR 04: AI Security, Workforce AI & Agentic AI
    # ----------------------------------------------------
    if any(k in full for k in ["ai-gateway", "ai gateway", "f5-ai-gateway", "ai-overview", "reference-architecture/ai", "frontier-ai"]):
        return ("04. AI Security, Workforce AI & Agentic AI", "AI Gateway & AI Security Platform")
    if any(k in full for k in ["calypso", "calypsoai", "guardrail", "ai-application-security", "ai application security"]):
        return ("04. AI Security, Workforce AI & Agentic AI", "F5 AI Guardrails & Runtime Protection")
    if any(k in full for k in ["workforce ai", "surepath", "help.ai.f5.com"]) or "f5-workforce-ai-security" in bm.get("tags", {}).get("products", []):
        return ("04. AI Security, Workforce AI & Agentic AI", "F5 Workforce AI Security & SurePath")
    if any(k in full for k in ["antigravity", "enterpriseagenticai", "agentic", "agent-server", "artificial-intelligence", "artificial intelligence"]):
        return ("04. AI Security, Workforce AI & Agentic AI", "Enterprise Agentic AI & Antigravity")
    if any(k in full for k in ["gemini.google.com", "openai.com", "anthropic", "claude.ai", "chatgpt", "notebooklm", "vertexaisearch", "ai tools", "f5ai.pd.f5net.com", "lifearchitect", "whylabs"]):
        return ("04. AI Security, Workforce AI & Agentic AI", "LLM Models, Assistants & Tools")

    # ----------------------------------------------------
    # PILLAR 06: Product Lifecycle, Releases & Roadmaps
    # ----------------------------------------------------
    if "aha.io" in url or "roadmap" in full or ("ideas" in full and ("product" in full or "candidate" in full)):
        return ("06. Product Lifecycle, Releases & Roadmaps", "Product Roadmaps & Ideas")
    if any(k in title for k in ["release matrix", "software support policy", "lifecycle support policy", "compatibility matrix", "hotfix and point release", "release date information", "most recent versions", "interchange", "k000162252", "release cadence"]):
        if any(k in title for k in ["hardware", "iseries", "rseries", "platform lifecycle"]):
            return ("06. Product Lifecycle, Releases & Roadmaps", "Hardware Platforms & Lifecycle Policies")
        return ("06. Product Lifecycle, Releases & Roadmaps", "BIG-IP & F5OS Software Release Matrices")

    # ----------------------------------------------------
    # PILLAR 02: NGINX Ecosystem
    # ----------------------------------------------------
    if "nginx" in full and "jira.f5net.com" not in url:
        if any(k in full for k in ["sizing", "sizing advisor", "core", "benchmark", "rps", "cps", "performance", "datasheet"]):
            return ("02. NGINX Ecosystem", "NGINX Sizing & Performance Benchmarks")
        if any(k in full for k in ["nap", "app protect", "waf", "dos", "security"]):
            return ("02. NGINX Ecosystem", "NGINX App Protect (NAP)")
        if any(k in full for k in ["ingress", "gateway api", "k8s", "kubernetes"]):
            return ("02. NGINX Ecosystem", "NGINX Ingress & Kubernetes")
        if any(k in full for k in ["njs", "javascript"]):
            return ("02. NGINX Ecosystem", "NJS & Modern Programmability")
        if any(k in full for k in ["nim", "instance manager", "connectivity"]):
            return ("02. NGINX Ecosystem", "NGINX Instance Manager & Connectivity")
        return ("02. NGINX Ecosystem", "NGINX Core & OSS Administration")

    # ----------------------------------------------------
    # PILLAR 03: F5 Distributed Cloud (XC) & Multi-Cloud
    # ----------------------------------------------------
    if any(k in full for k in ["f5xc", "f5 xc", "f5-xc", "volterra", "distributed cloud", "cloud.f5.com", "ves.volterra"]) or ("cloud" in leg and not any(k in full for k in ["azure aws", "sizing", "publiccloud"])):
        if any(k in full for k in ["aws", "azure", "gcp", "ocp", "alibaba", "openshift"]):
            return ("03. F5 Distributed Cloud (XC) & Multi-Cloud", "Public & Hybrid Cloud Deployments")
        if any(k in full for k in ["automation", "terraform", "api", "rest api"]):
            return ("03. F5 Distributed Cloud (XC) & Multi-Cloud", "XC Automation, APIs & Terraform")
        if "docs.cloud.f5.com" in url or "documentation" in title:
            return ("03. F5 Distributed Cloud (XC) & Multi-Cloud", "XC Documentation & Architecture Guides")
        if any(k in full for k in ["waap", "waf", "api protection", "bot", "ddos"]):
            return ("03. F5 Distributed Cloud (XC) & Multi-Cloud", "XC WAAP & API Security")
        return ("03. F5 Distributed Cloud (XC) & Multi-Cloud", "XC Console & SaaS Services")

    # ----------------------------------------------------
    # PILLAR 05: Knowledge Base (KBs) & Official TechDocs
    # ----------------------------------------------------
    if any(k in url for k in ["clouddocs.f5.com", "techdocs.f5.com", "docs.nginx.com", "my.f5.com", "support.f5.com", "docs.f5.com", "account.f5.com"]):
        if any(k in url or k in title for k in ["k12201527", "sirt", "security notifications", "security advisory", "vulnerability"]):
            return ("05. Knowledge Base (KBs) & Official TechDocs", "Security Advisories & Hardened Releases")
        if "clouddocs.f5.com" in url or "techdocs.f5.com" in url or "docs.f5.com" in url:
            return ("05. Knowledge Base (KBs) & Official TechDocs", "Official TechDocs & CloudDocs")
        if any(k in url for k in ["account.f5.com", "regional-support", "contact", "downloads"]):
            return ("05. Knowledge Base (KBs) & Official TechDocs", "F5 Support, Licensing & Account Portals")
        return ("05. Knowledge Base (KBs) & Official TechDocs", "MyF5 Portal & Knowledge Articles")

    # ----------------------------------------------------
    # PILLAR 08: Internal Sales Engineering & Enablement
    # (Evaluated before Pillar 07 so Salesforce/SharePoint URLs are never misrouted by keywords)
    # ----------------------------------------------------
    if any(k in url for k in [
        "service-now.com", "benevity.org", "supportnet.f5.com", "salesforce.com",
        "lightning.force.com", "force.com", "tableau.com", "tryopine.com", "highspot.com",
        "license.f5net.com", "workday.com", "servicegpt", "adp.com", "vivun.com", "varicent.com",
        "myapps.microsoft.com", "myapplications.microsoft.com"
    ]) or "sharepoint.com" in url or "f5net.com" in url:
        if "license.f5net.com" in url or "supportnet" in url or "support/rma" in leg_str or "sku.pdsea.f5net.com" in url:
            return ("08. Internal Sales Engineering & Enablement", "SupportNet RMA & License Key Generation")
        if any(k in url for k in ["tryopine.com", "salesforce", "lightning.force.com", "vivun.com"]):
            return ("08. Internal Sales Engineering & Enablement", "Presales Plays, Opine & Salesforce")
        if "highspot.com" in url or "solutionpackages" in url or "uberdeck" in full or "deck" in full:
            return ("08. Internal Sales Engineering & Enablement", "Field Enablement, Uberdecks & Highspot")
        if "tableau" in url or "dsm" in title or "telemetry" in title or "varicent.com" in url:
            return ("08. Internal Sales Engineering & Enablement", "Sales, BI & Telemetry Dashboards")
        if any(k in url for k in ["service-now" , "workday", "adp.com", "myapps.microsoft.com", "myapplications.microsoft.com"]):
            return ("08. Internal Sales Engineering & Enablement", "Corporate Portals, HR & Workday")
        if "sharepoint" in url or "jira.f5net.com" in url:
            return ("08. Internal Sales Engineering & Enablement", "Internal SharePoint & Engineering Hubs")
        return ("08. Internal Sales Engineering & Enablement", "Presales Plays, Opine & Salesforce")

    # ----------------------------------------------------
    # PILLAR 07: Lab Environments, Demos & Developer Ecosystem
    # ----------------------------------------------------
    if "udf.f5.com" in url or "testdrive.f5.com" in url:
        return ("07. Lab Environments, Demos & Developer Ecosystem", "UDF Lab Environments & Demos")
    if "github.com" in url or "gitlab.com" in url:
        return ("07. Lab Environments, Demos & Developer Ecosystem", "GitHub Repositories & Open Source Tools")
    if "community.f5.com" in url or "devcentral.f5.com" in url:
        return ("07. Lab Environments, Demos & Developer Ecosystem", "DevCentral Articles & Code Snippets")
    if any(re.search(p, full) for p in [r"\bdeclarative\b", r"\bas3\b", r"\bfast\b", r"\bpostman\b", r"big-ip declarative api", r"telemetry streaming"]):
        return ("07. Lab Environments, Demos & Developer Ecosystem", "Declarative APIs & Automation (AS3/FAST)")

    # ----------------------------------------------------
    # PILLAR 01: BIG-IP & TMOS
    # ----------------------------------------------------
    if "ihealth.f5.com" in url:
        return ("01. BIG-IP & TMOS", "TMOS Administration & Diagnostics (iHealth)")
    
    is_f5_context = any(k in full for k in [
        "f5", "big-ip", "bigip", "big-iq", "bigiq", "tmos", "rseries", "velos", "bugzilla", "vcmp", "tmm",
        "apm", "ltm", "asm", "awaf", "gtm", "afm", "irule", "irules", "ingresslink", "sirt", "ihealth", "viprion", "iseries"
    ])
    if ((any(l in leg for l in ("bip", "sizing", "products one-stop")) and is_f5_context) or any(k in full for k in [
        "big-ip", "bigip", "big-iq", "bigiq", "tmos", "rseries", "velos", "bugzilla", "vcmp", "tmm",
        "f5 apm", "f5 ltm", "f5 asm", "f5 gtm", "f5 afm", "irule", "irules", "ingresslink", "f5 sirt"
    ])):
        if "bugzilla" in url:
            return ("01. BIG-IP & TMOS", "TMOS Engineering & Bug Tracker")
        if any(k in full for k in ["asm", "awaf", "waf", "security", "ddos", "bot", "sirt", "attack"]):
            return ("01. BIG-IP & TMOS", "Security (AWAF, ASM, DoS & Bot Defense)")
        if any(k in full for k in ["apm", "access", "saml", "vpn", "edge client", "webtop", "session cookies"]):
            return ("01. BIG-IP & TMOS", "Access & Identity (APM & SAML)")
        if any(k in full for k in ["gtm", "dns", "wideip", "bind"]):
            return ("01. BIG-IP & TMOS", "DNS & Global Server Load Balancing (GTM)")
        if any(k in full for k in ["ltm", "traffic", "ssl", "tls", "icap", "pool", "virtual server", "persistence", "vlan", "ingresslink"]):
            return ("01. BIG-IP & TMOS", "LTM, Traffic & SSL/TLS")
        if any(k in full for k in ["irules", "irule"]):
            return ("01. BIG-IP & TMOS", "iRules & Programmability (Tcl & LX)")
        if "big-iq" in full or "bigiq" in full:
            return ("01. BIG-IP & TMOS", "Central Management (BIG-IQ)")
        if any(k in full for k in ["migrate", "migration", "journeys", "ucs", "scf"]):
            return ("01. BIG-IP & TMOS", "Migration & Modernization (Journeys & UCS)")
        if any(k in full for k in ["rseries", "velos", "iseries", "hardware", "appliance", "optics", "sfp"]):
            return ("01. BIG-IP & TMOS", "Next-Gen Hardware (rSeries & VELOS)")
        if any(k in full for k in ["sizing", "throughput", "tps", "cpu", "sizing advisor", "calculator", "ve platform specifications", "ve sizing", "image sizes"]):
            return ("01. BIG-IP & TMOS", "Sizing, Capacity & VE Specifications")
        return ("01. BIG-IP & TMOS", "TMOS Administration & Diagnostics (iHealth)")

    # ----------------------------------------------------
    # PILLAR 09: External Engineering, Protocols & Tools
    # ----------------------------------------------------
    if any(k in full for k in ["oauth", "oidc", "kerberos", "spnego", "saml", "authschemes"]):
        return ("09. External Engineering, Protocols & Tools", "Identity & Authentication Protocols")
    if any(k in full for k in ["k8s", "kubernetes", "docker", "cni", "container", "service mesh", "aspenmesh"]):
        return ("09. External Engineering, Protocols & Tools", "Kubernetes, Containers & Cloud Native")
    if any(k in full for k in ["security", "cve", "threat", "hackers", "exploit", "trojaner", "drown", "x-force", "opswat"]):
        return ("09. External Engineering, Protocols & Tools", "Security Research, CVEs & Threat Intel")
    if any(k in full for k in ["decoder", "calculator", "tool", "tester", "converter", "esta.cbp.dhs.gov", "httpbin", "linguee"]):
        return ("09. External Engineering, Protocols & Tools", "Online Utilities, Decoders & Network Tools")
    if any(k in full for k in ["http", "protocol", "rfc", "iana", "mdn", "virtualization", "vmware-images"]):
        return ("09. External Engineering, Protocols & Tools", "Industry Standards & Technical References")
        
    return ("09. External Engineering, Protocols & Tools", "Industry Standards & Technical References")

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def get_title_with_badges(b):
    badge = f"[{b['visit_count']} visits] " if b.get("visit_count", 0) > 0 else ""
    vpn_badge = "[🔒 VPN] " if b.get("requires_vpn") else ""
    return vpn_badge + badge + b["title"]

def is_valid_redirect(orig_url, final_url, title=""):
    """Rejects bogus DevCentral Khoros->Discourse slug mismatches and generic landing redirects."""
    if not final_url or final_url == orig_url:
        return False
    u_orig = orig_url.lower()
    u_final = final_url.lower()
    if any(s in u_final for s in ["login.", "/signin", "okta.com", "authgwy", "accessdenied"]):
        return False
    if "community.f5.com" in u_orig:
        # Check if at least one meaningful word (>3 chars) from the original slug/title is in the final slug
        orig_words = set(re.findall(r"[a-z0-9]{4,}", u_orig.split("/")[-2] if "/m-p/" in u_orig or "/ta-p/" in u_orig or "/ba-p/" in u_orig or "/td-p/" in u_orig else u_orig))
        orig_words -= {"community", "technical", "articles", "general", "discussion", "forum", "https", "http", "html"}
        final_words = set(re.findall(r"[a-z0-9]{4,}", u_final))
        if orig_words and not (orig_words & final_words):
            return False
    # Reject redirects that strip deep path to a generic root page
    orig_path = urlparse(orig_url).path.rstrip("/")
    final_path = urlparse(final_url).path.rstrip("/")
    if len(orig_path) >= 10 and final_path in ("", "/products/nginx", "/manage/s"):
        return False
    return True

# Domains that require interactive browser session / SSO / VPN and must never be auto-deleted as dead 404s by urllib
PROTECTED_BROWSER_AUTH_DOMAINS = (
    "aha.io",
    "console.ves.volterra.io",
    "heyhack.com",
    "ptt.pl.pdsea.f5net.com",
    "lg.ring.nlnog.net",
    "crt.sh",
)

def is_protected_browser_url(url):
    u_low = (url or "").lower()
    return any(d in u_low for d in PROTECTED_BROWSER_AUTH_DOMAINS)

def main():
    print("Loading data...")
    catalog, live_audit, stale_audit = load_data()
    print(f"Original catalog count: {len(catalog)}")

    # 1. Identify URLs to remove (excluding protected browser-authenticated / SSO portals)
    dead_urls = set(
        r["url"] for r in live_audit
        if r["action"] == "REMOVE" and not is_protected_browser_url(r["url"])
    )
    for s in stale_audit:
        if s.get("category") in ("STALE_404", "STALE_DNS", "STALE_410", "STALE_CONN", "STALE_DEAD_REDIRECT", "STALE_DECOMMISSIONED"):
            if not is_protected_browser_url(s["url"]):
                dead_urls.add(s["url"])

    # Specific useless stubs identified
    dead_urls.update([
        "http://eshop.xcemea.f5demo.ch/",
        "https://gameserver.d5bd.cyber-range.f5.com/",
        "https://simulator.f5.com/",
        "https://nam02.safelinks.protection.outlook.com/GetUrlReputation",
        "https://teams.public.onecdn.static.microsoft/evergreen-assets/safelinks/2/atp-safelinks.html",
        "https://statics.teams.cdn.office.net/evergreen-assets/safelinks/2/atp-safelinks.html",
        "https://f5.sharepoint.com/sites/salesandmktg/sales/pages/Search.aspx", # User attached screenshot!
        "https://f5.sharepoint.com/sites/SalesHub"
    ])

    audit_map = {r["url"]: r for r in live_audit}
    canonical_redirect_overrides = {
        "http://www.cisco.com/web/about/security/intelligence/network_performance_metrics.html": "https://sec.cloudapps.cisco.com/security/center/resources/network_performance_metrics.html",
        "http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-init.html": "https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-init.html",
    }

    # 2. Filter, clean, update redirects, and enrich
    cleaned_catalog = []
    seen_by_exact_url = {}
    redirect_count = 0
    title_clean_count = 0
    dedup_count = 0

    for b in catalog:
        url = b["url"]
        if url in dead_urls or "ihealth.f5.com/qkview" in url.lower():
            continue

        # Restore previous_url if an earlier run applied a bogus DevCentral or root redirect
        prev_u = b.get("previous_url")
        if prev_u and not is_valid_redirect(prev_u, url, b.get("title", "")):
            b["url"] = prev_u
            url = prev_u
            b.pop("previous_url", None)

        if url in canonical_redirect_overrides:
            b["previous_url"] = url
            b["url"] = canonical_redirect_overrides[url]
            url = b["url"]
            redirect_count += 1

        # Follow and update canonical redirect ONLY if verified as valid
        audit_entry = audit_map.get(url)
        if audit_entry and audit_entry.get("redirected") and audit_entry.get("final_url"):
            final_u = audit_entry["final_url"]
            if final_u != url and is_valid_redirect(url, final_u, b.get("title", "")):
                b["url"] = final_u
                b["previous_url"] = url
                redirect_count += 1

        # Clean title
        old_title = b.get("title", "")
        new_title = clean_title(old_title, b["url"])
        if new_title != old_title:
            b["title"] = new_title
            title_clean_count += 1

        # Update hierarchy if needed
        b["hierarchy"] = list(assign_hierarchy(b))

        # Check VPN requirements
        leg_str = " > ".join(b.get("legacy_path", []))
        is_vpn = is_vpn_url(b["url"], leg_str)
        b["requires_vpn"] = is_vpn

        tags = b.setdefault("tags", {})
        source_types = tags.setdefault("source_types", [])
        if is_vpn and "vpn-required" not in source_types:
            source_types.append("vpn-required")
        elif not is_vpn and "vpn-required" in source_types:
            source_types.remove("vpn-required")

        # Guardrail: Deduplicate exact URLs after canonical redirect resolution
        canon_url = b["url"]
        if canon_url in seen_by_exact_url:
            existing = seen_by_exact_url[canon_url]
            existing["visit_count"] = max(existing.get("visit_count", 0), b.get("visit_count", 0))
            ex_date = int(existing.get("add_date") or 0)
            b_date = int(b.get("add_date") or 0)
            if b_date > 0 and (ex_date == 0 or b_date < ex_date):
                existing["add_date"] = str(b_date)
            if not existing.get("previous_url") and b.get("previous_url"):
                existing["previous_url"] = b["previous_url"]
            if not existing.get("icon") and b.get("icon"):
                existing["icon"] = b["icon"]
            if not existing.get("notes") and b.get("notes"):
                existing["notes"] = b["notes"]
            dedup_count += 1
            continue

        seen_by_exact_url[canon_url] = b
        cleaned_catalog.append(b)

    print(f"Removed {len(catalog) - len(cleaned_catalog) - dedup_count} dead/useless bookmarks.")
    print(f"Deduplicated {dedup_count} exact-URL redundant bookmarks.")
    print(f"Active clean bookmarks remaining: {len(cleaned_catalog)}")
    print(f"Updated {redirect_count} bookmarks to final canonical redirected URLs.")
    print(f"Cleaned {title_clean_count} bookmark titles.")

    # 3. Save new catalog
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned_catalog, f, indent=2, ensure_ascii=False)
    print(f"Saved updated catalog to {CATALOG_PATH}")

    # 4. Build hierarchy tree
    tree = {}
    for b in cleaned_catalog:
        p, s = assign_hierarchy(b)
        tree.setdefault(p, {}).setdefault(s, []).append(b)

    for p in tree:
        for s in tree[p]:
            tree[p][s].sort(key=lambda x: (-x.get("visit_count", 0), x.get("title", "").lower()))

    # 5. Generate Netscape HTML
    now = int(time.time())
    sorted_all = sorted(cleaned_catalog, key=lambda x: -x.get("visit_count", 0))
    top_visited = [b for b in sorted_all if b.get("visit_count", 0) > 0][:35]
    top_recent = sorted(cleaned_catalog, key=lambda x: int(x.get("add_date", 0)), reverse=True)[:30]

    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        "<!-- This is an automatically generated file. -->",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
        "<DL><p>",
        f'    <DT><H3 ADD_DATE="{now}" LAST_MODIFIED="{now}" PERSONAL_TOOLBAR_FOLDER="true">Favorites Bar</H3>',
        "    <DL><p>"
    ]

    # Quick Access
    lines.append(f'        <DT><H3 ADD_DATE="{now}" LAST_MODIFIED="{now}">⭐ Quick Access (Most Frequently Used)</H3>')
    lines.append("        <DL><p>")
    for b in top_visited:
        icon_str = f' ICON="{b["icon"]}"' if b.get("icon") else ""
        name = get_title_with_badges(b)
        lines.append(f'            <DT><A HREF="{b["url"]}" ADD_DATE="{b.get("add_date", now)}"{icon_str}>{esc(name)}</A>')
        if b.get("notes"):
            lines.append(f'            <DD>{esc(b["notes"])}')
    lines.append("        </DL><p>")

    # Recently Added
    lines.append(f'        <DT><H3 ADD_DATE="{now}" LAST_MODIFIED="{now}">🕒 Recently Added</H3>')
    lines.append("        <DL><p>")
    for b in top_recent:
        icon_str = f' ICON="{b["icon"]}"' if b.get("icon") else ""
        name = get_title_with_badges(b)
        lines.append(f'            <DT><A HREF="{b["url"]}" ADD_DATE="{b.get("add_date", now)}"{icon_str}>{esc(name)}</A>')
        if b.get("notes"):
            lines.append(f'            <DD>{esc(b["notes"])}')
    lines.append("        </DL><p>")

    # 9 Strategic Pillars
    for pillar in sorted(tree.keys()):
        subs = tree[pillar]
        pillar_name = re.sub(r"^\d+\.\s*", "", pillar)
        p_total = sum(len(items) for items in subs.values())
        lines.append(f'        <DT><H3 ADD_DATE="{now}" LAST_MODIFIED="{now}">{esc(pillar_name)} ({p_total})</H3>')
        lines.append("        <DL><p>")
        for subcat in sorted(subs.keys()):
            items = subs[subcat]
            lines.append(f'            <DT><H3 ADD_DATE="{now}" LAST_MODIFIED="{now}">{esc(subcat)} ({len(items)})</H3>')
            lines.append("            <DL><p>")
            for b in items:
                icon_str = f' ICON="{b["icon"]}"' if b.get("icon") else ""
                name = get_title_with_badges(b)
                lines.append(f'                <DT><A HREF="{b["url"]}" ADD_DATE="{b.get("add_date", now)}"{icon_str}>{esc(name)}</A>')
                if b.get("notes"):
                    lines.append(f'                <DD>{esc(b["notes"])}')
            lines.append("            </DL><p>")
        lines.append("        </DL><p>")

    lines.append("    </DL><p>")
    lines.append("</DL><p>")

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Generated clean Netscape HTML at: {OUTPUT_HTML}")

    # 6. Synchronize Chrome Profile 1 Bookmarks
    print("Syncing with Chrome Profile 1 Bookmarks...")
    if os.path.exists(CHROME_P1_BM):
        shutil.copy2(CHROME_P1_BM, CHROME_P1_BAK)
        print(f"Created Chrome backup at {CHROME_P1_BAK}")

    id_tracker = {"id": 100}
    def next_id():
        id_tracker["id"] += 1
        return str(id_tracker["id"])

    now_str = str(int(time.time() * 1000000))
    def to_chrome_bm(b):
        return {
            "date_added": b.get("add_date", now_str),
            "date_last_used": "0",
            "id": next_id(),
            "name": get_title_with_badges(b),
            "type": "url",
            "url": b["url"]
        }

    chrome_pillars = []
    chrome_pillars.append({
        "date_added": now_str,
        "date_last_used": "0",
        "date_modified": now_str,
        "id": next_id(),
        "name": "⭐ Quick Access (Most Frequently Used)",
        "type": "folder",
        "children": [to_chrome_bm(b) for b in top_visited]
    })
    chrome_pillars.append({
        "date_added": now_str,
        "date_last_used": "0",
        "date_modified": now_str,
        "id": next_id(),
        "name": "🕒 Recently Added",
        "type": "folder",
        "children": [to_chrome_bm(b) for b in top_recent]
    })

    for pillar in sorted(tree.keys()):
        subs = tree[pillar]
        pillar_name = re.sub(r"^\d+\.\s*", "", pillar)
        p_total = sum(len(items) for items in subs.values())
        p_node = {
            "date_added": now_str,
            "date_last_used": "0",
            "date_modified": now_str,
            "id": next_id(),
            "name": f"{pillar_name} ({p_total})",
            "type": "folder",
            "children": []
        }
        for subcat in sorted(subs.keys()):
            items = subs[subcat]
            s_node = {
                "date_added": now_str,
                "date_last_used": "0",
                "date_modified": now_str,
                "id": next_id(),
                "name": f"{subcat} ({len(items)})",
                "type": "folder",
                "children": [to_chrome_bm(b) for b in items]
            }
            p_node["children"].append(s_node)
        chrome_pillars.append(p_node)

    p1_data = {
        "checksum": "",
        "roots": {
            "bookmark_bar": {
                "children": chrome_pillars,
                "date_added": now_str,
                "date_last_used": "0",
                "date_modified": now_str,
                "id": "1",
                "name": "Bookmarks Bar",
                "type": "folder"
            },
            "other": {"children": [], "date_added": "0", "date_last_used": "0", "date_modified": "0", "id": "2", "name": "Other Bookmarks", "type": "folder"},
            "synced": {"children": [], "date_added": "0", "date_last_used": "0", "date_modified": "0", "id": "3", "name": "Mobile Bookmarks", "type": "folder"}
        },
        "version": 1
    }

    try:
        with open(CHROME_P1_BM, "w", encoding="utf-8") as f:
            json.dump(p1_data, f, indent=3)
        print("Successfully updated Chrome Profile 1 Bookmarks.")
    except Exception as e:
        print(f"Note: Could not update Chrome Profile 1 file directly ({e}). HTML and catalog were fully updated.")

if __name__ == "__main__":
    main()
