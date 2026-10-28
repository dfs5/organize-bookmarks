#!/usr/bin/env python3
"""
ai_agent_server.py - Local AI Search & Assistant Backend for Bookmarks Showcase.
Provides intelligent intent extraction, hybrid BM25 / tag scoring, contextual synthesis,
and optional generative LLM completions (Google Gemini / local Ollama).

Zero external pip dependencies required. Uses Python standard library.
"""

import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)
_parent_dir = os.path.dirname(_script_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

import json
import re
import math
import time
import threading
from urllib.parse import urlparse, parse_qs
import urllib.request
import urllib.parse
import subprocess
import ssl
import hashlib
from collections import Counter
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

def load_config():
    """Loads and parses ai_agent_server.conf with line comments (# and //) stripped."""
    config_path = None
    if "--config" in sys.argv:
        idx = sys.argv.index("--config")
        if idx + 1 < len(sys.argv):
            config_path = sys.argv[idx + 1]
    if not config_path:
        config_path = os.environ.get("AI_SERVER_CONFIG")
    if not config_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(script_dir, "ai_agent_server.conf"),
            os.path.join(script_dir, "ai_agent_server", "ai_agent_server.conf"),
            os.path.join(os.path.dirname(script_dir), "ai_agent_server", "ai_agent_server.conf"),
            os.path.join(script_dir, "ai_agent_server.conf.example"),
            os.path.join(script_dir, "ai_agent_server", "ai_agent_server.conf.example"),
            os.path.join(os.path.dirname(script_dir), "ai_agent_server", "ai_agent_server.conf.example"),
        ]
        config_path = next((c for c in candidates if os.path.exists(c)), os.path.join(os.getcwd(), "ai_agent_server.conf"))

    config_dir = os.path.dirname(os.path.abspath(config_path))
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    cleaned = []
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            cleaned.append(line)
    cfg = json.loads("".join(cleaned))
    cfg["_config_path"] = config_path
    cfg["_config_dir"] = config_dir
    return cfg

def resolve_path(base_dir, p):
    if not p:
        return ""
    if os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(base_dir, p))

# Load configuration from ai_agent_server.conf
CFG = load_config()
CONFIG_DIR = CFG.get("_config_dir", os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = CFG.get("_config_path", "")

SERVER_CFG = CFG.get("server", {})
PORT = int(os.environ.get("BOOKMARKS_AI_PORT", SERVER_CFG.get("port", 8765)))
HOST = SERVER_CFG.get("host", "0.0.0.0")
CATALOG_PATH = resolve_path(CONFIG_DIR, SERVER_CFG.get("catalog_path", "../bookmarks_catalog.json"))
if not os.path.exists(CATALOG_PATH):
    _example_cat = resolve_path(CONFIG_DIR, "../bookmarks_catalog.example.json")
    if os.path.exists(_example_cat):
        CATALOG_PATH = _example_cat
CONTENT_CACHE_PATH = resolve_path(CONFIG_DIR, SERVER_CFG.get("content_cache_path", "./bookmarks_content_cache.json"))
SHOWCASE_PATH = resolve_path(CONFIG_DIR, SERVER_CFG.get("showcase_path", "../bookmarks_showcase.html"))

LLM_CFG = CFG.get("llm", {})
GEMINI_CFG = LLM_CFG.get("gemini", {})
OLLAMA_CFG = LLM_CFG.get("ollama", {})

SCRAPER_CFG = CFG.get("scraper", {})
MAX_SCRAPER_WORKERS = int(SCRAPER_CFG.get("max_workers", 6))
SCRAPER_TIMEOUT = float(SCRAPER_CFG.get("timeout_seconds", 3.5))
SKIPPED_DOMAINS = [d.lower() for d in SCRAPER_CFG.get("skipped_domains", ["sharepoint.com", "service-now.com", "salesforce.com", "tryopine.com", "highspot.com", "workday.com", "benevity.org"])]
SKIPPED_EXTENSIONS = [e.lower() for e in SCRAPER_CFG.get("skipped_extensions", [".pptx", ".xlsx", ".docx", ".pdf", ".zip"])]

RANKING_CFG = CFG.get("ranking", {})
BM25_K1 = float(RANKING_CFG.get("bm25_k1", 1.5))
BM25_B = float(RANKING_CFG.get("bm25_b", 0.75))
VISIT_BOOST_FACTOR = float(RANKING_CFG.get("visit_boost_factor", 1.5))
MAX_CANDIDATES = int(RANKING_CFG.get("max_candidates", 20))
DEFAULT_LIMIT = int(RANKING_CFG.get("default_limit", 10))

COMMON_TYPOS = CFG.get("common_typos", {})
PRODUCT_KEYWORDS = CFG.get("product_keywords", {})
TOPIC_KEYWORDS = CFG.get("topic_keywords", {})
SOURCE_TYPE_KEYWORDS = CFG.get("source_type_keywords", {})

PRODUCT_SCOPES = {
    "adsp": {
        "name": "ADSP (All Products)",
        "short_name": "ADSP (All)",
        "icon": "🌐",
        "tags": set(),
        "keywords": [],
        "instruction": "The search scope is ADSP (All Products across the entire F5 Application Delivery & Security Platform portfolio, including BIG-IP, NGINX, F5 Distributed Cloud, and AI solutions). Search across all products without restriction."
    },
    "aisp": {
        "name": "AISP (All AI Products)",
        "short_name": "AISP (All AI)",
        "icon": "🧠",
        "tags": {"f5-ai-gateway", "f5-workforce-ai-security", "ai-workloads", "ai-guardrails"},
        "keywords": [
            "ai gateway", "ai-gateway", "f5 ai gateway",
            "workforce ai", "surepath", "surepath ai", "f5 workforce ai", "shadow ai",
            "guardrail", "guardrails", "calypso", "calypsoai", "prompt security",
            "genai", "llm", "owasp llm", "prompt injection", "agentic ai", "prompt protection"
        ],
        "instruction": "The search scope is AISP (All AI Products across F5's entire AI portfolio, including F5 AI Gateway, Workforce AI Security, SurePath, AI Guardrails, and CalypsoAI). Focus answers and recommended bookmarks strictly on AI, GenAI, and LLM security and optimization solutions."
    },
    "big-ip": {
        "name": "BIG-IP & TMOS",
        "short_name": "BIG-IP",
        "icon": "⚡",
        "tags": {"big-ip", "rseries", "velos", "BIG-IP LTM"},
        "keywords": ["big-ip", "bigip", "tmos", "ltm", "apm", "asm", "awaf", "gtm", "big-iq", "rseries", "velos", "f5os"],
        "instruction": "The search scope is strictly focused on F5 BIG-IP, TMOS, LTM, APM, ASM/AWAF, BIG-IQ, rSeries, and VELOS architectures. Focus answers and recommended bookmarks strictly on BIG-IP and TMOS solutions."
    },
    "nginx": {
        "name": "NGINX Ecosystem",
        "short_name": "NGINX",
        "icon": "🟩",
        "tags": {"nginx", "nginx-plus", "nginx-open-source"},
        "keywords": ["nginx", "nginx plus", "nap", "nginx app protect", "nic", "nginx ingress", "gateway fabric", "instance manager", "njs"],
        "instruction": "The search scope is strictly focused on the NGINX ecosystem (NGINX Plus, NGINX App Protect WAF/DoS, NGINX Ingress Controller, NGINX Gateway Fabric, and NGINX Instance Manager). Focus answers and recommended bookmarks strictly on NGINX."
    },
    "f5xc": {
        "name": "F5 Distributed Cloud (XC)",
        "short_name": "F5 XC",
        "icon": "☁️",
        "tags": {"f5-xc", "distributed-cloud-services"},
        "keywords": ["f5-xc", "f5 xc", "f5xc", "distributed cloud", "volterra", "xc platform", "waap", "service policy", "multi-cloud"],
        "instruction": "The search scope is strictly focused on F5 Distributed Cloud (XC) Services (formerly Volterra), XC WAAP, Multi-Cloud App Connect, XC Service Policies, and cloud site management. Focus answers and recommended bookmarks strictly on F5 XC."
    },
    "ai-gateway": {
        "name": "F5 AI Gateway",
        "short_name": "AI Gateway",
        "icon": "🤖",
        "tags": {"f5-ai-gateway"},
        "keywords": ["ai-gateway", "ai gateway", "f5 ai gateway", "govern secure optimize ai", "ai routing"],
        "instruction": "The search scope is strictly focused on F5 AI Gateway (governing, securing, and optimizing AI and LLM inference traffic). Focus answers and recommended bookmarks strictly on F5 AI Gateway."
    },
    "ai-workforce": {
        "name": "F5 Workforce AI Security",
        "short_name": "AI Workforce",
        "icon": "🛡️",
        "tags": {"f5-workforce-ai-security"},
        "keywords": ["workforce ai", "surepath", "surepath ai", "f5 workforce ai", "genai traffic"],
        "instruction": "The search scope is strictly focused on F5 Workforce AI Security and SurePath AI traffic flows. Focus answers and recommended bookmarks strictly on Workforce AI and SurePath."
    },
    "ai-guardrails": {
        "name": "AI Guardrails & CalypsoAI",
        "short_name": "AI Guardrails",
        "icon": "🔒",
        "tags": {"ai-workloads"},
        "keywords": ["guardrail", "guardrails", "calypso", "calypsoai", "prompt security", "prompt history", "scanner"],
        "instruction": "The search scope is strictly focused on AI Guardrails and CalypsoAI (prompt defense, real-time scanners, prompt history auditing, and LLM security). Focus answers and recommended bookmarks strictly on AI Guardrails and CalypsoAI."
    }
}

def resolve_vertex_model(model_name):
    """
    Maps user-facing model aliases (e.g. 'Gemini 3.8 Flash (Medium)')
    to the active Google Cloud / Vertex AI endpoint model identifier.
    """
    raw = (model_name or "").strip()
    low = raw.lower()
    if "flash" in low:
        return "gemini-2.5-flash"
    elif "pro" in low:
        return "gemini-2.5-pro"
    return raw or "gemini-2.5-flash"

def get_vertex_endpoint(location, project_id, model_name):
    """
    Constructs the correct Vertex AI endpoint URL.
    Handles 'global' location (uses aiplatform.googleapis.com)
    and regional locations (e.g. us-central1-aiplatform.googleapis.com).
    """
    target_model = resolve_vertex_model(model_name)
    loc = (location or "global").strip()
    host = "aiplatform.googleapis.com" if loc in ["global", ""] else f"{loc}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project_id}/locations/{loc}/publishers/google/models/{target_model}:generateContent"

LOG_CFG = CFG.get("logging", {})
COMM_LOG_PATH = resolve_path(CONFIG_DIR, LOG_CFG.get("log_file", "./ai_communication.log"))
COMM_LOG_HEALTHCHECK = bool(LOG_CFG.get("log_healthcheck", False))

class CommunicationLogger:
    """
    Logs full content of communications:
      1. Website frontend to ai_agent_server (requests & responses)
      2. ai_agent_server to LLMs (prompts & model completions)

    Log file writing is ONLY performed when explicitly enabled via command:
      - CLI flags: --log-traffic / --enable-logging / --debug
      - Script: ./run_ai_server.sh --enable-logging (or --disable-logging)
      - API: POST /api/logging {"enabled": true}
      - Environment: AI_SERVER_LOG_TRAFFIC=1
    """
    def __init__(self, log_path, enabled=False, log_healthcheck=False):
        self.log_path = log_path
        self._enabled = bool(enabled)
        self._log_healthcheck = bool(log_healthcheck)
        self._lock = threading.Lock()
        self._req_counter = 0

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, state: bool) -> bool:
        with self._lock:
            prev = self._enabled
            self._enabled = bool(state)
            if self._enabled and not prev:
                self._write_banner(">>> COMMUNICATION LOGGING ENABLED VIA COMMAND <<<")
            elif not self._enabled and prev:
                self._write_banner(">>> COMMUNICATION LOGGING DISABLED VIA COMMAND <<<")
        return self._enabled

    def next_request_id(self, prefix="REQ") -> str:
        with self._lock:
            self._req_counter += 1
            return f"{prefix}-{self._req_counter:04d}"

    def _sanitize_headers(self, headers_dict) -> dict:
        if not headers_dict:
            return {}
        sanitized = {}
        for k, v in headers_dict.items():
            k_low = k.lower()
            if k_low == "authorization":
                s_val = str(v)
                if s_val.lower().startswith("bearer "):
                    tok = s_val[7:].strip()
                    masked = tok[:6] + "..." + tok[-4:] if len(tok) > 12 else "***[REDACTED]"
                    sanitized[k] = f"Bearer {masked}"
                else:
                    sanitized[k] = "***[REDACTED]"
            elif any(sub in k_low for sub in ["key", "secret", "token", "password"]):
                s_val = str(v)
                sanitized[k] = s_val[:4] + "...[REDACTED]" if len(s_val) > 8 else "***[REDACTED]"
            else:
                sanitized[k] = str(v)
        return sanitized

    def _sanitize_url(self, url: str) -> str:
        if not url:
            return ""
        return re.sub(r'([?&]key=)([^&]+)', r'\1\2[REDACTED]', url)

    def _write_banner(self, title: str):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        banner = (
            "\n"
            + "=" * 80 + "\n"
            + f"[{ts}] {title}\n"
            + f"Log File: {self.log_path}\n"
            + "=" * 80 + "\n\n"
        )
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(banner)
                f.flush()
        except Exception as e:
            sys.stderr.write(f"CommunicationLogger write banner error: {e}\n")

    def _write_entry(self, entry: str):
        if not self._enabled:
            return
        with self._lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(entry)
                    if not entry.endswith("\n"):
                        f.write("\n")
                    f.flush()
            except Exception as e:
                sys.stderr.write(f"CommunicationLogger write error: {e}\n")

    def log_frontend_request(self, req_id: str, method: str, path: str, headers, query_params=None, body=None):
        if not self._enabled:
            return
        is_healthcheck = (path == "/api/status")
        if is_healthcheck and not self._log_healthcheck:
            return

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        headers_dict = self._sanitize_headers(dict(headers)) if headers else {}
        filtered_headers = {k: v for k, v in headers_dict.items() if k.lower() in ["content-type", "user-agent", "origin", "host", "accept"]}

        body_str = ""
        if body is not None:
            if isinstance(body, (dict, list)):
                body_str = json.dumps(body, indent=2, ensure_ascii=False)
            else:
                body_str = str(body)

        entry = (
            "=" * 80 + "\n"
            + f"[{ts}] 🌐 [FRONTEND ➔ AI_SERVER]  Request ID: {req_id}\n"
            + f"HTTP Method : {method}\n"
            + f"Request Path: {path}\n"
        )
        if query_params:
            entry += f"Query Params: {json.dumps(query_params, ensure_ascii=False)}\n"
        if filtered_headers:
            entry += f"Headers     : {json.dumps(filtered_headers, ensure_ascii=False)}\n"
        if body_str:
            entry += f"Request Body:\n{body_str}\n"
        entry += "-" * 80 + "\n"
        self._write_entry(entry)

    def log_frontend_response(self, req_id: str, method: str, path: str, status_code: int, content_type: str, body_data, duration_s: float):
        if not self._enabled:
            return
        is_healthcheck = (path == "/api/status")
        if is_healthcheck and not self._log_healthcheck:
            return

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        body_str = ""
        if body_data is not None:
            if isinstance(body_data, (dict, list)):
                body_str = json.dumps(body_data, indent=2, ensure_ascii=False)
            else:
                body_str = str(body_data)

        entry = (
            f"[{ts}] 💻 [AI_SERVER ➔ FRONTEND]  Response ID: {req_id}\n"
            + f"HTTP Status : {status_code} ({'OK' if status_code < 400 else 'ERROR'})\n"
            + f"Duration    : {duration_s:.3f}s\n"
            + f"Content-Type: {content_type}\n"
        )
        if body_str:
            entry += f"Response Body:\n{body_str}\n"
        entry += "=" * 80 + "\n\n"
        self._write_entry(entry)

    def log_llm_request(self, call_id: str, provider: str, model: str, url: str, headers: dict, payload: dict):
        if not self._enabled:
            return
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        sanitized_headers = self._sanitize_headers(headers)
        sanitized_url = self._sanitize_url(url)
        payload_str = json.dumps(payload, indent=2, ensure_ascii=False) if isinstance(payload, (dict, list)) else str(payload)

        entry = (
            "▶" * 40 + "\n"
            + f"[{ts}] 🤖 [AI_SERVER ➔ LLM]  Call ID: {call_id}\n"
            + f"LLM Provider: {provider.upper()}\n"
            + f"Target Model: {model}\n"
            + f"Endpoint URL: {sanitized_url}\n"
            + f"HTTP Headers: {json.dumps(sanitized_headers, ensure_ascii=False)}\n"
            + f"Request Payload (Prompt & Parameters):\n{payload_str}\n"
            + "┄" * 80 + "\n"
        )
        self._write_entry(entry)

    def log_llm_response(self, call_id: str, provider: str, model: str, status_code: int, response_data, duration_s: float):
        if not self._enabled:
            return
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        resp_str = json.dumps(response_data, indent=2, ensure_ascii=False) if isinstance(response_data, (dict, list)) else str(response_data)

        entry = (
            f"[{ts}] 🧠 [LLM ➔ AI_SERVER]  Call ID: {call_id}\n"
            + f"LLM Provider: {provider.upper()}\n"
            + f"Target Model: {model}\n"
            + f"HTTP Status : {status_code}\n"
            + f"Latency     : {duration_s:.3f}s\n"
            + f"Response Body (Model Output):\n{resp_str}\n"
            + "◀" * 40 + "\n\n"
        )
        self._write_entry(entry)

    def log_llm_error(self, call_id: str, provider: str, model: str, status_code, error_msg: str, duration_s: float):
        if not self._enabled:
            return
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"[{ts}] ⚠️ [LLM ➔ AI_SERVER] ERROR  Call ID: {call_id}\n"
            + f"LLM Provider: {provider.upper()}\n"
            + f"Target Model: {model}\n"
            + f"HTTP Status : {status_code}\n"
            + f"Latency     : {duration_s:.3f}s\n"
            + f"Error Details:\n{error_msg}\n"
            + "◀" * 40 + "\n\n"
        )
        self._write_entry(entry)

# Initialize logger with default disabled state unless explicitly enabled via command / env / conf
cli_traffic_log = any(arg in sys.argv for arg in ["--log-traffic", "--enable-logging", "--debug"])
env_traffic_log = bool(os.environ.get("AI_SERVER_LOG_TRAFFIC") or os.environ.get("AI_LOG_COMMUNICATION"))
initial_logging_enabled = cli_traffic_log or env_traffic_log or bool(LOG_CFG.get("traffic_logging", False))

comm_logger = CommunicationLogger(
    log_path=COMM_LOG_PATH,
    enabled=initial_logging_enabled,
    log_healthcheck=COMM_LOG_HEALTHCHECK
)

def _build_http_opener():
    """Builds a urllib opener bypassing HTTP proxies and relaxing Python 3.13's strict X509 key-usage flag."""
    ctx = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ctx),
    )

def send_llm_request(provider: str, model_name: str, url: str, payload: dict, headers: dict = None, timeout: float = 10.0) -> dict:
    """
    Centralized HTTP dispatcher for all LLM API calls.
    Captures full request and response traffic and logs to communication log when enabled.
    """
    call_id = comm_logger.next_request_id("LLM")
    effective_headers = dict(headers or {})
    if "Content-Type" not in effective_headers:
        effective_headers["Content-Type"] = "application/json"

    comm_logger.log_llm_request(call_id, provider, model_name, url, effective_headers, payload)

    opener = _build_http_opener()
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=effective_headers)

    t0 = time.time()
    try:
        with opener.open(req, timeout=timeout) as resp:
            dur = round(time.time() - t0, 3)
            raw_body = resp.read().decode("utf-8")
            status_code = getattr(resp, "status", 200)
            try:
                parsed_json = json.loads(raw_body)
                comm_logger.log_llm_response(call_id, provider, model_name, status_code, parsed_json, dur)
                return parsed_json
            except json.JSONDecodeError:
                comm_logger.log_llm_response(call_id, provider, model_name, status_code, raw_body, dur)
                return {"raw_text": raw_body}
    except Exception as e:
        dur = round(time.time() - t0, 3)
        status_code = getattr(e, "code", "ERROR")
        err_msg = str(e)
        if hasattr(e, "read"):
            try:
                err_body = e.read().decode("utf-8")
                err_msg += f" | Response Body: {err_body}"
            except Exception:
                pass
        comm_logger.log_llm_error(call_id, provider, model_name, status_code, err_msg, dur)
        raise

class GoogleAuthHelper:
    """
    Zero-dependency Google Cloud authentication helper.
    Supports Project ID login via ADC (Application Default Credentials),
    OAuth2 token refresh, and gcloud CLI fallbacks without external pip packages.
    """
    _cached_token = None
    _token_expiry = 0

    @classmethod
    def get_project_id(cls, configured_id=None):
        if configured_id and configured_id not in ["auto", "", "YOUR_GCP_PROJECT_ID", "<YOUR_GCP_PROJECT_ID>"]:
            return configured_id
        for env_k in ["GOOGLE_CLOUD_PROJECT", "GCP_PROJECT", "PROJECT_ID"]:
            v = os.environ.get(env_k)
            if v:
                return v
        adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
        if os.path.exists(adc_path):
            try:
                with open(adc_path, "r") as f:
                    data = json.load(f)
                    if data.get("quota_project_id"):
                        return data["quota_project_id"]
            except Exception:
                pass
        for gcloud_bin in ["gcloud", os.path.expanduser("~/Downloads/google-cloud-sdk/bin/gcloud"), os.path.expanduser("~/google-cloud-sdk/bin/gcloud"), "/opt/homebrew/bin/gcloud", "/usr/local/bin/gcloud"]:
            try:
                out = subprocess.check_output([gcloud_bin, "config", "get-value", "project"], stderr=subprocess.DEVNULL).decode().strip()
                if out and "unset" not in out:
                    return out
            except Exception:
                continue
        return None

    @classmethod
    def get_token(cls):
        now = time.time()
        if cls._cached_token and now < cls._token_expiry - 60:
            return cls._cached_token

        env_token = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
        if env_token:
            return env_token

        adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
        if os.path.exists(adc_path):
            try:
                with open(adc_path, "r") as f:
                    adc = json.load(f)
                client_id = adc.get("client_id")
                client_secret = adc.get("client_secret")
                refresh_token = adc.get("refresh_token")
                if refresh_token and client_id:
                    data = urllib.parse.urlencode({
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token"
                    }).encode()
                    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
                    opener = _build_http_opener()
                    with opener.open(req, timeout=5) as resp:
                        res = json.loads(resp.read().decode())
                        cls._cached_token = res["access_token"]
                        cls._token_expiry = now + int(res.get("expires_in", 3600))
                        return cls._cached_token
            except Exception:
                pass

        for gcloud_bin in ["gcloud", os.path.expanduser("~/Downloads/google-cloud-sdk/bin/gcloud"), os.path.expanduser("~/google-cloud-sdk/bin/gcloud"), "/opt/homebrew/bin/gcloud", "/usr/local/bin/gcloud"]:
            try:
                out = subprocess.check_output([gcloud_bin, "auth", "application-default", "print-access-token"], stderr=subprocess.DEVNULL).decode().strip()
                if out:
                    token = out.split()[0]
                    cls._cached_token = token
                    cls._token_expiry = now + 3000
                    return cls._cached_token
            except Exception:
                continue

        return None

class HtmlTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ["script", "style", "noscript", "header", "footer", "nav", "svg", "button"]:
            self.skip = True

    def handle_endtag(self, tag):
        if tag.lower() in ["script", "style", "noscript", "header", "footer", "nav", "svg", "button"]:
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            s = data.strip()
            if s:
                self.text_parts.append(s)

    def get_text(self):
        raw = " ".join(self.text_parts)
        return re.sub(r"\s+", " ", raw).strip()


class ContentInspector:
    """
    Deep Content Verification Subsystem:
    1. Understands the intent.
    2. Opens related bookmarks and browses real content in parallel (using local caching).
    3. Evaluates if the content genuinely addresses the intent (discarding false positives).
    4. Extracts concrete evidence excerpts and returns only verified matches.
    """
    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.cache = {}
        self.cache_mtime = 0
        self.lock = threading.RLock()
        self.load_cache()

    def load_cache(self):
        with self.lock:
            if os.path.exists(self.cache_path):
                try:
                    mtime = os.path.getmtime(self.cache_path)
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        self.cache = json.load(f)
                    self.cache_mtime = mtime
                except Exception as e:
                    print(f"Warning: Failed to load content cache: {e}")
                    self.cache = {}

    def reload_if_changed(self):
        if not os.path.exists(self.cache_path):
            return
        try:
            mtime = os.path.getmtime(self.cache_path)
            if mtime > self.cache_mtime or not self.cache:
                self.load_cache()
        except Exception:
            pass

    def save_cache(self):
        with self.lock:
            try:
                with open(self.cache_path + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(self.cache, f, indent=2, ensure_ascii=False)
                os.replace(self.cache_path + ".tmp", self.cache_path)
                self.cache_mtime = os.path.getmtime(self.cache_path)
            except Exception as e:
                print(f"Warning: Failed to save content cache: {e}")

    def fetch_url(self, url, timeout=3.5):
        """
        Strictly returns website text from the /browser-verified content cache.
        Never uses headless browser or raw urllib HTTP requests to inspect websites.
        """
        with self.lock:
            entry = self.cache.get(url)
            if not entry:
                alt = url.rstrip("/") if url.endswith("/") else (url + "/")
                entry = self.cache.get(alt)
            if isinstance(entry, dict):
                text = entry.get("text", "")
                # Guard against MyF5 SPA cross-article cache contamination
                m_url = re.search(r"/article/(K\d+)", url, re.IGNORECASE)
                if m_url and text:
                    expected_k = m_url.group(1).upper()
                    m_txt = re.search(r"\b(K\d{4,10})\s*:", text[:250], re.IGNORECASE)
                    if m_txt and m_txt.group(1).upper() != expected_k:
                        return url, "", "contaminated_k_mismatch"
                return url, text, "cached"
        return url, "", "requires_browser_subagent"

    def extract_relevant_excerpt(self, text, keywords, fallback=""):
        # Filter out any SPA error shells
        if any(err in (text or "").lower() for err in ["sorry to interrupt", "css error", "javascript is required"]):
            text = ""
        if not text and fallback:
            text = fallback

        for kw in keywords:
            pattern = r"([^.?!]{10,120}" + re.escape(kw) + r"[^.?!]{10,140}[.?!])"
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                clean = re.sub(r"\s+", " ", m.group(0)).strip()
                if len(clean) > 30 and not any(err in clean.lower() for err in ["sorry to interrupt", "css error"]):
                    return clean
        m = re.search(r"([^.?!]{30,220}[.?!])", text)
        if m:
            clean = re.sub(r"\s+", " ", m.group(0)).strip()
            if not any(err in clean.lower() for err in ["sorry to interrupt", "css error"]):
                return clean
        if text and not any(err in text.lower() for err in ["sorry to interrupt", "css error"]):
            return text[:180].strip() + ("..." if len(text) > 180 else "")
        return (fallback[:180].strip() + ("..." if len(fallback) > 180 else "")) if fallback else ""

    def analyze_relevance(self, bm, text, intent):
        """
        Step 3: Browse content to understand if it relates to the intent.
        Returns: (is_relevant: bool, content_score: float, excerpt: str, reason: str)
        """
        title = bm.get("title", "")
        desc = bm.get("description", "")
        summary = bm.get("content_summary", "")
        notes = bm.get("notes", "")
        is_vpn = bm.get("requires_vpn", False)

        # Discard SPA error text if present
        if any(err in (text or "").lower() for err in ["sorry to interrupt", "css error", "javascript is required"]):
            text = ""

        # If page body is empty or stub, supplement with content_summary and notes
        if not text.strip() and (summary or notes):
            text = f"{summary} {notes}".strip()

        # Internal / VPN protected page where HTTP fetch failed or returned auth redirect/stub
        text_lower = (text or "").lower()
        is_stub = len(text_lower.strip()) < 80 or any(s in text_lower for s in ["redirecting", "sign in to your account", "login", "please wait..."])
        if is_stub:
            text_lower = f"{text_lower} {title.lower()} {desc.lower()} {summary.lower()} {notes.lower()} {' '.join(bm.get('legacy_path', [])).lower()}"
        is_migration = intent.get("is_migration", False)
        mig_target = intent.get("migration_target")
        mig_source = intent.get("migration_source")

        # Internal / VPN protected page or HTTP fetch unavailable
        if not text:
            if is_vpn or any(st in bm.get("tags", {}).get("source_types", []) for st in ["internal-portal", "dashboard"]):
                excerpt = f"Internal Enterprise Resource: {desc or title}"
                return True, 15.0, excerpt, "Verified (Internal VPN-protected portal)"
            
            if is_migration and mig_target == "f5-xc":
                url_low = bm.get("url", "").lower()
                title_low = title.lower()
                if "f5-xc" in bm.get("tags", {}).get("products", []) and ("guide-convert" in url_low or "ps-convert" in url_low or "conversion" in title_low):
                    excerpt = desc or f"Official F5 XC conversion reference for {title}"
                    return True, 45.0, excerpt, "Verified: Official F5 XC Conversion Guide"

            q_tokens = [w for w in re.findall(r"[a-z0-9_\-]+", intent.get("normalized_query", "")) if len(w) > 3]
            if any(t in title.lower() for t in q_tokens) or bm.get("_candidate_score", 0) > 25:
                return True, 12.0, desc or title, "Verified via catalog reference"
            return False, 0.0, None, "Discarded: Content unavailable and metadata does not match"

        # Intent: Migration (e.g. iRules to XC platform)
        if is_migration:
            if mig_target == "f5-xc":
                has_xc = bool(re.search(r"\b(distributed cloud|f5-xc|f5 xc|volterra|service policy|origin pool|vk8s)\b|\bxc\b", text_lower))
                has_mig = bool(re.search(r"\b(convert|conversion|migrate|migration|transition|replace|replacing|ps-convert)\b", text_lower))
                has_source = bool(re.search(r"\b(irules?|tcl|traffic policy|big-ip|virtual server)\b", text_lower))

                # If candidate has NO mention of XC or Distributed Cloud in its actual page text, DISCARD!
                if not has_xc:
                    return False, 0.0, None, "Discarded: Page body does not discuss F5 XC or Distributed Cloud"

                score = 25.0
                if has_xc: score += 15.0
                if has_mig: score += 20.0
                if has_source: score += 15.0

                kw_list = ["ps-convert", "convert", "conversion", "service policy", "irule", "traffic policy", "distributed cloud"]
                excerpt = self.extract_relevant_excerpt(text, kw_list, fallback=summary or desc)
                return True, score, excerpt, "Verified: Page content addresses XC migration/conversion"

            elif mig_target == "nginx":
                has_nginx = bool(re.search(r"\bnginx\b", text_lower))
                if not has_nginx:
                    return False, 0.0, None, "Discarded: Page body does not discuss NGINX"
                score = 30.0
                excerpt = self.extract_relevant_excerpt(text, ["nginx", "migrate", "convert"], fallback=summary or desc)
                return True, score, excerpt, "Verified: NGINX transition content"

        # LLM Must-Mention Verification (if LLM identified mandatory concepts)
        must_mention = intent.get("must_mention", [])
        if must_mention:
            has_must = any(m in text_lower for m in must_mention)
            if not has_must:
                return False, 0.0, None, f"Discarded: Page body does not discuss required concept ({', '.join(must_mention)})"

        # General Intent Verification (topics, products, concepts, search keywords)
        concepts = list(set(intent.get("concepts", []) + intent.get("search_keywords", [])))
        norm_query = intent.get("normalized_query", "")
        query_words = [w for w in re.findall(r"[a-z0-9_\-]+", norm_query) if len(w) > 3 and w not in {"what", "show", "find", "want", "need", "like", "with"}]

        matched_concepts = [c for c in concepts if c in text_lower and re.search(r"\b" + re.escape(c) + r"\b", text_lower)]
        matched_words = [w for w in query_words if w in text_lower and re.search(r"\b" + re.escape(w) + r"\b", text_lower)]

        if not matched_concepts and not matched_words:
            if any(w in title.lower() for w in query_words):
                excerpt = self.extract_relevant_excerpt(text, query_words, fallback=summary or desc) or desc
                return True, 10.0, excerpt, "Matched primarily on title"
            return False, 0.0, None, "Discarded: Page content does not contain relevant query concepts"

        score = (len(matched_concepts) * 15.0) + (len(matched_words) * 5.0)
        excerpt = self.extract_relevant_excerpt(text, matched_concepts or query_words, fallback=summary or desc)
        return True, score, excerpt, "Verified: Relevant content found in page body"

    def verify_candidates(self, candidates, intent, limit=None):
        """
        Step 3 & 4: Opens candidate bookmarks from the verified cache,
        verifies relevance to intent, and returns ONLY bookmarks with relevant content.
        Never overwrites bookmarks_content_cache.json with stale in-memory state.
        """
        if limit is None:
            limit = DEFAULT_LIMIT
        self.reload_if_changed()

        strip_keys = {"_tokens", "_token_counts", "_id", "_candidate_score", "icon"}
        verified = []
        for bm in candidates:
            url = bm["url"]
            _, text, _ = self.fetch_url(url)
            is_relevant, content_score, excerpt, reason = self.analyze_relevance(bm, text, intent)

            # Step 4: Display ONLY these bookmarks where relevant content was found
            if is_relevant:
                bm_copy = {k: v for k, v in bm.items() if k not in strip_keys}
                bm_copy["content_verified"] = True
                bm_copy["content_score"] = round(content_score + bm.get("_candidate_score", 0), 2)
                bm_copy["content_excerpt"] = excerpt
                bm_copy["content_reason"] = reason
                verified.append(bm_copy)

        # Sort verified results by content relevance score
        verified.sort(key=lambda x: x.get("content_score", 0), reverse=True)
        return verified[:limit]


# LLM-Based Intent Extractor
class LLMIntentExtractor:
    """
    Leverages LLMs (Local Ollama gemma3:4b or Google Gemini API) to understand
    the user's underlying search intent dynamically, eliminating hardcoded rules
    and static instruction files.
    """
    def __init__(self, ollama_url=None, preferred_ollama_model=None):
        self.ollama_url = (ollama_url or OLLAMA_CFG.get("url", "http://127.0.0.1:11434")).rstrip("/")
        self.preferred_model = preferred_ollama_model or OLLAMA_CFG.get("preferred_model", "gemma3:4b")
        api_key_env = GEMINI_CFG.get("api_key_env", "GEMINI_API_KEY")
        self.gemini_key = os.environ.get(api_key_env)
        self.gemini_model = GEMINI_CFG.get("model", "Gemini 3.8 Flash (Medium)")
        self.gemini_project = GoogleAuthHelper.get_project_id(GEMINI_CFG.get("project_id"))
        self.gemini_location = GEMINI_CFG.get("location", "us-central1")
        self._cache = {}
        self._active_model = None
        self._detect_engine()

    def _detect_engine(self):
        # 1. Google Cloud Project ID (Vertex AI with ADC / OAuth token)
        if self.gemini_project and GoogleAuthHelper.get_token():
            self._active_model = f"vertex/{self.gemini_model}"
            return
        # 2. Google Gemini Developer API Key
        if self.gemini_key:
            self._active_model = f"gemini/{self.gemini_model}"
            return
        # 3. Local Ollama GPU Engine
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "BookmarksAI"})
            opener = _build_http_opener()
            with opener.open(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in data.get("models", [])]
                if self.preferred_model in models:
                    self._active_model = f"ollama/{self.preferred_model}"
                elif any("gemma" in m for m in models):
                    gemma_m = [m for m in models if "gemma" in m][0]
                    self._active_model = f"ollama/{gemma_m}"
                elif models:
                    self._active_model = f"ollama/{models[0]}"
        except Exception:
            self._active_model = None

    def get_status(self):
        if not self._active_model:
            self._detect_engine()
        engine_type = "Heuristic Rule Fallback"
        if self._active_model:
            if self._active_model.startswith("vertex/"):
                engine_type = f"Google Vertex AI [Project: {self.gemini_project}]"
            elif self._active_model.startswith("gemini/"):
                engine_type = "Google Gemini Cloud (API Key)"
            elif self._active_model.startswith("ollama/"):
                engine_type = "Local GPU LLM (Ollama)"
        return {
            "active": bool(self._active_model),
            "model": self._active_model or "heuristic-fallback",
            "type": engine_type
        }

    def _normalize_target(self, target_str):
        if not target_str:
            return None
        t = str(target_str).lower().strip()
        if any(x in t for x in ["xc", "distributed cloud", "volterra"]):
            return "f5-xc"
        if "nginx" in t:
            return "nginx"
        if any(x in t for x in ["rseries", "velos", "f5os"]):
            return "rseries"
        if "big-ip" in t or "bigip" in t:
            return "big-ip"
        return t

    def extract(self, query):
        clean_q = query.strip()
        if not clean_q:
            return None

        if clean_q.lower() in self._cache:
            return dict(self._cache[clean_q.lower()])

        if not self._active_model:
            self._detect_engine()

        if self._active_model and self._active_model.startswith("vertex/"):
            intent = self._extract_via_vertex(clean_q)
            if intent:
                self._cache[clean_q.lower()] = intent
                return dict(intent)
        elif self._active_model and self._active_model.startswith("ollama/"):
            model_name = self._active_model.split("/", 1)[1]
            intent = self._extract_via_ollama(clean_q, model_name)
            if intent:
                self._cache[clean_q.lower()] = intent
                return dict(intent)
        elif self._active_model and self._active_model.startswith("gemini/"):
            intent = self._extract_via_gemini(clean_q)
            if intent:
                self._cache[clean_q.lower()] = intent
                return dict(intent)

        return None

    def _extract_via_vertex(self, query):
        token = GoogleAuthHelper.get_token()
        if not token or not self.gemini_project:
            return None
        timeout = float(GEMINI_CFG.get("timeout_seconds", 10))
        url = get_vertex_endpoint(self.gemini_location, self.gemini_project, self.gemini_model)

        prompt = (
            "Analyze search query for F5/NGINX/Cloud bookmarks catalog. Output JSON only:\n"
            "{\n"
            '  "is_migration": boolean,\n'
            '  "migration_source": string or null,\n'
            '  "migration_target": string or null,\n'
            '  "target_products": ["big-ip", "f5-xc", "nginx"],\n'
            '  "target_topics": ["sizing-capacity", "security-waf"],\n'
            '  "search_keywords": ["3-5 high signal terms"],\n'
            '  "must_mention": ["1-2 mandatory concepts"],\n'
            '  "requires_vpn": boolean or null,\n'
            '  "summary": "one sentence explaining intent"\n'
            "}\nQuery: " + query
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0}
        }
        t0 = time.time()
        try:
            data = send_llm_request(
                "vertex",
                self.gemini_model,
                url,
                payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=timeout
            )
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_json = re.sub(r"^```json\s*|\s*```$", "", text.strip())
            parsed = json.loads(clean_json)
            dur = round(time.time() - t0, 2)
            mig_target = self._normalize_target(parsed.get("migration_target"))
            prods = [p.lower() for p in parsed.get("target_products", []) if isinstance(p, str)]
            if mig_target and mig_target not in prods:
                prods.insert(0, mig_target)
            keywords = [k.lower() for k in parsed.get("search_keywords", []) if isinstance(k, str)]
            must = [m.lower() for m in parsed.get("must_mention", []) if isinstance(m, str)]
            if parsed.get("is_migration") and mig_target == "f5-xc":
                if not any("xc" in m or "distributed cloud" in m for m in must):
                    must.extend(["distributed cloud", "xc"])
            return {
                    "raw_query": query,
                    "normalized_query": query.lower(),
                    "is_migration": bool(parsed.get("is_migration")),
                    "migration_source": (parsed.get("migration_source") or "").lower() or None,
                    "migration_target": mig_target,
                    "products": prods,
                    "topics": [t.lower() for t in parsed.get("target_topics", []) if isinstance(t, str)],
                    "search_keywords": keywords,
                    "must_mention": must,
                    "requires_vpn": parsed.get("requires_vpn"),
                    "min_visits": 0,
                    "concepts": keywords,
                    "source_types": [],
                    "summary_of_intent": parsed.get("summary", ""),
                    "llm_extracted": True,
                    "llm_engine": f"vertex/{self.gemini_model}",
                    "llm_duration_s": dur
                }
        except Exception as e:
            print(f"Vertex AI intent extraction error: {e}")
            return None

    def _extract_via_ollama(self, query, model_name):
        system_prompt = (
            "You are an expert AI intent engine for an enterprise technical bookmarks library covering "
            "F5 BIG-IP, F5 XC (Distributed Cloud), and NGINX.\n"
            "Analyze the user search query and output ONLY a valid JSON object matching this example structure:\n"
            "{\n"
            '  "is_migration": true,\n'
            '  "migration_source": "irules",\n'
            '  "migration_target": "f5-xc",\n'
            '  "target_products": ["big-ip", "f5-xc"],\n'
            '  "target_topics": ["programmability-irules"],\n'
            '  "search_keywords": ["migration", "irules", "distributed cloud", "xc"],\n'
            '  "must_mention": ["distributed cloud", "xc"],\n'
            '  "requires_vpn": false,\n'
            '  "summary": "User wants to migrate/convert legacy BIG-IP iRules to F5 Distributed Cloud (XC)."\n'
            "}"
        )
        temp = float(OLLAMA_CFG.get("temperature", 0.0))
        num_pred = int(OLLAMA_CFG.get("num_predict", 160))
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": temp, "num_predict": num_pred}
        }
        timeout = float(OLLAMA_CFG.get("timeout_seconds", 7))
        t0 = time.time()
        try:
            data = send_llm_request(
                "ollama",
                model_name,
                f"{self.ollama_url}/api/chat",
                payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout
            )
            content = data.get("message", {}).get("content", "{}")
            parsed = json.loads(content)
            dur = round(time.time() - t0, 2)

            mig_target = self._normalize_target(parsed.get("migration_target"))
            prods = [p.lower() for p in parsed.get("target_products", []) if isinstance(p, str)]
            if mig_target and mig_target not in prods:
                prods.insert(0, mig_target)

            keywords = [k.lower() for k in parsed.get("search_keywords", []) if isinstance(k, str)]
            must = [m.lower() for m in parsed.get("must_mention", []) if isinstance(m, str)]
            if parsed.get("is_migration") and mig_target == "f5-xc":
                if not any("xc" in m or "distributed cloud" in m for m in must):
                    must.extend(["distributed cloud", "xc"])

            intent = {
                "raw_query": query,
                "normalized_query": query.lower(),
                "is_migration": bool(parsed.get("is_migration")),
                "migration_source": (parsed.get("migration_source") or "").lower() or None,
                "migration_target": mig_target,
                "products": prods,
                "topics": [t.lower() for t in parsed.get("target_topics", []) if isinstance(t, str)],
                "search_keywords": keywords,
                "must_mention": must,
                "requires_vpn": parsed.get("requires_vpn"),
                "min_visits": 0,
                "concepts": keywords,
                "source_types": [],
                "summary_of_intent": parsed.get("summary", ""),
                "llm_extracted": True,
                "llm_engine": f"ollama/{model_name}",
                "llm_duration_s": dur
            }
            return intent
        except Exception as e:
            print(f"Ollama intent extraction failed: {e}")
            return None

    def _extract_via_gemini(self, query):
        timeout = float(GEMINI_CFG.get("timeout_seconds", 8))
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
        prompt = (
            "Analyze search query for F5/NGINX/Cloud bookmarks catalog. Output JSON only:\n"
            "{\n"
            '  "is_migration": boolean,\n'
            '  "migration_source": string or null,\n'
            '  "migration_target": string or null,\n'
            '  "target_products": ["big-ip", "f5-xc", "nginx"],\n'
            '  "target_topics": ["sizing-capacity", "security-waf"],\n'
            '  "search_keywords": ["3-5 high signal terms"],\n'
            '  "must_mention": ["1-2 mandatory concepts"],\n'
            '  "requires_vpn": boolean or null,\n'
            '  "summary": "one sentence explaining intent"\n'
            "}\nQuery: " + query
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        t0 = time.time()
        try:
            data = send_llm_request(
                "gemini",
                self.gemini_model,
                url,
                payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout
            )
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_json = re.sub(r"^```json\s*|\s*```$", "", text.strip())
            parsed = json.loads(clean_json)
            dur = round(time.time() - t0, 2)
            mig_target = self._normalize_target(parsed.get("migration_target"))
            return {
                "raw_query": query,
                "normalized_query": query.lower(),
                "is_migration": bool(parsed.get("is_migration")),
                "migration_source": (parsed.get("migration_source") or "").lower() or None,
                "migration_target": mig_target,
                "products": [p.lower() for p in parsed.get("target_products", []) if isinstance(p, str)],
                "topics": [t.lower() for t in parsed.get("target_topics", []) if isinstance(t, str)],
                "search_keywords": [k.lower() for k in parsed.get("search_keywords", []) if isinstance(k, str)],
                "must_mention": [m.lower() for m in parsed.get("must_mention", []) if isinstance(m, str)],
                "requires_vpn": parsed.get("requires_vpn"),
                "min_visits": 0,
                "concepts": parsed.get("search_keywords", []),
                "source_types": [],
                "summary_of_intent": parsed.get("summary", ""),
                "llm_extracted": True,
                "llm_engine": self.gemini_model,
                "llm_duration_s": dur
            }
        except Exception as e:
            print(f"Gemini intent extraction error: {e}")
            return None


class CatalogEngine:
    def __init__(self, catalog_path):
        self.catalog_path = catalog_path
        self.last_mtime = 0
        self.catalog = []
        self.corpus_words = {}
        self.doc_token_counts = []
        self.doc_lengths = []
        self.avg_doc_len = 0
        self.lock = threading.RLock()
        self.content_inspector = ContentInspector(CONTENT_CACHE_PATH)
        self.llm_intent_extractor = LLMIntentExtractor(ollama_url=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))
        self.reload()

    def reload(self):
        with self.lock:
            self.content_inspector.reload_if_changed()
            if not os.path.exists(self.catalog_path):
                print(f"Warning: Catalog not found at {self.catalog_path}")
                return
            mtime = os.path.getmtime(self.catalog_path)
            if mtime > self.last_mtime or not self.catalog:
                with open(self.catalog_path, "r", encoding="utf-8") as f:
                    self.catalog = json.load(f)
                self.last_mtime = mtime
                self._build_index()
                print(f"[{time.strftime('%X')}] Loaded {len(self.catalog)} bookmarks from {os.path.basename(self.catalog_path)}")

    def _build_index(self):
        total_len = 0
        self.corpus_words = {}
        self.doc_token_counts = []
        self.doc_lengths = []
        for bm in self.catalog:
            bm.pop("_tokens", None)
            bm.pop("_id", None)
            text = self._get_searchable_text(bm)
            tokens = self._tokenize(text)
            doc_len = len(tokens)
            total_len += doc_len
            counts = Counter(tokens)
            self.doc_token_counts.append(counts)
            self.doc_lengths.append(doc_len)
            for t in counts:
                self.corpus_words[t] = self.corpus_words.get(t, 0) + 1
        self.avg_doc_len = (total_len / len(self.catalog)) if self.catalog else 1

    def _tokenize(self, text):
        return re.findall(r"[a-z0-9_\-]+", text.lower())

    def _get_searchable_text(self, bm):
        tags = bm.get("tags", {})
        prods = " ".join(tags.get("products", []))
        topics = " ".join(tags.get("topics", []))
        stypes = " ".join(tags.get("source_types", []))
        leg = " ".join(bm.get("legacy_path", []))
        desc = bm.get("description", "")
        summary = bm.get("content_summary", "")
        notes = bm.get("notes", "")
        return f"{bm.get('title', '')} {bm.get('url', '')} {desc} {summary} {notes} {prods} {topics} {stypes} {leg}"

    def normalize_query(self, query):
        words = re.findall(r"[a-z0-9_\-]+", query.lower())
        norm_words = [COMMON_TYPOS.get(w, w) for w in words]
        return " ".join(norm_words)

    def extract_intent(self, query):
        # 1. Primary: Leverage LLM-based intent identification (no hardcoded md/instructions)
        llm_intent = self.llm_intent_extractor.extract(query)
        if llm_intent and llm_intent.get("llm_extracted"):
            return llm_intent

        # 2. Resilient Fallback: Deterministic Heuristic Intent Extraction
        return self._heuristic_extract_intent(query)

    def _heuristic_extract_intent(self, query):
        norm_query = self.normalize_query(query)
        intent = {
            "products": [],
            "topics": [],
            "source_types": [],
            "requires_vpn": None,
            "min_visits": 0,
            "raw_query": query,
            "normalized_query": norm_query,
            "concepts": [],
            "is_migration": False,
            "migration_source": None,
            "migration_target": None,
            "search_keywords": [],
            "must_mention": [],
            "summary_of_intent": "Heuristic match for " + query,
            "llm_extracted": False,
            "llm_engine": "heuristic-fallback"
        }

        # Check products
        for prod, kws in PRODUCT_KEYWORDS.items():
            matched = False
            for kw in kws:
                pattern = kw if kw.startswith(r"\b") else r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, norm_query):
                    matched = True
                    break
            if matched:
                intent["products"].append(prod)

        # Check topics
        for topic, kws in TOPIC_KEYWORDS.items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", norm_query) for kw in kws):
                intent["topics"].append(topic)

        # Check source types
        for stype, kws in SOURCE_TYPE_KEYWORDS.items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", norm_query) for kw in kws):
                intent["source_types"].append(stype)

        # Check VPN indicators
        if any(w in norm_query for w in ["vpn", "internal only", "intranet", "needs vpn", "behind vpn"]):
            intent["requires_vpn"] = True
        elif any(w in norm_query for w in ["public", "no vpn", "external"]):
            intent["requires_vpn"] = False

        # Check visit indicators
        if any(w in norm_query for w in ["most used", "frequent", "popular", "top links", "most visited"]):
            intent["min_visits"] = 5

        # Check specific concept extractions
        for concept in ["sizing", "matrix", "cve", "saml", "oauth", "irule", "fast", "as3", "udf", "license", "convert"]:
            if concept in norm_query:
                intent["concepts"].append(concept)

        # Migration & Platform Transition Intent
        if any(re.search(r"\b" + re.escape(w) + r"\b", norm_query) for w in ["migrate", "migration", "converting", "convert", "conversion", "transition", "port", "move to", "switch to", "ps-convert"]):
            intent["is_migration"] = True

            # Target platform
            if re.search(r"\b(to|into|onto|in)\s+(the\s+)?(f5[\-\s]*)?xc(\s+platform)?\b|\bxc\s+platform\b|\bxc\b|\bdistributed cloud\b|\bvolterra\b", norm_query):
                intent["migration_target"] = "f5-xc"
                intent["must_mention"] = ["distributed cloud", "xc"]
                if "f5-xc" not in intent["products"]:
                    intent["products"].insert(0, "f5-xc")
            elif re.search(r"\b(to|into|onto|in)\s+(the\s+)?nginx\b", norm_query):
                intent["migration_target"] = "nginx"
                intent["must_mention"] = ["nginx"]
                if "nginx" not in intent["products"]:
                    intent["products"].insert(0, "nginx")
            elif re.search(r"\b(to|into|onto|in)\s+(the\s+)?(rseries|velos|f5os)\b", norm_query):
                intent["migration_target"] = "rseries"
                if "rseries" not in intent["products"]:
                    intent["products"].insert(0, "rseries")

            # Source component
            if re.search(r"\birules?\b|\btcl\b", norm_query):
                intent["migration_source"] = "irules"
            elif re.search(r"\bbig[\-\s]?ip\b|\bltm\b|\bucs\b|\bvirtual server\b", norm_query):
                intent["migration_source"] = "big-ip"

        return intent

    def search(self, query, filters=None, limit=15):
        self.reload()
        filters = filters or {}
        product_scope = (filters.get("product") or filters.get("product_scope") or "adsp").strip().lower()
        if product_scope not in PRODUCT_SCOPES:
            product_scope = "adsp"

        # Step 1: Understand Intent using LLM
        intent = self.extract_intent(query)
        intent["product_scope"] = product_scope

        # Combine explicit filters from client with query-extracted intent
        target_prods = set(filters.get("products", []) or intent["products"])
        target_topics = set(filters.get("topics", []) or intent["topics"])
        target_types = set(filters.get("source_types", []) or intent["source_types"])
        req_vpn = filters.get("requires_vpn", intent["requires_vpn"])
        min_v = filters.get("min_visits", intent["min_visits"])

        norm_query = intent.get("normalized_query", self.normalize_query(query))
        tokens = self._tokenize(norm_query)
        stop_words = {"how", "do", "i", "can", "show", "me", "find", "the", "a", "an", "for", "with", "and", "or", "to", "in", "on", "of", "what", "is", "are", "where", "want"}
        query_tokens = [t for t in tokens if t not in stop_words] or tokens

        # Add search keywords identified by the LLM to query_tokens for candidate retrieval
        llm_kws = intent.get("search_keywords", [])
        for kw in llm_kws:
            for kw_tok in self._tokenize(kw):
                if kw_tok not in query_tokens and kw_tok not in stop_words:
                    query_tokens.append(kw_tok)

        # For migration intent, ensure conversion and migration keywords participate in candidate retrieval
        if intent.get("is_migration"):
            for syn in ["convert", "conversion", "migration"]:
                if syn not in query_tokens:
                    query_tokens.append(syn)

        # If a specific product scope is selected, augment candidate retrieval tokens with scope keywords
        scope_info = PRODUCT_SCOPES.get(product_scope, {})
        scope_tags = scope_info.get("tags", set())
        scope_keywords = scope_info.get("keywords", [])
        if product_scope != "adsp":
            for skw in scope_keywords:
                for skw_tok in self._tokenize(skw):
                    if skw_tok not in query_tokens and skw_tok not in stop_words:
                        query_tokens.append(skw_tok)

        with self.lock:
            catalog_snapshot = list(self.catalog)
            counts_snapshot = list(self.doc_token_counts)
            lengths_snapshot = list(self.doc_lengths)
            corpus_snapshot = dict(self.corpus_words)
            avg_doc_len = self.avg_doc_len or 1

        scored = []
        n_docs = len(catalog_snapshot)
        k1 = BM25_K1
        b = BM25_B

        for idx, bm in enumerate(catalog_snapshot):
            v_count = bm.get("visit_count", 0)
            if v_count < min_v:
                continue
            is_vpn = bm.get("requires_vpn", False)
            if req_vpn is not None and is_vpn != req_vpn:
                continue

            bm_tags = bm.get("tags", {})
            bm_prods = set(bm_tags.get("products", []))
            bm_topics = set(bm_tags.get("topics", []))
            bm_types = set(bm_tags.get("source_types", []))

            # Base BM25 score (O(1) Counter lookup)
            bm25_score = 0.0
            doc_len = lengths_snapshot[idx] if idx < len(lengths_snapshot) else 0
            doc_counts = counts_snapshot[idx] if idx < len(counts_snapshot) else {}

            for qt in query_tokens:
                tf = doc_counts.get(qt, 0)
                if tf > 0:
                    df = corpus_snapshot.get(qt, 1)
                    idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
                    tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_doc_len)))
                    bm25_score += idf * tf_norm

            # Tag alignment boost
            tag_boost = 0.0
            if target_prods and (target_prods & bm_prods):
                tag_boost += 6.0
            if target_topics and (target_topics & bm_topics):
                tag_boost += 5.0
            if target_types and (target_types & bm_types):
                tag_boost += 4.0

            # Title exact phrase / token boost
            title_lower = bm.get("title", "").lower()
            url_lower = bm.get("url", "").lower()
            if norm_query in title_lower:
                tag_boost += 10.0
            elif all(t in title_lower for t in query_tokens):
                tag_boost += 6.0

            # Product Scope alignment boost and non-matching penalty
            if product_scope != "adsp":
                scope_match = False
                if scope_tags and (scope_tags & bm_prods):
                    scope_match = True
                elif any(sk in title_lower or sk in url_lower for sk in scope_keywords):
                    scope_match = True

                if scope_match:
                    tag_boost += 35.0
                elif scope_tags and bm_prods and not (scope_tags & bm_prods):
                    # Contains explicit product tags that belong to a different product
                    tag_boost -= 20.0

            # Targeted Migration and Conversion Intelligence
            if intent.get("is_migration"):
                mig_target = intent.get("migration_target")
                mig_source = intent.get("migration_source")

                if mig_target == "f5-xc":
                    if "f5-xc" in bm_prods:
                        tag_boost += 15.0

                    # Direct conversion guides get paramount boost
                    if "guide-convert" in url_lower or "ps-convert" in url_lower or ("conversion" in title_lower and "distributed cloud" in title_lower):
                        tag_boost += 40.0
                    elif ("convert" in title_lower or "migration" in title_lower) and ("f5-xc" in bm_prods or "big-ip" in bm_prods):
                        tag_boost += 25.0

                    if mig_source == "irules":
                        # iRules functional equivalents in XC: Service Policies, Listener Logic, Routing
                        if "service policy" in title_lower or "service-policy" in url_lower or "listener logic" in title_lower:
                            tag_boost += 26.0
                        elif "f5-xc" in bm_prods and any(k in title_lower for k in ["routing", "load balancer", "docs-v2", "technical knowledge"]):
                            tag_boost += 12.0

                        # Demote pure BIG-IP iRules syntax docs (they do not apply to XC)
                        if "f5-xc" not in bm_prods and "clouddocs.f5.com/api/irules" in url_lower:
                            tag_boost -= 30.0
                        elif "f5-xc" not in bm_prods and "programmability-irules" in bm_topics and "convert" not in title_lower:
                            tag_boost -= 20.0

            # Historical visit frequency boost
            visit_boost = math.log1p(v_count) * VISIT_BOOST_FACTOR

            total_score = bm25_score + tag_boost + visit_boost

            if total_score > 0.5:
                scored.append({
                    "score": round(total_score, 2),
                    "bookmark": bm
                })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # Step 2: Retrieve candidate pool matching labels & tags
        candidates = []
        for item in scored[:MAX_CANDIDATES]:
            bm_copy = dict(item["bookmark"])
            bm_copy["_candidate_score"] = item["score"]
            candidates.append(bm_copy)

        # Step 3 & 4: Open related bookmarks, browse content, verify relevance, and display ONLY verified bookmarks
        verified_results = self.content_inspector.verify_candidates(candidates, intent, limit=limit or DEFAULT_LIMIT)
        return intent, verified_results

# LLM Providers Handler (Vertex AI / Gemini / Ollama / Heuristic)
class LLMBridge:
    def __init__(self):
        api_key_env = GEMINI_CFG.get("api_key_env", "GEMINI_API_KEY")
        self.gemini_key = os.environ.get(api_key_env)
        self.gemini_model = GEMINI_CFG.get("model", "Gemini 3.8 Flash (Medium)")
        self.gemini_project = GoogleAuthHelper.get_project_id(GEMINI_CFG.get("project_id"))
        self.gemini_location = GEMINI_CFG.get("location", "us-central1")
        self.ollama_url = (os.environ.get("OLLAMA_HOST") or OLLAMA_CFG.get("url", "http://127.0.0.1:11434")).rstrip("/")
        self.ollama_model = OLLAMA_CFG.get("preferred_model", "gemma3:4b")

    def get_status(self):
        # 1. Google Cloud Project ID (Vertex AI with ADC / OAuth token)
        if self.gemini_project and GoogleAuthHelper.get_token():
            return {"provider": "vertex", "details": f"Google Vertex AI ({self.gemini_model}) [Project: {self.gemini_project}]"}
        # 2. Google Gemini Developer API Key
        if self.gemini_key:
            return {"provider": "gemini", "details": f"Google Gemini API ({self.gemini_model})"}
        # 3. Local Ollama GPU Engine
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "BookmarksAI"})
            opener = _build_http_opener()
            with opener.open(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return {"provider": "ollama", "details": f"Local Ollama ({self.ollama_model}) at {self.ollama_url}"}
        except Exception:
            pass
        return {"provider": "heuristic", "details": "High-Precision Deep Content Verification Engine"}

    def generate_synthesis(self, query, intent, results, history=None, product_scope="adsp"):
        status = self.get_status()
        provider = status["provider"]

        if provider == "vertex":
            try:
                return self._call_vertex(query, intent, results, history, product_scope=product_scope)
            except Exception as e:
                print(f"Vertex AI synthesis error, falling back to heuristic: {e}")

        elif provider == "gemini":
            try:
                return self._call_gemini(query, intent, results, history, product_scope=product_scope)
            except Exception as e:
                print(f"Gemini API error, falling back to heuristic: {e}")

        elif provider == "ollama":
            try:
                return self._call_ollama(query, intent, results, history, product_scope=product_scope)
            except Exception as e:
                print(f"Ollama error, falling back to heuristic: {e}")

        return self._generate_heuristic(query, intent, results, product_scope=product_scope)

    def _call_vertex(self, query, intent, results, history=None, product_scope="adsp"):
        token = GoogleAuthHelper.get_token()
        if not token:
            raise RuntimeError("Unable to acquire Google OAuth access token for Vertex AI")
        timeout = float(GEMINI_CFG.get("timeout_seconds", 12))
        url = get_vertex_endpoint(self.gemini_location, self.gemini_project, self.gemini_model)

        context_items = []
        for i, b in enumerate(results[:8], 1):
            summary = b.get("content_summary") or b.get("description", "")
            notes_str = f"\n   Custom Notes: {b['notes']}" if b.get("notes") else ""
            context_items.append(
                f"{i}. Title: {b['title']}\n   URL: {b['url']}\n   Technical Summary: {summary}{notes_str}\n   VPN Required: {b.get('requires_vpn')}\n   Visits: {b.get('visit_count', 0)}"
            )
        context_str = "\n".join(context_items)

        scope_addon = ""
        if product_scope and product_scope != "adsp" and product_scope in PRODUCT_SCOPES:
            sc_info = PRODUCT_SCOPES[product_scope]
            scope_addon = f"\nTARGET PRODUCT SCOPE: {sc_info['name']}\nSCOPE DIRECTIVE: {sc_info['instruction']}\nFocus your synthesis and recommended links strictly on this product.\n"

        prompt = (
            "You are an expert AI Assistant specialized in F5, NGINX, Cloud and security architecture.\n"
            "The user is searching their curated bookmarks showcase.\n"
            f"Here is the user query: {query}\n"
            f"{scope_addon}\n"
            "Here are the top retrieved bookmarks from their catalog:\n"
            f"{context_str}\n\n"
            "Instructions:\n"
            "1. Provide a concise, professional answer directly addressing the user's inquiry.\n"
            "2. Reference the most relevant bookmarks with markdown links [Title](URL).\n"
            "3. Mention if any link requires VPN.\n"
            "4. Be helpful, concise, and technical."
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2}
        }
        data = send_llm_request(
            "vertex",
            self.gemini_model,
            url,
            payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=timeout
        )
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _generate_heuristic(self, query, intent, results, product_scope="adsp"):
        if not results:
            reply = f"I opened and browsed candidate bookmarks matching your search, but **none contained content sufficiently relevant to \"{query}\""
            if product_scope and product_scope != "adsp" and product_scope in PRODUCT_SCOPES:
                reply += f" within the **{PRODUCT_SCOPES[product_scope]['name']}** scope**.\n\n"
            else:
                reply += "**.\n\n"
            reply += "💡 **Suggestions**:\n"
            reply += "- Try broader keywords like `sizing`, `nginx`, `big-ip`, `cve`, or `saml`.\n"
            if product_scope != "adsp":
                reply += "- Switch product scope to `🌐 ADSP (All)` to search across the entire portfolio.\n"
            reply += "- Check if the target is an internal portal requiring VPN.\n"
            reply += "- Use the category pills at the top of the showcase to explore all 980+ links."
            return reply

        # Migration-specific consultative synthesis
        if intent.get("is_migration"):
            mig_target = intent.get("migration_target")
            mig_source = intent.get("migration_source")

            if mig_target == "f5-xc":
                reply = "### 🔄 Migrating to F5 Distributed Cloud (XC)\n\n"
                if mig_source == "irules":
                    reply += (
                        "F5 Distributed Cloud (XC) utilizes an Envoy-based proxy architecture and **does not execute TCL-based iRules directly**. "
                        "Instead, iRule functionality is mapped to native XC components:\n\n"
                        "1. **HTTP Load Balancer Routing & Rewrites**: For path rewrites, URL redirects, prefix routing, header manipulation, and pool routing.\n"
                        "2. **Service Policies**: For custom header inspection, ASN/IP reputation filtering, and rule-based request blocking or routing.\n"
                        "3. **Automated Conversion Tools**: Use **F5 Policy Supervisor (`ps-convert`)** and the official conversion guide to analyze and translate configurations.\n"
                        "4. **vK8s & Edge Compute**: For complex programmatic requirements needing inline code execution at the edge.\n\n"
                    )
                else:
                    reply += (
                        "When migrating from BIG-IP to F5 Distributed Cloud (XC), services are transitioned from traditional Virtual Servers and Pools "
                        "to XC **HTTP/TCP Load Balancers**, **Origin Pools**, and **Service Policies**.\n\n"
                    )

                reply += f"### 🔍 Verified in Bookmark Content ({len(results)} matches)\n"
                reply += "*The agent opened candidate bookmarks, inspected their page bodies, and verified the following resources:*\n\n"
                for b in results[:5]:
                    vpn_str = " 🔒" if b.get("requires_vpn") else ""
                    v_str = f" `({b.get('visit_count', 0)} visits)`" if b.get("visit_count", 0) > 0 else ""
                    reply += f"- **[{b['title']}]({b['url']})**{vpn_str}{v_str}\n"
                    if b.get("content_excerpt"):
                        reply += f"  > 💬 *\"{b['content_excerpt']}\"*\n"
                    elif b.get("description"):
                        reply += f"  > {b['description']}\n"

                reply += "\n*Click **Locate on Page** to jump to any bookmark card, or **Filter Page** to isolate them in the showcase.*"
                return reply

        intent_badges = []
        if product_scope and product_scope != "adsp" and product_scope in PRODUCT_SCOPES:
            intent_badges.append(f"Scope: `{PRODUCT_SCOPES[product_scope]['short_name']}`")
        if intent.get("products"):
            intent_badges.append(f"Product: `{', '.join(intent['products'])}`")
        if intent.get("topics"):
            intent_badges.append(f"Topic: `{', '.join(intent['topics'])}`")
        if intent.get("requires_vpn"):
            intent_badges.append("🔒 Requires VPN")

        summary_intro = f"Browsed candidate bookmarks and verified **{len(results)}** with relevant content"
        if intent_badges:
            summary_intro += f" for {', '.join(intent_badges)}"
        summary_intro += ":\n\n"

        # Highlight the top match
        top = results[0]
        desc = top.get("description") or f"Direct link to {top['title']}"
        vpn_note = " *(Requires F5 VPN)*" if top.get("requires_vpn") else ""
        visits = top.get("visit_count", 0)
        visit_note = f" • 🔥 Visited {visits} times" if visits > 0 else ""

        reply = summary_intro
        reply += f"### ⭐ Top Verified Match\n"
        reply += f"**[{top['title']}]({top['url']})**{vpn_note}{visit_note}\n\n"
        if top.get("content_excerpt"):
            reply += f"> 💬 **Verified Excerpt from Page Content:**\n> *\"{top['content_excerpt']}\"*\n\n"
        reply += f"> {desc}\n\n"
        if top.get("notes"):
            reply += f"> 📝 **Custom Notes:** {top['notes']}\n\n"

        if len(results) > 1:
            reply += f"### 📚 Additional Verified Bookmarks\n"
            for b in results[1:5]:
                v_str = f" `({b.get('visit_count', 0)} visits)`" if b.get("visit_count", 0) > 0 else ""
                vpn_str = " 🔒" if b.get("requires_vpn") else ""
                reply += f"- **[{b['title']}]({b['url']})**{vpn_str}{v_str}\n"
                if b.get("content_excerpt"):
                    reply += f"  > 💬 *\"{b['content_excerpt']}\"*\n"
                if b.get("notes"):
                    reply += f"  > 📝 *Note: {b['notes']}*\n"

        reply += "\n*Use the **Locate on Page** buttons below to jump directly to any card on the showcase, or click **Filter Page** to view them in the main grid.*"
        return reply

    def _call_gemini(self, query, intent, results, history=None, product_scope="adsp"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
        context_items = []
        for i, b in enumerate(results[:8], 1):
            summary = b.get("content_summary") or b.get("description", "")
            notes_str = f"\n   Custom Notes: {b['notes']}" if b.get("notes") else ""
            context_items.append(
                f"{i}. Title: {b['title']}\n   URL: {b['url']}\n   Technical Summary: {summary}{notes_str}\n   VPN Required: {b.get('requires_vpn')}\n   Visits: {b.get('visit_count', 0)}"
            )
        context_str = "\n".join(context_items)

        scope_addon = ""
        if product_scope and product_scope != "adsp" and product_scope in PRODUCT_SCOPES:
            sc_info = PRODUCT_SCOPES[product_scope]
            scope_addon = f"\nTARGET PRODUCT SCOPE: {sc_info['name']}\nSCOPE DIRECTIVE: {sc_info['instruction']}\nFocus your synthesis and recommended links strictly on this product.\n"

        prompt = (
            "You are an expert AI Assistant specialized in F5, NGINX, Cloud and security architecture.\n"
            "The user is searching their curated bookmarks showcase.\n"
            f"Here is the user query: {query}\n"
            f"{scope_addon}\n"
            "Here are the top retrieved bookmarks from their catalog:\n"
            f"{context_str}\n\n"
            "Instructions:\n"
            "1. Provide a concise, professional answer directly addressing the user's inquiry.\n"
            "2. Reference the most relevant bookmarks with markdown links [Title](URL).\n"
            "3. Mention if any link requires VPN.\n"
            "4. Be helpful, concise, and technical."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        timeout = float(GEMINI_CFG.get("timeout_seconds", 8))
        data = send_llm_request(
            "gemini",
            self.gemini_model,
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_ollama(self, query, intent, results, history=None, product_scope="adsp"):
        url = f"{self.ollama_url}/api/chat"
        context_items = [
            f"- [{b['title']}]({b['url']}): {b.get('description', '')}" + (f" (Notes: {b['notes']})" if b.get("notes") else "")
            for b in results[:6]
        ]
        context_str = "\n".join(context_items)

        scope_addon = ""
        if product_scope and product_scope != "adsp" and product_scope in PRODUCT_SCOPES:
            sc_info = PRODUCT_SCOPES[product_scope]
            scope_addon = f"Target Product Scope: {sc_info['name']}. {sc_info['instruction']}\n\n"

        prompt = f"{scope_addon}User asks: {query}\n\nTop matching bookmarks verified from user's catalog:\n{context_str}\n\nProvide a concise, helpful summary highlighting the best links for the user with markdown links:"
        payload = {
            "model": self.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 256}
        }
        timeout = float(OLLAMA_CFG.get("timeout_seconds", 8))
        data = send_llm_request(
            "ollama",
            self.ollama_model,
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        return data.get("message", {}).get("content", "")

COPYRIGHT_REGEX = re.compile(
    r'(?:©|&copy;|Copyright|\(c\))\s*(?:(?:19|20)\d{2}\s*[-–]\s*)?(20\d{2})\s+F5(?:,\s*Inc\.|\s+Networks,\s*Inc\.)?',
    re.IGNORECASE
)
TRADEMARK_REGEX = re.compile(
    r'F5,\s*(?:the\s+F5\s+logo,\s*)?(?:BIG-IP|TMOS|Distributed\s+Cloud|NGINX|F5OS).*trademarks',
    re.IGNORECASE
)
F5_CORP_NAMES = [
    "f5, inc.", "f5 networks, inc.", "f5 networks", "all rights reserved. f5",
    "f5 clouddocs", "f5 distributed cloud", "myf5", "f5 devcentral", "tmos®", "big-ip®",
    "f5 cloud", "f5 workforce ai"
]

class WebPageContentExtractor(HTMLParser):
    """
    Extracts structured page metadata, headings, main body text, footers,
    and inspects official F5 branding markers (SVGs, logos, copyrights).
    """
    def __init__(self):
        super().__init__()
        self.title_parts = []
        self.in_title = False
        self.in_heading = False
        self.headings = []
        self.meta_desc = ""
        self.og_title = ""
        self.og_desc = ""
        self.og_site_name = ""
        self.text_parts = []
        self.footer_parts = []
        self.skip_depth = 0
        self.in_footer = False
        self.has_f5_logo = False
        self.has_f5_theme = False
        self.f5_markers = []

    VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form"}
    SKIP_PATTERNS = re.compile(r"\b(nav|navbar|sidebar|breadcrumb|pagination|related|social-share|cookie-banner|footer)\b", re.IGNORECASE)

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        # Check for F5 logos in img, svg, or classes
        if t in ("img", "svg", "span", "div", "a"):
            src = attr_dict.get("src", "").lower()
            alt = attr_dict.get("alt", "").lower()
            cls = attr_dict.get("class", "").lower()
            id_val = attr_dict.get("id", "").lower()
            aria = attr_dict.get("aria-label", "").lower()

            f5_logo_signals = [
                "f5-logo", "f5_logo", "f5logo", "f5-ball", "f5_ball", "f5.svg",
                "f5-red", "cdn.f5.com", "assets.f5.com", "f5-header", "f5-navigation"
            ]
            combined_attr = f"{src} {alt} {cls} {id_val} {aria}"
            if any(sig in combined_attr for sig in f5_logo_signals):
                self.has_f5_logo = True
                self.f5_markers.append(f"Logo/Asset: {combined_attr[:60]}")

            if "rst-content" in cls or "f5-sphinx" in cls:
                self.has_f5_theme = True

        if t == "title":
            self.in_title = True
        elif t in ("h1", "h2", "h3"):
            self.in_heading = True
        elif t in self.VOID_ELEMENTS:
            pass
        elif self.skip_depth > 0:
            self.skip_depth += 1
        elif t in self.SKIP_TAGS or self.SKIP_PATTERNS.search(attr_dict.get("class", "")) or self.SKIP_PATTERNS.search(attr_dict.get("id", "")):
            self.skip_depth = 1

        if t == "meta":
            name = (attr_dict.get("name") or attr_dict.get("property") or "").lower()
            content = attr_dict.get("content", "").strip()
            if name in ("description", "twitter:description"):
                self.meta_desc = content
            elif name in ("og:description",):
                self.og_desc = content
            elif name in ("og:title", "twitter:title"):
                self.og_title = content
            elif name in ("og:site_name", "author"):
                self.og_site_name = content
                if "f5" in content.lower():
                    self.f5_markers.append(f"Meta: {content}")

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "title":
            self.in_title = False
        elif t in ("h1", "h2", "h3"):
            self.in_heading = False
        elif t in self.VOID_ELEMENTS:
            pass
        elif self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        s = data.strip()
        if not s:
            return
        if self.in_title:
            self.title_parts.append(s)
        elif self.skip_depth == 0:
            # Skip pure URL strings or link markers
            if s.startswith("http://") or s.startswith("https://") or s.startswith("[http"):
                return
            if self.in_heading:
                self.headings.append(s)
            self.text_parts.append(s)

    def get_results(self):
        title = " ".join(self.title_parts).strip()
        body_text = re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()
        footer_text = re.sub(r"\s+", " ", " ".join(self.footer_parts)).strip()
        headings_text = " | ".join(self.headings[:6])
        return {
            "title": title or self.og_title,
            "meta_description": self.meta_desc or self.og_desc,
            "headings": headings_text,
            "body_text": body_text[:35000],
            "footer_text": footer_text[:5000],
            "has_f5_logo": self.has_f5_logo,
            "has_f5_theme": self.has_f5_theme,
            "f5_markers": self.f5_markers
        }

class BookmarkInspector:
    """
    Automated URL Inspection & LLM Metadata Synthesizer.
    1. Fetches target webpage, follows validated redirects, extracts title, meta, headings, body, footers.
    2. Deep inspection for official F5 assets (logos, trademarks, copyright) even on CDNs.
    3. Generates concise UI summary + dense technical LLM summary (attached as hidden context).
    4. Automatically maps to 9 Strategic Pillars and aligns product/topic tags.
    """
    def __init__(self, llm_bridge):
        self.llm = llm_bridge
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        self._workspace_dir = os.path.dirname(os.path.abspath(CATALOG_PATH))
        self.verified_metadata = {}
        self.content_cache = {}
        self._load_reference_stores()

    def _load_reference_stores(self):
        verified_path = os.path.join(self._workspace_dir, "ai_agent_server", "bookmarks_verified_metadata.json")
        if os.path.exists(verified_path):
            try:
                with open(verified_path, "r", encoding="utf-8") as f:
                    self.verified_metadata = json.load(f)
            except Exception:
                self.verified_metadata = {}

        cache_path = os.path.join(self._workspace_dir, "ai_agent_server", "bookmarks_content_cache.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    self.content_cache = json.load(f)
            except Exception:
                self.content_cache = {}

    def _is_bot_challenge_page(self, title, body_text=""):
        t_low = str(title or "").strip().lower()
        b_low = str(body_text or "").strip().lower()[:1500]
        challenge_titles = (
            "just a moment...",
            "just a moment",
            "attention required!",
            "attention required | cloudflare",
            "checking your browser",
            "security verification",
            "ddos-guard",
            "access denied",
            "one moment, please...",
            "request unsuccessful",
            "pardon our interruption",
            "bot verification",
        )
        if any(t_low == ct or t_low.startswith(ct) for ct in challenge_titles):
            return True
        challenge_body_markers = (
            "this website uses a security service to protect against malicious bots",
            "performing security verification",
            "verifies you are not a bot",
            "enable javascript and cookies to continue",
            "checking if the site connection is secure",
            "ray id:",
            "incapsula incident id",
            "request unsuccessful. incapsula",
            "powered by imperva",
            "datadome",
            "perimeterx",
            "please verify you are a human",
        )
        if any(cm in b_low for cm in challenge_body_markers) and len(b_low) < 1200:
            return True
        return False

    def _is_generic_placeholder_entry(self, entry):
        if not isinstance(entry, dict):
            return False
        desc = str(entry.get("description") or "").strip()
        summary = str(entry.get("content_summary") or entry.get("text") or "").strip()
        if desc.startswith("Technical engineering resource providing architectural guidance, operational standards, and best practices for "):
            return True
        if summary.startswith("This technical reference for ") and "Industry Standards & Technical References" in summary:
            return True
        return False

    def _lookup_verified_entry(self, url):
        if not url:
            return None
        cand = None
        if url in self.verified_metadata:
            cand = self.verified_metadata[url]
        elif "#" not in url:
            alt = url.rstrip("/") if url.endswith("/") else (url + "/")
            if alt in self.verified_metadata:
                cand = self.verified_metadata[alt]
        if cand and (
            self._is_bot_challenge_page(
                cand.get("title", ""),
                cand.get("description", "") + " " + cand.get("content_summary", "")
            )
            or self._is_generic_placeholder_entry(cand)
        ):
            return None
        return cand

    def _save_browser_content_to_cache(self, final_url, clean_url, extracted):
        if self._is_bot_challenge_page(extracted.get("title", ""), extracted.get("body_text", "")):
            return
        cache_path = os.path.join(self._workspace_dir, "ai_agent_server", "bookmarks_content_cache.json")
        entry = {
            "title": extracted.get("title", ""),
            "text": extracted.get("body_text", ""),
            "meta_description": extracted.get("meta_description", ""),
            "headings": extracted.get("headings", ""),
            "company_context": extracted.get("company_context", ""),
            "len": len(extracted.get("body_text", "")),
            "inspected_via": "/browser"
        }
        self.content_cache[final_url] = entry
        if clean_url != final_url:
            self.content_cache[clean_url] = entry
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(self.content_cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _discover_company_context(self, target_url, existing_company_context="", inspect_domain_pages=True):
        """
        Inspects the company/brand's root domain (and /about or /solutions pages under the same domain
        via /browser when needed) to determine the company's core business, industry vertical, and
        flagship products/services so bookmark summaries reflect their real core business context.
        """
        if existing_company_context and len(str(existing_company_context).strip()) > 35:
            return str(existing_company_context).strip()

        parsed = urlparse(target_url)
        netloc = (parsed.netloc or "").lower()
        if not netloc:
            return ""

        # Skip generic code/video/standard hosts or internal F5 hosts where company context is already F5
        skip_domains = (
            "f5.com", "nginx.com", "volterra.io", "f5net.com", "f5se.com", "github.com",
            "gitlab.com", "youtube.com", "youtu.be", "tools.ietf.org", "rfc-editor.org",
            "kubernetes.io", "sigs.k8s.io", "google.com", "microsoft.com", "sharepoint.com",
            "salesforce.com", "force.com", "highspot.com", "aha.io"
        )
        if any(netloc == d or netloc.endswith("." + d) for d in skip_domains):
            return ""

        scheme = parsed.scheme or "https"
        root_url = f"{scheme}://{netloc}"
        domain_cache_key = f"__company_context__:{netloc}"
        cached_ctx = self.content_cache.get(domain_cache_key)
        if isinstance(cached_ctx, dict) and cached_ctx.get("company_context"):
            return str(cached_ctx["company_context"]).strip()

        # Check if root_url or root_url + '/en' is already in content_cache
        snippets = []
        for cand_u in (root_url, f"{root_url}/en", f"{root_url}/about", f"{root_url}/en/about/overview"):
            c_entry = self.content_cache.get(cand_u) or self.content_cache.get(cand_u.rstrip("/"))
            if isinstance(c_entry, dict) and not self._is_bot_challenge_page(c_entry.get("title", ""), c_entry.get("text", "")):
                c_title = str(c_entry.get("title") or "").strip()
                c_meta = str(c_entry.get("meta_description") or "").strip()
                c_text = str(c_entry.get("text") or "")[:900].strip()
                if c_title or c_meta or c_text:
                    snippets.append(" ".join(x for x in (c_title, c_meta, c_text) if x))

        # If not cached and live domain inspection is enabled (and target_url is a subpage), inspect root page via /browser
        path_clean = (parsed.path or "").strip("/")
        if not snippets and inspect_domain_pages and path_clean and path_clean not in ("en", "de", "fr", "es"):
            lang_prefix = ""
            first_seg = path_clean.split("/")[0].lower()
            if first_seg in ("en", "en-us", "en-gb", "de", "fr", "es"):
                lang_prefix = f"/{first_seg}"
            probe_urls = [f"{root_url}{lang_prefix}" if lang_prefix else root_url]
            for p_url in probe_urls[:1]:
                res = self._inspect_via_live_browser(p_url, allow_llm_fallback=False)
                if isinstance(res, dict) and not self._is_bot_challenge_page(res.get("title", ""), res.get("body_text", "")):
                    r_title = str(res.get("title") or "").strip()
                    r_meta = str(res.get("meta_description") or "").strip()
                    r_body = str(res.get("body_text") or "")[:900].strip()
                    if r_title or r_meta or r_body:
                        snippets.append(" ".join(x for x in (r_title, r_meta, r_body) if x))

        company_summary = ""
        if snippets:
            combined = re.sub(r"\s+", " ", " ".join(snippets)).strip()
            sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", combined) if len(s.strip()) >= 35]
            company_summary = " ".join(sents[:3])[:480].strip()

        if company_summary:
            self.content_cache[domain_cache_key] = {
                "company_context": company_summary,
                "domain": netloc,
                "inspected_via": "/browser"
            }
            cache_path = os.path.join(self._workspace_dir, "ai_agent_server", "bookmarks_content_cache.json")
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(self.content_cache, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        return company_summary

    def _discover_browser_ws_endpoint(self):
        """
        Discovers a direct browser-level CDP WebSocket URL from DevToolsActivePort
        (supported by Chrome 136+ chrome://inspect/#remote-debugging even when HTTP /json/* is disabled).
        NEVER connects to a headless browser.
        """
        import socket

        home = os.path.expanduser("~")
        port_files = [
            os.path.join(home, ".gemini", "antigravity-browser-profile", "DevToolsActivePort"),
            os.path.join(home, ".gemini", "antigravity", "browser-profile", "DevToolsActivePort"),
            os.path.join(home, "Library", "Application Support", "Google", "Chrome", "DevToolsActivePort"),
        ]
        try:
            out = subprocess.check_output(["ps", "auxww"], text=True, stderr=subprocess.DEVNULL, timeout=2)
            for line in out.splitlines():
                if "--headless" in line or "agy_chrome" in line:
                    continue
                for m in re.finditer(r"--user-data-dir=([^\s\"']+)", line):
                    udir = m.group(1).strip()
                    if "agy_chrome" in udir:
                        continue
                    pf = os.path.join(udir, "DevToolsActivePort")
                    if pf not in port_files:
                        port_files.insert(0, pf)
        except Exception:
            pass

        for pf in port_files:
            try:
                if not os.path.exists(pf):
                    continue
                with open(pf, "r", encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f.read().splitlines() if ln.strip()]
                if len(lines) >= 2 and lines[0].isdigit() and lines[1].startswith("/devtools/"):
                    port = int(lines[0])
                    ws_path = lines[1]
                    if port <= 0 or port == 9233:
                        continue
                    with socket.create_connection(("127.0.0.1", port), timeout=0.6):
                        pass
                    return f"ws://127.0.0.1:{port}{ws_path}"
            except Exception:
                continue
        return None

    def _inspect_via_browser_ws(self, browser_ws_url, target_url, js_extract_sync, handshake_timeout=25.0):
        """
        Inspects target_url over a browser-level CDP WebSocket (Target.createTarget +
        Target.attachToTarget(flatten=True) + Runtime.evaluate) when HTTP /json/* endpoints
        are disabled by Chrome 136+ native remote debugging.
        """
        import base64
        import socket
        import struct

        parsed = urlparse(browser_ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 9222
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        sock = socket.create_connection((host, port), timeout=handshake_timeout)
        opened_target_id = None
        try:
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            handshake = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            sock.sendall(handshake.encode("utf-8"))
            resp_buf = b""
            while b"\r\n\r\n" not in resp_buf:
                chunk = sock.recv(4096)
                if not chunk:
                    raise RuntimeError("CDP Browser WebSocket handshake EOF (remote debugging dialog denied or closed)")
                resp_buf += chunk
            header_line = resp_buf.split(b"\r\n", 1)[0].decode("utf-8", errors="replace")
            if "101" not in header_line:
                raise RuntimeError(f"CDP Browser WebSocket handshake rejected: {header_line}")

            sock.settimeout(6.0)
            leftover = resp_buf.split(b"\r\n\r\n", 1)[1]

            def send_ws_json(obj):
                payload = json.dumps(obj).encode("utf-8")
                mask_key = os.urandom(4)
                header = bytearray([0x81])
                length = len(payload)
                if length < 126:
                    header.append(0x80 | length)
                elif length < 65536:
                    header.append(0x80 | 126)
                    header.extend(struct.pack("!H", length))
                else:
                    header.append(0x80 | 127)
                    header.extend(struct.pack("!Q", length))
                header.extend(mask_key)
                masked = bytearray(length)
                for i in range(length):
                    masked[i] = payload[i] ^ mask_key[i % 4]
                sock.sendall(header + masked)

            def recv_exact(n):
                nonlocal leftover
                while len(leftover) < n:
                    chunk = sock.recv(65536)
                    if not chunk:
                        raise RuntimeError("CDP Browser WebSocket unexpected EOF")
                    leftover += chunk
                out, leftover = leftover[:n], leftover[n:]
                return out

            def recv_ws_json():
                while True:
                    b1, b2 = recv_exact(2)
                    opcode = b1 & 0x0F
                    masked = bool(b2 & 0x80)
                    length = b2 & 0x7F
                    if length == 126:
                        length = struct.unpack("!H", recv_exact(2))[0]
                    elif length == 127:
                        length = struct.unpack("!Q", recv_exact(8))[0]
                    mask_bytes = recv_exact(4) if masked else b""
                    data = bytearray(recv_exact(length))
                    if masked:
                        for i in range(length):
                            data[i] ^= mask_bytes[i % 4]
                    if opcode == 0x8:
                        raise RuntimeError("CDP Browser WebSocket closed by peer")
                    if opcode == 0x9:
                        # Respond with pong frame
                        pong = bytearray([0x8A, 0x80]) + os.urandom(4)
                        sock.sendall(pong)
                        continue
                    if opcode == 0x1:
                        return json.loads(data.decode("utf-8", errors="replace"))

            def call_cdp(msg_id, method, params=None, session_id=None, call_timeout=5.0):
                req = {"id": msg_id, "method": method, "params": params or {}}
                if session_id:
                    req["sessionId"] = session_id
                send_ws_json(req)
                deadline = time.time() + call_timeout
                while time.time() < deadline:
                    msg = recv_ws_json()
                    if msg.get("id") == msg_id:
                        if "error" in msg:
                            raise RuntimeError(f"CDP {method} error: {msg['error']}")
                        return msg.get("result") or {}
                raise TimeoutError(f"CDP {method} timed out")

            targets_res = call_cdp(1, "Target.getTargets", {})
            target_infos = targets_res.get("targetInfos") or []
            norm_target = normalize_url_for_comparison(target_url)
            target_id = None
            for t in target_infos:
                if t.get("type") == "page" and normalize_url_for_comparison(t.get("url", "")) == norm_target:
                    target_id = t.get("targetId")
                    break
            if not target_id:
                create_res = call_cdp(2, "Target.createTarget", {"url": target_url})
                target_id = create_res.get("targetId")
                opened_target_id = target_id
            if not target_id:
                return None

            attach_res = call_cdp(3, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
            session_id = attach_res.get("sessionId")
            if not session_id:
                return None

            expected_k_match = re.search(r"/article/(K\d+)", target_url, re.IGNORECASE)
            expected_k = expected_k_match.group(1).upper() if expected_k_match else None
            last_valid = None
            for attempt in range(18):
                time.sleep(0.45)
                try:
                    eval_res = call_cdp(
                        100 + attempt,
                        "Runtime.evaluate",
                        {
                            "expression": js_extract_sync,
                            "awaitPromise": False,
                            "returnByValue": True,
                        },
                        session_id=session_id,
                        call_timeout=2.5,
                    )
                    res = (eval_res.get("result") or {}).get("value")
                except Exception:
                    res = None
                if isinstance(res, dict):
                    u = res.get("final_url", "")
                    txt = (res.get("body_text") or "").strip()
                    ttl = (res.get("title") or "").strip()
                    rstate = res.get("ready_state", "")
                    if self._is_bot_challenge_page(ttl, txt):
                        continue
                    if expected_k:
                        m_dom_k = re.search(r"\b(K\d{4,10})\s*:", (ttl + " " + txt[:350]), re.IGNORECASE)
                        if m_dom_k and m_dom_k.group(1).upper() != expected_k:
                            continue
                    if u and u != "about:blank" and (ttl or txt):
                        last_valid = res
                    if (
                        u
                        and u != "about:blank"
                        and rstate == "complete"
                        and len(txt) > 140
                        and not txt.lower().startswith("loading")
                        and (not expected_k or expected_k in (ttl + " " + txt[:450]).upper())
                    ):
                        return res
            if last_valid:
                return last_valid
        except Exception:
            return None
        finally:
            if opened_target_id:
                try:
                    send_ws_json({"id": 999, "method": "Target.closeTarget", "params": {"targetId": opened_target_id}})
                except Exception:
                    pass
            try:
                sock.close()
            except Exception:
                pass
        return None

    def _discover_browser_cdp_port(self):
        """
        Discovers the active /browser subagent Chrome DevTools Protocol (CDP) port.
        NEVER launches or connects to a headless browser.
        """
        home = os.path.expanduser("~")
        port_files = [
            os.path.join(home, ".gemini", "antigravity-browser-profile", "DevToolsActivePort"),
            os.path.join(home, ".gemini", "antigravity", "browser-profile", "DevToolsActivePort"),
            os.path.join(home, "Library", "Application Support", "Google", "Chrome", "DevToolsActivePort"),
        ]
        candidate_ports = []
        try:
            # Use 'auxww' so macOS BSD ps never truncates long Chrome command lines at 80 columns
            out = subprocess.check_output(["ps", "auxww"], text=True, stderr=subprocess.DEVNULL, timeout=2)
            for line in out.splitlines():
                if "--headless" in line or "agy_chrome" in line:
                    continue
                for m in re.finditer(r"--remote-debugging-port=(\d+)", line):
                    port_num = int(m.group(1))
                    if port_num > 0 and port_num != 9233 and port_num not in candidate_ports:
                        candidate_ports.append(port_num)
                for m in re.finditer(r"--user-data-dir=([^\s\"']+)", line):
                    udir = m.group(1).strip()
                    if "agy_chrome" in udir:
                        continue
                    pf = os.path.join(udir, "DevToolsActivePort")
                    if pf not in port_files:
                        port_files.insert(0, pf)
        except Exception:
            pass
        for pf in port_files:
            try:
                if os.path.exists(pf):
                    with open(pf, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if first_line.isdigit():
                            p_val = int(first_line)
                            if p_val > 0 and p_val != 9233 and p_val not in candidate_ports:
                                candidate_ports.append(p_val)
            except Exception:
                pass
        for p in (9222, 9223, 9224, 9229):
            if p not in candidate_ports:
                candidate_ports.append(p)
        for port in candidate_ports:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.8) as resp:
                    if resp.status == 200:
                        ver_info = json.loads(resp.read().decode("utf-8", errors="replace"))
                        browser_str = str(ver_info.get("Browser") or "")
                        if "HeadlessChrome" in browser_str:
                            continue
                        return port
            except Exception:
                continue
        return None

    def _cdp_ws_eval(self, ws_url, js_expr, timeout=10.0, await_promise=False):
        """Minimal RFC 6455 WebSocket client to evaluate JS in a /browser CDP page target."""
        import base64
        import socket
        import struct

        parsed = urlparse(ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 9222
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            handshake = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            sock.sendall(handshake.encode("utf-8"))
            resp_buf = b""
            while b"\r\n\r\n" not in resp_buf:
                chunk = sock.recv(4096)
                if not chunk:
                    raise RuntimeError("CDP WebSocket handshake EOF")
                resp_buf += chunk

            def send_ws_json(obj):
                payload = json.dumps(obj).encode("utf-8")
                mask_key = os.urandom(4)
                header = bytearray([0x81])
                length = len(payload)
                if length < 126:
                    header.append(0x80 | length)
                elif length < 65536:
                    header.append(0x80 | 126)
                    header.extend(struct.pack("!H", length))
                else:
                    header.append(0x80 | 127)
                    header.extend(struct.pack("!Q", length))
                header.extend(mask_key)
                masked = bytearray(length)
                for i in range(length):
                    masked[i] = payload[i] ^ mask_key[i % 4]
                sock.sendall(header + masked)

            leftover = resp_buf.split(b"\r\n\r\n", 1)[1]

            def recv_exact(n):
                nonlocal leftover
                while len(leftover) < n:
                    chunk = sock.recv(65536)
                    if not chunk:
                        raise RuntimeError("CDP WebSocket unexpected EOF")
                    leftover += chunk
                out, leftover = leftover[:n], leftover[n:]
                return out

            def recv_ws_json():
                while True:
                    b1, b2 = recv_exact(2)
                    opcode = b1 & 0x0F
                    masked = bool(b2 & 0x80)
                    length = b2 & 0x7F
                    if length == 126:
                        length = struct.unpack("!H", recv_exact(2))[0]
                    elif length == 127:
                        length = struct.unpack("!Q", recv_exact(8))[0]
                    mask_bytes = recv_exact(4) if masked else b""
                    data = bytearray(recv_exact(length))
                    if masked:
                        for i in range(length):
                            data[i] ^= mask_bytes[i % 4]
                    if opcode == 0x8:
                        raise RuntimeError("CDP WebSocket closed by peer")
                    if opcode == 0x9:
                        continue
                    if opcode == 0x1:
                        return json.loads(data.decode("utf-8", errors="replace"))

            send_ws_json({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_expr,
                    "awaitPromise": bool(await_promise),
                    "returnByValue": True
                }
            })
            deadline = time.time() + timeout
            while time.time() < deadline:
                msg = recv_ws_json()
                if msg.get("id") == 1:
                    return msg.get("result", {}).get("result", {}).get("value")
        finally:
            try:
                sock.close()
            except Exception:
                pass
        return None

    def _inspect_via_macos_open_tab(self, target_url, js_extract_sync):
        """
        Inspects ONLY the tab matching `target_url` in the user's running macOS Google Chrome
        or Microsoft Edge via JXA (osascript) when 'Allow JavaScript from Apple Events' is enabled.
        Never executes JavaScript on any other open tabs.
        """
        if sys.platform != "darwin":
            return None
        norm_target = normalize_url_for_comparison(target_url)
        jxa_script = """
        ObjC.import('stdlib');
        const targetUrl = $.getenv('TARGET_URL') || '';
        const normTarget = $.getenv('NORM_TARGET') || '';
        const jsCode = $.getenv('JS_EXTRACT_CODE') || '';
        function norm(u) {
            let s = String(u || '').trim();
            try {
                const parsed = new URL(s);
                const host = parsed.hostname.toLowerCase().replace(/^www\\./, '');
                const path = parsed.pathname.replace(/\\/+$/, '') || '/';
                return parsed.protocol.toLowerCase() + '//' + host + path + (parsed.search || '');
            } catch (e) {
                return s.replace(/\\/+$/, '').toLowerCase();
            }
        }
        const normTargetStrict = norm(targetUrl);
        const browsers = ['Google Chrome', 'Microsoft Edge'];
        for (const bName of browsers) {
            try {
                const app = Application(bName);
                if (!app.running()) continue;
                const wins = app.windows();
                let matchedTab = null;
                for (let w = 0; w < wins.length; w++) {
                    const tabs = wins[w].tabs();
                    for (let t = 0; t < tabs.length; t++) {
                        const u = tabs[t].url();
                        if (norm(u) === normTargetStrict || norm(u) === normTarget) {
                            matchedTab = tabs[t];
                            break;
                        }
                    }
                    if (matchedTab) break;
                }
                if (matchedTab) {
                    const out = matchedTab.execute({javascript: 'JSON.stringify(' + jsCode + ')'});
                    if (out) {
                        console.log(out);
                        $.exit(0);
                    }
                }
            } catch (e) {
                console.log('ERR:' + String(e));
            }
        }
        """
        env = os.environ.copy()
        env["TARGET_URL"] = target_url
        env["NORM_TARGET"] = norm_target
        env["JS_EXTRACT_CODE"] = js_extract_sync
        try:
            proc = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", jxa_script],
                env=env,
                capture_output=True,
                text=True,
                timeout=20.0,
            )
            combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            for line in combined.splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    data = json.loads(line)
                    if isinstance(data, dict) and (data.get("title") or data.get("body_text")):
                        return data
        except Exception:
            pass
        return None

    def _inspect_via_live_browser(self, target_url, allow_llm_fallback=False):
        """
        Inspects target_url strictly using the active /browser subagent Chrome instance
        (sharing active user SSO sessions). NEVER uses a headless browser or --dump-dom.
        """
        js_extract_sync = """
        (() => {
          const final_url = window.location.href || '';
          const ready_state = document.readyState || '';
          let title = document.title || '';
          const metaDescEl = document.querySelector('meta[name="description"]') || document.querySelector('meta[property="og:description"]');
          let meta_description = metaDescEl ? (metaDescEl.getAttribute('content') || '') : '';
          const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4')).map(h => (h.innerText || '').trim()).filter(Boolean).slice(0, 10);
          let body_text = '';
          const stripNoiseSelector = 'header, nav, footer, [role="navigation"], [class*="cookie" i], [id*="onetrust" i], script, style, noscript, form, select, option, label, button, input, textarea';

          let anchorSectionText = '';
          const rawHash = (window.location.hash || '').replace(/^#/, '').trim();
          if (rawHash && !rawHash.startsWith(':~:')) {
            const anchorEl = document.getElementById(rawHash) || document.querySelector(`[name="${CSS.escape(rawHash)}"]`);
            if (anchorEl) {
              const secHeadingEl = anchorEl.matches('h1, h2, h3, h4, h5, h6') ? anchorEl : anchorEl.querySelector('h1, h2, h3, h4, h5, h6, .title');
              const secHeading = secHeadingEl ? (secHeadingEl.innerText || '').trim() : '';
              if (secHeading && !title.toLowerCase().includes(secHeading.toLowerCase())) {
                title = title.includes('|') ? title.replace('|', `— ${secHeading} |`) : `${title} — ${secHeading}`;
              }
              const container = anchorEl.closest('section, .section, .topic, article') || anchorEl.parentElement;
              if (container) {
                const cClone = container.cloneNode(true);
                cClone.querySelectorAll(stripNoiseSelector).forEach(el => el.remove());
                anchorSectionText = (cClone.innerText || '').trim();
              }
            }
          }

          const mainEl = document.querySelector('main, [role="main"], article, .article-content, .content-body');
          if (mainEl) {
            const mClone = mainEl.cloneNode(true);
            mClone.querySelectorAll(stripNoiseSelector).forEach(el => el.remove());
            const mText = (mClone.innerText || '').trim();
            if (mText.length > 140) body_text = mText;
          }
          if (!body_text && document.body) {
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll(stripNoiseSelector).forEach(el => el.remove());
            body_text = (clone.innerText || document.body.innerText || '').trim();
          }
          if (anchorSectionText && anchorSectionText.length > 40) {
            body_text = `${anchorSectionText}\n\n${body_text}`;
          }
          const has_f5_logo = !!(
            document.querySelector('img[alt*="F5" i], img[src*="f5" i], svg[aria-label*="F5" i], [class*="f5-logo" i]') ||
            title.includes('F5')
          );
          return { final_url, ready_state, title, meta_description, headings, body_text, has_f5_logo };
        })()
        """
        macos_tab_res = self._inspect_via_macos_open_tab(target_url, js_extract_sync)
        if macos_tab_res:
            return macos_tab_res
        cdp_port = self._discover_browser_cdp_port()
        if cdp_port:
            opened_target_id = None
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/list", timeout=2.0) as resp:
                    tabs = json.loads(resp.read().decode("utf-8", errors="replace"))
                norm_target = normalize_url_for_comparison(target_url)
                ws_url = None
                for t in tabs:
                    if t.get("type") == "page" and normalize_url_for_comparison(t.get("url", "")) == norm_target:
                        ws_url = t.get("webSocketDebuggerUrl")
                        break
                if not ws_url:
                    from urllib.parse import quote
                    new_tab_url = f"http://127.0.0.1:{cdp_port}/json/new?{quote(target_url, safe=':/?&=#%')}"
                    try:
                        req = urllib.request.Request(new_tab_url, method="PUT")
                        with urllib.request.urlopen(req, timeout=4.0) as resp:
                            tab_info = json.loads(resp.read().decode("utf-8", errors="replace"))
                    except Exception:
                        with urllib.request.urlopen(new_tab_url, timeout=4.0) as resp:
                            tab_info = json.loads(resp.read().decode("utf-8", errors="replace"))
                    opened_target_id = tab_info.get("id")
                    ws_url = tab_info.get("webSocketDebuggerUrl")

                if ws_url:
                    expected_k_match = re.search(r"/article/(K\d+)", target_url, re.IGNORECASE)
                    expected_k = expected_k_match.group(1).upper() if expected_k_match else None
                    last_valid = None
                    for attempt in range(18):
                        time.sleep(0.45)
                        try:
                            res = self._cdp_ws_eval(ws_url, js_extract_sync, timeout=2.5, await_promise=False)
                        except Exception:
                            res = None
                        if isinstance(res, dict):
                            u = res.get("final_url", "")
                            txt = (res.get("body_text") or "").strip()
                            ttl = (res.get("title") or "").strip()
                            rstate = res.get("ready_state", "")
                            if self._is_bot_challenge_page(ttl, txt):
                                continue
                            if expected_k:
                                m_dom_k = re.search(r"\b(K\d{4,10})\s*:", (ttl + " " + txt[:350]), re.IGNORECASE)
                                if m_dom_k and m_dom_k.group(1).upper() != expected_k:
                                    continue
                            if u and u != "about:blank" and (ttl or txt):
                                last_valid = res
                            if (
                                u
                                and u != "about:blank"
                                and rstate == "complete"
                                and len(txt) > 140
                                and not txt.lower().startswith("loading")
                                and (not expected_k or expected_k in (ttl + " " + txt[:450]).upper())
                            ):
                                return res
                    if last_valid:
                        return last_valid
            except Exception:
                pass
            finally:
                if opened_target_id:
                    try:
                        urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{opened_target_id}", timeout=1.5).read()
                    except Exception:
                        pass
        browser_ws_url = self._discover_browser_ws_endpoint()
        if browser_ws_url:
            ws_res = self._inspect_via_browser_ws(browser_ws_url, target_url, js_extract_sync)
            if ws_res:
                return ws_res
        return None

    def fetch_page(self, url, browser_data=None):
        """
        Inspects website content strictly via /browser subagent (`browser_data` payload,
        active /browser subagent Chrome session, or previously /browser-verified metadata/content cache).
        NEVER uses a headless browser or raw urllib scraping.
        """
        from batch_enrich_all import clean_bookmark_url
        from update_and_reorganize_bookmarks import is_valid_redirect

        # Reload stores so any fresh /browser inspection written to disk is immediately visible
        self._load_reference_stores()

        clean_url = clean_bookmark_url(url.strip())
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        orig_parsed = urlparse(clean_url)
        orig_fragment = orig_parsed.fragment
        final_url = clean_url
        html_text = ""
        error = None

        b_data = browser_data if isinstance(browser_data, dict) else {}
        if b_data and self._is_bot_challenge_page(b_data.get("title", ""), b_data.get("body_text", "") or b_data.get("text", "")):
            b_data = {}
        ver_entry_initial = self._lookup_verified_entry(clean_url)
        cached_initial = self.content_cache.get(clean_url) or self.content_cache.get(clean_url.rstrip("/")) or self.content_cache.get(clean_url + "/")
        if cached_initial and self._is_bot_challenge_page(cached_initial.get("title", ""), cached_initial.get("text", "")):
            cached_initial = None

        # If no browser_data was explicitly provided and URL is not yet in verified/cache, live-inspect via /browser!
        if not (b_data.get("title") or b_data.get("body_text") or b_data.get("text")) and not (
            ver_entry_initial or (cached_initial and (cached_initial.get("text") or cached_initial.get("title")))
        ):
            live_b_data = self._inspect_via_live_browser(clean_url)
            if isinstance(live_b_data, dict):
                b_data = live_b_data

        # 1. Check if /browser passed or returned explicit live inspection data in b_data
        auth_redirect_indicators = [
            "/signin", "/login", "login.microsoftonline.com", "f5.okta.com", "login.f5.com",
            "accounts.google.com", "openid-connect/auth", "oauth2/authorize", "ves.volterra.io/auth",
            "myapplications.microsoft.com", "weblogin.f5net.com"
        ]
        if b_data.get("final_url"):
            cand_final = clean_bookmark_url(str(b_data["final_url"]).strip())
            if orig_fragment and "#" not in cand_final:
                cand_final = f"{cand_final}#{orig_fragment}"
            is_cand_auth = (
                any(ind in cand_final.lower() for ind in auth_redirect_indicators)
                and not any(ind in clean_url.lower() for ind in auth_redirect_indicators)
            )
            if not is_cand_auth:
                if normalize_url_for_comparison(cand_final) == normalize_url_for_comparison(clean_url):
                    final_url = cand_final
                elif is_valid_redirect(clean_url, cand_final):
                    final_url = cand_final
                elif b_data.get("is_dead_page") is not False:
                    return clean_url, "", {
                        "is_dead_page": True,
                        "dead_reason": f"Dead redirect to generic portal ({cand_final})",
                        "http_status": 404
                    }, f"Dead redirect to generic portal ({cand_final})"

        # 2. Check if we have a /browser-verified canonical URL mapping
        ver_entry = self._lookup_verified_entry(final_url) or self._lookup_verified_entry(clean_url)
        if ver_entry and ver_entry.get("url") and not b_data.get("final_url"):
            ver_url = ver_entry["url"]
            if orig_fragment and "#" in ver_url:
                final_url = ver_url.split("#")[0] + "#" + orig_fragment
            elif orig_fragment and "#" not in ver_url:
                final_url = ver_url + "#" + orig_fragment
            else:
                final_url = ver_url

        cached_item = (
            self.content_cache.get(final_url)
            or self.content_cache.get(clean_url)
            or self.content_cache.get(final_url.rstrip("/"))
            or self.content_cache.get(final_url.rstrip("/") + "/")
        )
        if cached_item and self._is_bot_challenge_page(cached_item.get("title", ""), cached_item.get("text", "")):
            cached_item = None

        # 3. Extract title, body_text, headings, meta_description, and company_context from /browser data or verified cache
        raw_title = str(
            b_data.get("title")
            or (cached_item.get("title") if cached_item else "")
            or (ver_entry.get("title") if ver_entry else "")
            or ""
        ).strip()
        raw_body = str(
            b_data.get("body_text")
            or b_data.get("text")
            or (cached_item.get("text") if cached_item else "")
            or (cached_item.get("body_text") if cached_item else "")
            or (ver_entry.get("content_summary") if ver_entry else "")
            or (ver_entry.get("text_sample") if ver_entry else "")
            or ""
        ).strip()
        raw_meta = str(
            b_data.get("meta_description")
            or (cached_item.get("meta_description") if cached_item else "")
            or (cached_item.get("description") if cached_item else "")
            or (ver_entry.get("description") if ver_entry else "")
            or (ver_entry.get("meta_desc") if ver_entry else "")
            or ""
        ).strip()
        raw_headings = (
            b_data.get("headings")
            or (cached_item.get("headings") if cached_item else "")
            or (ver_entry.get("headings") if ver_entry else "")
        )
        if isinstance(raw_headings, list):
            raw_headings = " | ".join(
                (h.get("text", "") if isinstance(h, dict) else str(h))
                for h in raw_headings[:6]
            )
        raw_company_ctx = str(
            b_data.get("company_context")
            or b_data.get("brand_context")
            or (cached_item.get("company_context") if cached_item else "")
            or (ver_entry.get("company_context") if ver_entry else "")
            or ""
        ).strip()
        # Automatically discover company/brand core business from the root domain when adding/inspecting via /browser
        raw_company_ctx = self._discover_company_context(
            final_url,
            existing_company_context=raw_company_ctx,
            inspect_domain_pages=bool(b_data)
        )

        extracted = {
            "title": raw_title,
            "meta_description": raw_meta,
            "headings": str(raw_headings or ""),
            "company_context": raw_company_ctx,
            "body_text": raw_body[:35000],
            "footer_text": "",
            "has_f5_logo": bool(b_data.get("has_f5_logo", False)),
            "has_f5_theme": False,
            "f5_markers": []
        }

        # 4. Check if /browser reported a dead/404 page
        page_title_lower = raw_title.lower()
        body_lower = raw_body[:1500].lower()
        soft_404_titles = [
            "page not found", "404 not found", "404 - page not found",
            "oops! that page doesn’t exist or is private", "oops! that page doesn't exist or is private",
            "help centre closed", "help center closed", "article not found", "file not found"
        ]
        is_dead_page = bool(b_data.get("is_dead_page", False))
        dead_reason = str(b_data.get("dead_reason") or "")
        if any(st in page_title_lower for st in soft_404_titles) or any(
            sb in body_lower for sb in ["help centre closed", "help center closed", "trying to reach no longer exists", "page you were looking for doesn't exist"]
        ):
            is_dead_page = True
            dead_reason = dead_reason or f"Soft-404 / Decommissioned page ({raw_title or 'Not Found'})"

        if is_dead_page:
            extracted["is_dead_page"] = True
            extracted["dead_reason"] = dead_reason or "Target webpage does not exist or is unreachable in /browser"
            extracted["http_status"] = int(b_data.get("http_status", 404))
            return final_url, "", extracted, extracted["dead_reason"]

        # 5. Check for SSO / Login Wall barriers reported by /browser or detected in title/URL
        auth_title_markers = [
            "sign in", "sign-in", "log in", "login", "single sign-on", "sso login", "f5 networks single sign-on",
            "f5 single sign-on", "f5 highspot sign in", "okta single sign-on", "sign in to your account", "continue"
        ]
        is_auth_barrier = bool(b_data.get("is_auth_barrier", False))
        b_final_lower = str(b_data.get("final_url") or "").lower()
        if b_final_lower and any(ind in b_final_lower for ind in auth_redirect_indicators) and not any(ind in clean_url.lower() for ind in auth_redirect_indicators):
            is_auth_barrier = True
        is_title_auth = any(
            page_title_lower == m or page_title_lower.startswith(m + " ") or f"| {m}" in page_title_lower or f"- {m}" in page_title_lower
            for m in auth_title_markers
        )
        if is_title_auth and not any(k in final_url.lower() for k in ["signin", "login", "auth"]):
            is_auth_barrier = True

        # If /browser hit a login wall and we do not have verified non-login metadata for this exact URL, block!
        if is_auth_barrier and not ver_entry:
            extracted["is_auth_barrier"] = True
            extracted["auth_target_url"] = final_url
            extracted["auth_redirect_url"] = str(b_data.get("final_url") or "")
            extracted["auth_message"] = (
                f"Login / SSO wall encountered in /browser for {final_url} "
                f"(detected title: '{raw_title or 'Login Page'}'). Please log in via the browser first so /browser can inspect the real page content."
            )
            return final_url, "", extracted, extracted["auth_message"]

        # 6. Enforce /browser-only inspection: if neither browser_data nor verified/cached /browser content exists, block!
        has_browser_data = bool(b_data and (b_data.get("title") or b_data.get("body_text") or b_data.get("text")))
        has_verified_data = bool(ver_entry or (cached_item and (cached_item.get("text") or cached_item.get("title"))))
        if not has_browser_data and not has_verified_data:
            extracted["requires_browser_inspection"] = True
            extracted["browser_message"] = (
                f"Could not read the open browser tab for {final_url}. "
                f"To let the server inspect tabs you already have open in Chrome with zero popups, enable "
                f"'View > Developer > Allow JavaScript from Apple Events' in Chrome's top menu bar "
                f"(or click 'Allow' on Chrome's 'Allow remote debugging?' dialog)."
            )
            return final_url, "", extracted, extracted["browser_message"]

        # 7. Persist new /browser-extracted content into bookmarks_content_cache.json
        if has_browser_data and not is_auth_barrier:
            self._save_browser_content_to_cache(final_url, clean_url, extracted)

        return final_url, html_text, extracted, error

    def detect_official_f5(self, url, final_url, html_text, extracted):
        u_lower = (final_url or url).lower()
        netloc = urlparse(u_lower).netloc
        is_official = any(k in netloc for k in [
            "f5.com", "nginx.com", "volterra.io", "f5net.com", "f5se.com", "calypsoai.app", "aha.io", "heyhack.com"
        ])
        if "my.f5.com" in netloc or "/article/k" in u_lower:
            return is_official, "knowledge-base"
        if any(d in netloc for d in ["clouddocs.f5.com", "techdocs.f5.com", "docs.f5.com", "docs.cloud.f5.com", "docs.nginx.com", "help.ai.f5.com", "www.f5.com"]) or netloc == "f5.com":
            return is_official, "official-docs"
        if any(d in netloc for d in ["f5net.com", "sharepoint.com", "highspot.com", "salesforce.com", "force.com", "tryopine.com", "aha.io"]):
            return is_official, "internal-portal"
        if "community.f5.com" in netloc or "devcentral.f5.com" in netloc:
            return is_official, "community-article"
        if "github.com" in netloc:
            return is_official, "github"
        if "udf.f5.com" in netloc:
            return is_official, "lab-environment"
        if "youtube.com" in netloc:
            return is_official, "video-demonstration"
        if "tools.ietf.org" in netloc or "rfc-editor.org" in netloc:
            return is_official, "rfc-standard"
        return is_official, "external-resource"

    def detect_vpn(self, url, final_url, html_text):
        from batch_enrich_all import is_vpn_url
        return is_vpn_url(final_url or url)

    def inspect_and_enrich(self, raw_url, browser_data=None, notes=None):
        from batch_enrich_all import (
            clean_card_title, summarize_text, generate_domain_summary,
            ensure_summary_length, enrich_tags, is_vpn_url, format_clean_description,
            extract_core_description
        )
        from update_and_reorganize_bookmarks import assign_hierarchy

        final_url, html_text, extracted, error = self.fetch_page(raw_url, browser_data=browser_data)
        if extracted.get("is_dead_page"):
            return {
                "url": final_url,
                "raw_url": raw_url,
                "is_dead_page": True,
                "dead_reason": extracted.get("dead_reason", "Target webpage does not exist or is unreachable")
            }
        if extracted.get("is_auth_barrier"):
            return {
                "url": final_url,
                "raw_url": raw_url,
                "is_auth_barrier": True,
                "auth_message": extracted.get("auth_message", "Authentication / SSO login required in /browser before adding this bookmark.")
            }
        if extracted.get("requires_browser_inspection"):
            return {
                "url": final_url,
                "raw_url": raw_url,
                "requires_browser_inspection": True,
                "browser_message": extracted.get("browser_message", "New bookmarks must be inspected via /browser subagent before ingestion.")
            }

        ver_entry = self._lookup_verified_entry(final_url) or self._lookup_verified_entry(raw_url)

        # 1. Determine raw title and clean it via canonical clean_card_title
        raw_title = (
            extracted.get("title")
            or (ver_entry.get("title") if ver_entry else None)
            or urlparse(final_url).path.strip("/").split("/")[-1]
            or final_url
        )
        if ver_entry and ver_entry.get("title") and (not extracted.get("title") or extracted.get("title") in ("MyF5", "F5")):
            raw_title = ver_entry["title"]
        cached_entry = self.content_cache.get(final_url)
        if "/article/K" in final_url and cached_entry and cached_entry.get("title"):
            raw_title = cached_entry["title"]
        cleaned_title = clean_card_title(raw_title, final_url)

        # 2. Preserve legacy_path, visit_count, add_date, icon, notes if available in verified store
        legacy_path = ver_entry.get("legacy_path", []) if ver_entry else []
        visit_count = ver_entry.get("visit_count", 1) if ver_entry else 1
        add_date = ver_entry.get("add_date") if ver_entry else str(int(time.time()))
        icon = ver_entry.get("icon", "") if ver_entry else ""
        explicit_notes = notes
        if explicit_notes is None and isinstance(browser_data, dict):
            if "notes" in browser_data:
                explicit_notes = browser_data.get("notes")
            elif "custom_notes" in browser_data:
                explicit_notes = browser_data.get("custom_notes")
        resolved_notes = (
            str(explicit_notes).strip()
            if explicit_notes is not None
            else (ver_entry.get("notes", "") if ver_entry else "")
        )

        # 3. Assign Strategic Pillar & Subcategory via canonical assign_hierarchy
        bm_stub = {
            "url": final_url,
            "title": cleaned_title,
            "description": extracted.get("meta_description") or (ver_entry.get("description") if ver_entry else ""),
            "notes": resolved_notes,
            "legacy_path": legacy_path
        }
        if ver_entry and ver_entry.get("hierarchy") and not browser_data and not ver_entry["hierarchy"][0].startswith("09."):
            bm_stub["hierarchy"] = ver_entry["hierarchy"]
        pillar, subcategory = assign_hierarchy(bm_stub, force=bool(browser_data))

        # 4. VPN and Official F5 flags
        requires_vpn = is_vpn_url(final_url)
        is_official_f5, source_type = self.detect_official_f5(raw_url, final_url, html_text, extracted)

        # 5. Synthesize Description (110-180 chars) & Content Summary (150-250 words) incorporating company/brand core business
        body_text = (extracted.get("body_text") or "").strip()
        company_ctx = (extracted.get("company_context") or "").strip()
        if company_ctx and body_text and company_ctx[:60].lower() not in body_text.lower():
            combined_body_text = f"{company_ctx}\n\n{body_text}"
        else:
            combined_body_text = body_text or company_ctx
        is_dead_help_center = any(
            err_phrase in body_text.lower()
            for err_phrase in ["help centre closed", "help center closed", "trying to reach no longer exists"]
        )
        if any(k in final_url.lower() for k in [
            "69e1679204ccdfbb76bc6140", "ai-gateway", "k71764661", "k39757430", "k000130285", "k84205182",
            "k17160", "k86112227", "k8986", "k84554955",
            "aha.io", "console.ves.volterra.io/login/start", "f5-emea-ent.console.ves.volterra.io", "app.heyhack.com",
            "ptt.pl.pdsea.f5net.com", "lg.ring.nlnog.net", "network_performance_metrics.html", "aws-resource-init.html",
            "brightcloud.com", "websense-web-filter-security", "bgp.he.net/report/peers", "microservices.io",
            "regex101.com", "string-functions.com/hex-string.aspx", "access.redhat.com/management"
        ]) or final_url.lower().rstrip("/") == "https://clouddocs.f5.com":
            desc, content_summary = generate_domain_summary(final_url, cleaned_title, pillar, subcategory)
        elif len(combined_body_text) > 150 and not is_dead_help_center:
            content_summary = summarize_text(combined_body_text, cleaned_title, final_url, pillar, subcategory)
            meta_desc = (extracted.get("meta_description") or "").strip()
            desc = extract_core_description(body_text or combined_body_text, meta_desc, cleaned_title, final_url, subcategory)
        elif ver_entry and ver_entry.get("description") and ver_entry.get("content_summary"):
            desc = ver_entry["description"]
            content_summary = ensure_summary_length(ver_entry["content_summary"], cleaned_title, pillar, subcategory)
        else:
            desc, content_summary = generate_domain_summary(final_url, cleaned_title, pillar, subcategory)

        # Enforce description bounds (110-180 chars) and summary bounds (150-250 words)
        desc = format_clean_description(desc, cleaned_title, subcategory, final_url)
        content_summary = ensure_summary_length(content_summary, cleaned_title, pillar, subcategory)

        # 6. Enrich tags with full pillar/subcategory/domain alignment
        bm_for_tags = {
            "url": final_url,
            "title": cleaned_title,
            "description": desc,
            "notes": resolved_notes,
            "requires_vpn": requires_vpn,
            "is_official_f5": is_official_f5,
            "tags": ver_entry.get("tags", {"products": [], "topics": [], "source_types": [source_type]}) if ver_entry else {"products": [], "topics": [], "source_types": [source_type]}
        }
        tags = enrich_tags(bm_for_tags, pillar, subcategory)

        content_hash = hashlib.sha256(content_summary.encode("utf-8")).hexdigest()[:16]

        return {
            "url": final_url,
            "title": cleaned_title,
            "description": desc,
            "content_summary": content_summary,
            "content_hash": content_hash,
            "pillar": pillar,
            "subcategory": subcategory,
            "products": tags["products"],
            "topics": tags["topics"],
            "source_types": tags["source_types"],
            "is_official_f5": is_official_f5,
            "requires_vpn": requires_vpn,
            "legacy_path": legacy_path,
            "visit_count": visit_count,
            "add_date": add_date,
            "icon": icon,
            "notes": resolved_notes
        }

    def ingest_and_persist(self, raw_url, browser_data=None, regenerate_html=True, notes=None):
        """Canonical helper to inspect, enrich, format to catalog schema, persist to all stores, and regenerate HTML."""
        enriched = self.inspect_and_enrich(raw_url, browser_data=browser_data, notes=notes)
        if any(enriched.get(k) for k in ("is_dead_page", "is_auth_barrier", "requires_browser_inspection")):
            return enriched

        final_url = enriched.get("url", raw_url)
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        existing_idx, existing_bm = find_catalog_entry(catalog, [raw_url, final_url])
        explicit_notes = notes
        if explicit_notes is None and isinstance(browser_data, dict):
            if "notes" in browser_data:
                explicit_notes = browser_data.get("notes")
            elif "custom_notes" in browser_data:
                explicit_notes = browser_data.get("custom_notes")
        resolved_notes = (
            str(explicit_notes).strip()
            if explicit_notes is not None
            else (
                existing_bm.get("notes", enriched.get("notes", ""))
                if existing_bm
                else enriched.get("notes", "")
            )
        )

        op_label = "update" if existing_idx is not None else "add"
        backup_file = save_catalog_backup(catalog, self._workspace_dir, op_label)

        target_bm = {
            "url": final_url,
            "title": enriched["title"],
            "description": enriched["description"],
            "content_summary": enriched.get("content_summary", ""),
            "content_hash": enriched.get("content_hash", ""),
            "notes": resolved_notes,
            "hierarchy": [enriched["pillar"], enriched["subcategory"]],
            "legacy_path": existing_bm.get("legacy_path", enriched.get("legacy_path", [])) if existing_bm else enriched.get("legacy_path", []),
            "tags": {
                "products": enriched.get("products", []),
                "topics": enriched.get("topics", []),
                "source_types": enriched.get("source_types", [])
            },
            "requires_vpn": enriched.get("requires_vpn", False),
            "is_official_f5": enriched.get("is_official_f5", False),
            "visit_count": existing_bm.get("visit_count", enriched.get("visit_count", 1)) if existing_bm else enriched.get("visit_count", 1),
            "add_date": existing_bm.get("add_date", enriched.get("add_date") or str(int(time.time()))) if existing_bm else (enriched.get("add_date") or str(int(time.time()))),
            "icon": existing_bm.get("icon", enriched.get("icon", "")) if existing_bm else enriched.get("icon", "")
        }

        if existing_idx is not None:
            catalog[existing_idx] = target_bm
        else:
            catalog.append(target_bm)

        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

        self.verified_metadata[final_url] = dict(target_bm)
        vmeta_path = os.path.join(self._workspace_dir, "ai_agent_server", "bookmarks_verified_metadata.json")
        try:
            with open(vmeta_path, "w", encoding="utf-8") as vf:
                json.dump(self.verified_metadata, vf, indent=2, ensure_ascii=False)
        except Exception:
            pass

        if regenerate_html:
            for script_name in ("update_and_reorganize_bookmarks.py", "generate_dark_showcase.py"):
                script_path = os.path.join(self._workspace_dir, script_name)
                if os.path.exists(script_path):
                    subprocess.run([sys.executable, script_path], cwd=self._workspace_dir, check=False)

        return {
            "success": True,
            "is_existing": existing_idx is not None,
            "total_bookmarks": len(catalog),
            "backup_path": backup_file,
            "bookmark": {k: v for k, v in target_bm.items() if k != "icon"}
        }

    def import_bookmarks_batch(
        self,
        items: list,
        dry_run: bool = False,
        skip_existing: bool = True,
        max_items: int = 25,
        regenerate_html: bool = True,
        default_notes: str = None,
    ) -> dict:
        """
        Parse, deduplicate, preview (--dry-run), or live-inspect and ingest a batch of imported bookmarks.
        Supports items parsed from Netscape HTML exports, Chrome/Edge Bookmarks JSON, catalog JSON, or URL lists.
        Never injects unverified stubs: every new bookmark goes through canonical inspect_and_enrich().
        """
        from batch_enrich_all import clean_bookmark_url, clean_card_title
        from update_and_reorganize_bookmarks import assign_hierarchy

        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        already_existing = []
        new_candidates = []
        seen_batch_keys = set()

        for raw_item in items or []:
            if isinstance(raw_item, str):
                raw_item = {"url": raw_item.strip()}
            elif not isinstance(raw_item, dict):
                continue

            raw_url = str(raw_item.get("url") or "").strip()
            if not raw_url:
                continue
            cleaned_u = clean_bookmark_url(raw_url)
            if not cleaned_u.startswith(("http://", "https://")):
                cleaned_u = "https://" + cleaned_u

            norm_key = normalize_url_for_comparison(cleaned_u)
            if not norm_key or norm_key in seen_batch_keys:
                continue
            seen_batch_keys.add(norm_key)

            raw_title = str(raw_item.get("title") or "").strip()
            cleaned_title = clean_card_title(raw_title or cleaned_u, cleaned_u)
            legacy_path = raw_item.get("legacy_path") if isinstance(raw_item.get("legacy_path"), list) else []
            item_notes = str(
                raw_item.get("notes")
                if raw_item.get("notes") is not None
                else (default_notes or "")
            ).strip()

            existing_idx, existing_bm = find_catalog_entry(catalog, [raw_url, cleaned_u])
            if existing_idx is not None:
                already_existing.append({
                    "url": existing_bm.get("url", cleaned_u),
                    "title": existing_bm.get("title", cleaned_title),
                    "hierarchy": existing_bm.get("hierarchy", []),
                    "notes": existing_bm.get("notes", ""),
                })
                if skip_existing:
                    continue

            pillar, subcat = assign_hierarchy({
                "url": cleaned_u,
                "title": cleaned_title,
                "description": str(raw_item.get("description") or ""),
                "notes": item_notes,
                "legacy_path": legacy_path,
            })

            new_candidates.append({
                "url": cleaned_u,
                "title": cleaned_title,
                "legacy_path": legacy_path,
                "predicted_pillar": pillar,
                "predicted_subcategory": subcat,
                "notes": item_notes,
                "add_date": str(raw_item.get("add_date") or "").strip(),
                "icon": str(raw_item.get("icon") or "").strip(),
                "visit_count": int(raw_item.get("visit_count", 1) or 1),
                "browser_data": raw_item.get("browser_data") if isinstance(raw_item.get("browser_data"), dict) else None,
            })

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "total_parsed": len(seen_batch_keys),
                "already_existing_count": len(already_existing),
                "new_candidates_count": len(new_candidates),
                "max_items_limit": max_items,
                "candidates": [
                    {k: v for k, v in c.items() if k not in ("icon", "browser_data")}
                    for c in new_candidates[: max(max_items, 50)]
                ],
                "existing_preview": already_existing[:20],
            }

        batch_to_process = new_candidates[: max(1, int(max_items or 25))]
        backup_file = save_catalog_backup(catalog, self._workspace_dir, "bulk_import") if batch_to_process else None

        ingested_bookmarks = []
        updated_bookmarks = []
        skipped_items = []

        for cand in batch_to_process:
            u = cand["url"]
            b_data = cand.get("browser_data")
            # Seed fallback title/meta from imported file if verified metadata or browser_data is present
            res = self.ingest_and_persist(
                u,
                browser_data=b_data,
                regenerate_html=False,
                notes=cand.get("notes") or None,
            )
            if res.get("success") and res.get("bookmark"):
                bm_out = res["bookmark"]
                # Preserve imported legacy_path / add_date / icon if catalog entry didn't already have them
                if cand.get("legacy_path") or cand.get("icon") or cand.get("add_date"):
                    try:
                        with open(CATALOG_PATH, "r", encoding="utf-8") as cf:
                            cur_cat = json.load(cf)
                        idx, cur_bm = find_catalog_entry(cur_cat, [u, bm_out.get("url", u)])
                        if idx is not None and cur_bm:
                            changed = False
                            if cand.get("legacy_path") and not cur_bm.get("legacy_path"):
                                cur_bm["legacy_path"] = cand["legacy_path"]
                                bm_out["legacy_path"] = cand["legacy_path"]
                                changed = True
                            if cand.get("icon") and not cur_bm.get("icon"):
                                cur_bm["icon"] = cand["icon"]
                                changed = True
                            if cand.get("add_date") and not cur_bm.get("add_date"):
                                cur_bm["add_date"] = cand["add_date"]
                                bm_out["add_date"] = cand["add_date"]
                                changed = True
                            if changed:
                                cur_cat[idx] = cur_bm
                                with open(CATALOG_PATH, "w", encoding="utf-8") as cf:
                                    json.dump(cur_cat, cf, indent=2, ensure_ascii=False)
                    except Exception:
                        pass

                if res.get("is_existing"):
                    updated_bookmarks.append(bm_out)
                else:
                    ingested_bookmarks.append(bm_out)
            else:
                reason = (
                    res.get("auth_message")
                    or res.get("dead_reason")
                    or res.get("browser_message")
                    or res.get("error")
                    or "Requires live /browser inspection"
                )
                skipped_items.append({
                    "url": u,
                    "title": cand.get("title", u),
                    "reason": reason,
                    "is_auth_barrier": bool(res.get("is_auth_barrier")),
                    "is_dead_page": bool(res.get("is_dead_page")),
                    "requires_browser_inspection": bool(res.get("requires_browser_inspection")),
                })

        if (ingested_bookmarks or updated_bookmarks) and regenerate_html:
            for script_name in ("update_and_reorganize_bookmarks.py", "generate_dark_showcase.py"):
                script_path = os.path.join(self._workspace_dir, script_name)
                if os.path.exists(script_path):
                    subprocess.run([sys.executable, script_path], cwd=self._workspace_dir, check=False)

        return {
            "success": True,
            "dry_run": False,
            "total_parsed": len(seen_batch_keys),
            "already_existing_count": len(already_existing),
            "new_candidates_count": len(new_candidates),
            "processed_count": len(batch_to_process),
            "remaining_unprocessed_count": max(0, len(new_candidates) - len(batch_to_process)),
            "ingested_count": len(ingested_bookmarks),
            "updated_count": len(updated_bookmarks),
            "skipped_count": len(skipped_items),
            "backup_path": backup_file,
            "ingested_bookmarks": ingested_bookmarks,
            "updated_bookmarks": updated_bookmarks,
            "skipped_items": skipped_items,
        }


IMPORT_IGNORE_PATTERNS = (
    "javascript:",
    "chrome://",
    "edge://",
    "about:",
    "file://",
    "data:",
    "mailto:",
    "localhost",
    "127.0.0.1",
    "login.microsoftonline.com",
    "accounts.google.com",
    "safelinks.protection.outlook.com",
)


def _is_importable_bookmark_url(url_str: str) -> bool:
    u = (url_str or "").strip().lower()
    if not u or len(u) < 8:
        return False
    if any(pat in u for pat in IMPORT_IGNORE_PATTERNS):
        return False
    return u.startswith(("http://", "https://", "www.")) or ("." in u.split("/")[0])


def parse_bookmarks_import_payload(content_str: str, filename: str = "") -> list:
    """
    Parse bookmarks from any of the 4 standard import formats:
      1. Netscape Bookmark HTML export (`<!DOCTYPE NETSCAPE-Bookmark-file-1` or `<DT><A HREF=...`)
      2. Chrome / Edge `Bookmarks` JSON file (`{"roots": {"bookmark_bar": ...}}`)
      3. Catalog JSON array or object (`[{"url": ...}]` or `{"bookmarks": [...]}`)
      4. Plain-text / Markdown URL list (one URL per line or `[Title](https://...)`)
    """
    import html

    text = (content_str or "").strip()
    if not text:
        return []

    parsed_items = []

    # 1. Try JSON formats first if it starts with '{' or '['
    if text[0] in ("{", "["):
        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("roots"), dict):
                # Chrome / Edge Bookmarks JSON profile format
                def _walk_chrome_node(node, folder_stack):
                    if not isinstance(node, dict):
                        return
                    ntype = node.get("type", "")
                    name = str(node.get("name") or "").strip()
                    if ntype == "url" and node.get("url"):
                        u = str(node["url"]).strip()
                        if _is_importable_bookmark_url(u):
                            parsed_items.append({
                                "url": u,
                                "title": name or u,
                                "legacy_path": [f for f in folder_stack if f and f.lower() not in ("bookmarks bar", "favorites bar", "other bookmarks", "other favorites", "mobile bookmarks")],
                                "add_date": str(node.get("date_added") or ""),
                            })
                    elif isinstance(node.get("children"), list):
                        next_stack = folder_stack + ([name] if name else [])
                        for child in node["children"]:
                            _walk_chrome_node(child, next_stack)

                for root_node in data["roots"].values():
                    if isinstance(root_node, dict):
                        _walk_chrome_node(root_node, [])
                return parsed_items

            # Catalog JSON list or wrapper object
            raw_list = data if isinstance(data, list) else (
                data.get("bookmarks") or data.get("items") or data.get("urls") or [data]
            )
            if isinstance(raw_list, list):
                for entry in raw_list:
                    if isinstance(entry, str) and _is_importable_bookmark_url(entry):
                        parsed_items.append({"url": entry.strip()})
                    elif isinstance(entry, dict) and entry.get("url") and _is_importable_bookmark_url(str(entry["url"])):
                        parsed_items.append({
                            "url": str(entry["url"]).strip(),
                            "title": str(entry.get("title") or entry.get("name") or "").strip(),
                            "description": str(entry.get("description") or "").strip(),
                            "notes": str(entry.get("notes") or entry.get("custom_notes") or "").strip(),
                            "legacy_path": entry.get("legacy_path") if isinstance(entry.get("legacy_path"), list) else [],
                            "add_date": str(entry.get("add_date") or "").strip(),
                            "icon": str(entry.get("icon") or "").strip(),
                            "visit_count": int(entry.get("visit_count", 1) or 1),
                            "browser_data": entry.get("browser_data") if isinstance(entry.get("browser_data"), dict) else None,
                        })
                return parsed_items
        except Exception:
            pass

    # 2. Check for Netscape Bookmark HTML format (<DL>, <DT><A HREF="...">)
    if re.search(r"<A\s+[^>]*HREF=", text, re.IGNORECASE):
        current_path = []
        last_item = None
        for line in text.splitlines():
            stripped = line.strip()
            if "<H3" in stripped.upper():
                m_h3 = re.search(r"<H3[^>]*>(.*?)</H3>", stripped, re.IGNORECASE)
                if m_h3:
                    folder_name = html.unescape(m_h3.group(1)).strip()
                    current_path.append(folder_name)
                last_item = None
            elif "</DL>" in stripped.upper():
                if current_path:
                    current_path.pop()
                last_item = None
            elif "<A " in stripped.upper():
                m_u = re.search(r'HREF="([^"]+)"|HREF=\'([^\']+)\'', stripped, re.IGNORECASE)
                m_t = re.search(r">([^<]*)</A>", stripped, re.IGNORECASE)
                m_d = re.search(r'ADD_DATE=["\']?(\d+)', stripped, re.IGNORECASE)
                m_i = re.search(r'ICON="([^"]+)"|ICON=\'([^\']+)\'', stripped, re.IGNORECASE)
                if m_u:
                    raw_href = (m_u.group(1) or m_u.group(2) or "").strip()
                    u = (
                        raw_href.replace("&amp;", "&")
                        .replace("&quot;", '"')
                        .replace("&#39;", "'")
                        .replace("&lt;", "<")
                        .replace("&gt;", ">")
                    )
                    if _is_importable_bookmark_url(u):
                        t = html.unescape(m_t.group(1)).strip() if m_t else u
                        t = re.sub(r"^\[\d+\s+visits?\]\s*", "", t, flags=re.IGNORECASE).strip()
                        clean_folders = [
                            f for f in current_path
                            if f.lower() not in ("bookmarks bar", "favorites bar", "bookmarks", "favorites", "other bookmarks")
                        ]
                        icon_str = (m_i.group(1) or m_i.group(2) or "").strip() if m_i else ""
                        item = {
                            "url": u,
                            "title": t,
                            "legacy_path": list(clean_folders),
                            "add_date": m_d.group(1) if m_d else str(int(time.time())),
                            "icon": icon_str,
                            "notes": "",
                        }
                        parsed_items.append(item)
                        last_item = item
            elif stripped.upper().startswith("<DD>") and last_item is not None:
                dd_text = re.sub(r"</?DD[^>]*>", "", stripped, flags=re.IGNORECASE).strip()
                dd_text = html.unescape(dd_text)
                if dd_text and not last_item.get("notes"):
                    last_item["notes"] = dd_text[:300]
        if parsed_items:
            return parsed_items

    # 3. Fallback: Plain-text or Markdown URL list
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # Match Markdown link [Title](https://...)
        m_md = re.search(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", s)
        if m_md:
            u = m_md.group(2).strip()
            t = m_md.group(1).strip()
            if _is_importable_bookmark_url(u):
                parsed_items.append({"url": u, "title": t})
            continue
        # Match raw http(s) URL in line
        m_url = re.search(r"(https?://[^\s<>\"\'`]+)", s)
        if m_url:
            u = m_url.group(1).rstrip(".,;)")
            if _is_importable_bookmark_url(u):
                parsed_items.append({"url": u})
        elif _is_importable_bookmark_url(s.split()[0]):
            u = s.split()[0]
            if not u.startswith(("http://", "https://")):
                u = "https://" + u
            parsed_items.append({"url": u})

    return parsed_items

MAX_CATALOG_BACKUPS = 10

def save_catalog_backup(catalog: list, workspace_dir: str, operation: str = "update", max_backups: int = MAX_CATALOG_BACKUPS) -> str:
    """Write a timestamped catalog snapshot to archive/backups/ and prune older snapshots beyond max_backups."""
    backup_dir = os.path.join(workspace_dir, "archive", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"bookmarks_catalog_pre_{operation}_{timestamp}.json")
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    try:
        snaps = sorted(
            [
                os.path.join(backup_dir, fn)
                for fn in os.listdir(backup_dir)
                if fn.startswith("bookmarks_catalog") and (fn.endswith(".json") or ".json.bak" in fn)
            ],
            key=lambda p: os.path.getmtime(p),
        )
        if len(snaps) > max_backups:
            for old_snap in snaps[:-max_backups]:
                try:
                    os.remove(old_snap)
                except OSError:
                    pass
    except Exception:
        pass
    return backup_file

def normalize_url_for_comparison(url_str: str) -> str:
    """Normalize URL for duplicate detection (handles trailing slashes, www, case, and scheme)."""
    if not url_str:
        return ""
    u = url_str.strip()
    if not u.startswith("http://") and not u.startswith("https://"):
        u = "https://" + u
    try:
        p = urlparse(u)
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = p.path.rstrip("/")
        query = p.query
        return f"{netloc}{path}{'?' + query if query else ''}"
    except Exception:
        return u.lower().rstrip("/")

def find_catalog_entry(catalog: list, url_candidates: list) -> tuple:
    """Find existing catalog entry index and dict matching any candidate URL."""
    cand_keys = {normalize_url_for_comparison(u) for u in url_candidates if u}
    cand_keys.discard("")
    for idx, b in enumerate(catalog):
        b_url = b.get("url", "")
        b_key = normalize_url_for_comparison(b_url)
        if b_key and b_key in cand_keys:
            return idx, b
    return None, None

# HTTP Request Handler
class AIAgentHandler(BaseHTTPRequestHandler):
    engine = CatalogEngine(CATALOG_PATH)
    llm = LLMBridge()
    inspector = BookmarkInspector(llm_bridge=llm)

    def _set_cors_headers(self, content_type="application/json"):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)

    def _send_json_resp(self, code, data, req_id=None, t0=None):
        duration = round(time.time() - t0, 3) if t0 else 0.0
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self._set_cors_headers("application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass
        if req_id:
            comm_logger.log_frontend_response(req_id, self.command, self.path, code, "application/json", data, duration)

    def _send_bytes_resp(self, code, content_type, data_bytes, headers_dict=None, req_id=None, t0=None):
        duration = round(time.time() - t0, 3) if t0 else 0.0
        try:
            self.send_response(code)
            self._set_cors_headers(content_type)
            if headers_dict:
                for k, v in headers_dict.items():
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)
        except (BrokenPipeError, ConnectionResetError):
            pass
        if req_id:
            summary_desc = f"[{len(data_bytes)} bytes content]"
            comm_logger.log_frontend_response(req_id, self.command, self.path, code, content_type, summary_desc, duration)

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        t0 = time.time()
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        req_id = comm_logger.next_request_id("FE-GET")
        comm_logger.log_frontend_request(req_id, "GET", self.path, self.headers, qs, body=None)

        if path == "/api/status":
            status_data = {
                "status": "online",
                "server": "Bookmarks AI Project Agent",
                "port": PORT,
                "config_file": CONFIG_PATH,
                "bookmarks_count": len(self.engine.catalog),
                "last_modified": self.engine.last_mtime,
                "llm_backend": self.llm.get_status(),
                "intent_engine": self.engine.llm_intent_extractor.get_status(),
                "logging": {
                    "traffic_logging": comm_logger.is_enabled(),
                    "log_file": comm_logger.log_path,
                    "log_healthcheck": comm_logger._log_healthcheck
                }
            }
            self._send_json_resp(200, status_data, req_id=req_id, t0=t0)

        elif path == "/api/logging":
            self._send_json_resp(200, {
                "enabled": comm_logger.is_enabled(),
                "log_file": comm_logger.log_path,
                "log_healthcheck": comm_logger._log_healthcheck
            }, req_id=req_id, t0=t0)

        elif path in ["/", "/index.html", "/bookmarks_showcase.html"]:
            if os.path.exists(SHOWCASE_PATH):
                headers_map = {
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
                with open(SHOWCASE_PATH, "rb") as f:
                    content_bytes = f.read()
                self._send_bytes_resp(200, "text/html; charset=utf-8", content_bytes, headers_dict=headers_map, req_id=req_id, t0=t0)
            else:
                self._send_json_resp(404, {"error": "Showcase file not found"}, req_id=req_id, t0=t0)

        elif path in ["/stale_bookmarks_review.html", "/archive/audits/stale_bookmarks_review.html"]:
            workspace_dir = os.path.dirname(os.path.abspath(CATALOG_PATH))
            stale_html_path = os.path.join(workspace_dir, "archive", "audits", "stale_bookmarks_review.html")
            if os.path.exists(stale_html_path):
                with open(stale_html_path, "rb") as f:
                    content_bytes = f.read()
                self._send_bytes_resp(200, "text/html; charset=utf-8", content_bytes, req_id=req_id, t0=t0)
            else:
                self._send_json_resp(404, {"error": "Stale bookmarks review HTML not found"}, req_id=req_id, t0=t0)

        elif path == "/api/search":
            query = qs.get("q", [""])[0]
            limit = int(qs.get("limit", [15])[0])
            product = qs.get("product", ["adsp"])[0]
            intent, results = self.engine.search(query, filters={"product": product}, limit=limit)
            client_strip = {"_tokens", "_token_counts", "_id", "_candidate_score", "icon", "content_summary", "content_hash", "legacy_path"}
            slim_results = [{k: v for k, v in r.items() if k not in client_strip} for r in results]
            self._send_json_resp(200, {"intent": intent, "results": slim_results, "product_scope": product}, req_id=req_id, t0=t0)

        else:
            self._send_json_resp(404, {"error": "Not Found", "path": path}, req_id=req_id, t0=t0)

    def do_POST(self):
        t0 = time.time()
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else ""
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = body

        req_id = comm_logger.next_request_id("FE-POST")
        comm_logger.log_frontend_request(req_id, "POST", self.path, self.headers, None, body=payload)

        if parsed.path == "/api/logging":
            new_state = payload.get("enabled", True) if isinstance(payload, dict) else True
            if isinstance(new_state, str):
                new_state = new_state.lower() in ["1", "true", "yes", "on", "enable"]
            active = comm_logger.set_enabled(bool(new_state))
            resp = {
                "success": True,
                "logging_enabled": active,
                "log_file": comm_logger.log_path,
                "message": f"Communication traffic logging is now {'ENABLED' if active else 'DISABLED'}."
            }
            self._send_json_resp(200, resp, req_id=req_id, t0=t0)

        elif parsed.path == "/api/chat":
            p_dict = payload if isinstance(payload, dict) else {}
            query = p_dict.get("query", "").strip()
            filters = p_dict.get("filters", {})
            history = p_dict.get("history", [])
            product = (p_dict.get("product") or filters.get("product") or "adsp").strip().lower()
            filters["product"] = product

            intent, results = self.engine.search(query, filters=filters, limit=12)
            reply = self.llm.generate_synthesis(query, intent, results, history=history, product_scope=product)

            client_strip = {"_tokens", "_token_counts", "_id", "_candidate_score", "icon", "content_summary", "content_hash", "legacy_path"}
            slim_results = [{k: v for k, v in r.items() if k not in client_strip} for r in results]

            response_data = {
                "query": query,
                "reply": reply,
                "intent": intent,
                "results": slim_results,
                "product_scope": product,
                "provider": self.llm.get_status()["provider"]
            }
            self._send_json_resp(200, response_data, req_id=req_id, t0=t0)

        elif parsed.path == "/api/search":
            p_dict = payload if isinstance(payload, dict) else {}
            query = p_dict.get("query", "").strip()
            limit = p_dict.get("limit", 15)
            filters = p_dict.get("filters", {})
            product = (p_dict.get("product") or filters.get("product") or "adsp").strip().lower()
            filters["product"] = product
            intent, results = self.engine.search(query, filters=filters, limit=limit)
            client_strip = {"_tokens", "_token_counts", "_id", "_candidate_score", "icon", "content_summary", "content_hash", "legacy_path"}
            slim_results = [{k: v for k, v in r.items() if k not in client_strip} for r in results]
            self._send_json_resp(200, {"intent": intent, "results": slim_results, "product_scope": product}, req_id=req_id, t0=t0)

        elif parsed.path == "/api/bookmarks/delete":
            p_dict = payload if isinstance(payload, dict) else {}
            raw_urls = p_dict.get("urls", [])
            urls_to_delete = set(u.strip() for u in raw_urls if isinstance(u, str) and u.strip())

            if not urls_to_delete:
                self._send_json_resp(400, {"error": "No valid URLs provided to delete"}, req_id=req_id, t0=t0)
                return

            try:
                # 1. Load catalog
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    catalog = json.load(f)

                initial_count = len(catalog)

                # 2. Backup catalog (with automatic retention rotation)
                workspace_dir = os.path.dirname(os.path.abspath(CATALOG_PATH))
                backup_file = save_catalog_backup(catalog, workspace_dir, "delete")

                # 3. Filter catalog (match exact URL, cleaned URL without #:~:text=, or normalized URL)
                from batch_enrich_all import clean_bookmark_url
                cleaned_to_delete = {clean_bookmark_url(u) for u in urls_to_delete} | urls_to_delete
                norm_to_delete = {normalize_url_for_comparison(u) for u in cleaned_to_delete if u}

                def _matches_delete(bm_item):
                    u = (bm_item.get("url") or "").strip()
                    if not u:
                        return False
                    return (
                        u in cleaned_to_delete
                        or clean_bookmark_url(u) in cleaned_to_delete
                        or normalize_url_for_comparison(u) in norm_to_delete
                    )

                deleted_items = [b for b in catalog if _matches_delete(b)]
                updated_catalog = [b for b in catalog if not _matches_delete(b)]

                # 4. Save catalog & purge deleted URLs from verified_metadata and content_cache
                with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(updated_catalog, f, indent=2, ensure_ascii=False)

                try:
                    ver_path = os.path.join(workspace_dir, "ai_agent_server", "bookmarks_verified_metadata.json")
                    if os.path.exists(ver_path):
                        with open(ver_path, "r", encoding="utf-8") as f:
                            ver_data = json.load(f)
                        if isinstance(ver_data, dict):
                            keys_to_pop = [
                                k for k in list(ver_data.keys())
                                if k in cleaned_to_delete or normalize_url_for_comparison(k) in norm_to_delete
                            ]
                            if keys_to_pop:
                                for k in keys_to_pop:
                                    ver_data.pop(k, None)
                                with open(ver_path, "w", encoding="utf-8") as f:
                                    json.dump(ver_data, f, indent=2, ensure_ascii=False)
                    cache_path = os.path.join(workspace_dir, "ai_agent_server", "bookmarks_content_cache.json")
                    if os.path.exists(cache_path):
                        with open(cache_path, "r", encoding="utf-8") as f:
                            cache_data = json.load(f)
                        if isinstance(cache_data, dict):
                            keys_to_pop = [
                                k for k in list(cache_data.keys())
                                if k in cleaned_to_delete or normalize_url_for_comparison(k) in norm_to_delete
                            ]
                            if keys_to_pop:
                                for k in keys_to_pop:
                                    cache_data.pop(k, None)
                                with open(cache_path, "w", encoding="utf-8") as f:
                                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
                    self.inspector._load_reference_stores()
                except Exception:
                    pass

                # 5. Run downstream updates: favorites HTML & Chrome profile, then showcase HTML
                sync_error = None
                try:
                    update_script = os.path.join(workspace_dir, "update_and_reorganize_bookmarks.py")
                    showcase_script = os.path.join(workspace_dir, "generate_dark_showcase.py")
                    if os.path.exists(update_script):
                        subprocess.run([sys.executable, update_script], cwd=workspace_dir, check=False)
                    if os.path.exists(showcase_script):
                        subprocess.run([sys.executable, showcase_script], cwd=workspace_dir, check=False)
                except Exception as ex:
                    sync_error = str(ex)

                # 6. Reload engine in memory
                self.engine.reload()

                response_data = {
                    "success": True,
                    "deleted_count": len(deleted_items),
                    "remaining_count": len(updated_catalog),
                    "backup_path": backup_file,
                    "deleted_urls": [b.get("url") for b in deleted_items],
                    "sync_error": sync_error
                }

                self._send_json_resp(200, response_data, req_id=req_id, t0=t0)

            except Exception as e:
                self._send_json_resp(500, {"error": str(e)}, req_id=req_id, t0=t0)

        elif parsed.path == "/api/bookmarks/add":
            p_dict = payload if isinstance(payload, dict) else {}
            raw_url = p_dict.get("url", "").strip()
            browser_data = p_dict.get("browser_data") if isinstance(p_dict.get("browser_data"), dict) else None
            has_explicit_notes = ("notes" in p_dict) or ("custom_notes" in p_dict)
            if not has_explicit_notes and isinstance(browser_data, dict):
                has_explicit_notes = ("notes" in browser_data) or ("custom_notes" in browser_data)
            raw_notes_val = (
                p_dict.get("notes")
                if "notes" in p_dict
                else (
                    p_dict.get("custom_notes")
                    if "custom_notes" in p_dict
                    else (
                        browser_data.get("notes")
                        if isinstance(browser_data, dict) and "notes" in browser_data
                        else (browser_data.get("custom_notes") if isinstance(browser_data, dict) else None)
                    )
                )
            )
            custom_notes = str(raw_notes_val).strip() if raw_notes_val is not None else ""
            if not raw_url:
                self._send_json_resp(400, {"error": "No valid URL provided to add"}, req_id=req_id, t0=t0)
                return

            try:
                # 1. Load catalog first so we can check for existing bookmark candidates
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    catalog = json.load(f)

                # Preliminary duplicate check by submitted URL
                pre_idx, pre_bm = find_catalog_entry(catalog, [raw_url])

                # 2. Inspect website content strictly from /browser subagent data or /browser-verified cache
                enriched = self.inspector.inspect_and_enrich(
                    raw_url,
                    browser_data=browser_data,
                    notes=custom_notes if has_explicit_notes else None
                )
                workspace_dir = os.path.dirname(os.path.abspath(CATALOG_PATH))
                if enriched.get("is_auth_barrier"):
                    auth_msg = enriched.get(
                        "auth_message",
                        "Login / SSO wall encountered in /browser. Please log in via the browser first so /browser can inspect the real page content."
                    )
                    self._send_json_resp(428, {
                        "status": "error",
                        "error": "auth_login_required",
                        "url": raw_url,
                        "message": auth_msg
                    }, req_id=req_id, t0=t0)
                    return

                if enriched.get("requires_browser_inspection"):
                    browser_msg = enriched.get(
                        "browser_message",
                        "Website has not been inspected with /browser yet. Please inspect it via the /browser subagent first."
                    )
                    self._send_json_resp(428, {
                        "status": "error",
                        "error": "browser_inspection_required",
                        "url": raw_url,
                        "message": browser_msg
                    }, req_id=req_id, t0=t0)
                    return

                if enriched.get("is_dead_page"):
                    dead_reason = enriched.get("dead_reason", "Target webpage does not exist or is unreachable")
                    stale_json = os.path.join(workspace_dir, "archive", "audits", "stale_bookmarks_results.json")
                    try:
                        stale_list = json.load(open(stale_json, "r", encoding="utf-8")) if os.path.exists(stale_json) else []
                        if not any(s.get("url") == raw_url for s in stale_list):
                            stale_list.append({
                                "url": raw_url,
                                "title": urlparse(raw_url).path.strip("/").split("/")[-1] or raw_url,
                                "category": "STALE_404",
                                "reason": dead_reason,
                                "hierarchy": ["Archived Dead Link"]
                            })
                            with open(stale_json, "w", encoding="utf-8") as sf:
                                json.dump(stale_list, sf, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                    self._send_json_resp(422, {
                        "status": "error",
                        "error": "dead_page",
                        "url": raw_url,
                        "reason": dead_reason,
                        "message": f"Target website does not exist or is no longer available ({dead_reason}). Archived for manual removal."
                    }, req_id=req_id, t0=t0)
                    return

                final_url = enriched.get("url", raw_url)

                # 3. Check for existing bookmark with both raw_url and final resolved url
                existing_idx, existing_bm = find_catalog_entry(catalog, [raw_url, final_url])
                if existing_idx is None and pre_idx is not None:
                    existing_idx = pre_idx
                    existing_bm = pre_bm

                backup_file = None
                sync_error = None
                is_existing = (existing_idx is not None)

                if is_existing:
                    # Bookmark already exists! Check if content has changed, if it lacks a summary, or if custom notes changed.
                    old_summary = (existing_bm.get("content_summary") or "").strip()
                    new_summary = (enriched.get("content_summary") or "").strip()
                    missing_summary = (not old_summary and bool(new_summary))

                    old_title = (existing_bm.get("title") or "").strip()
                    new_title = (enriched.get("title") or "").strip()
                    title_improved = (
                        bool(new_title) and new_title != old_title and
                        (not old_title or old_title == existing_bm.get("url") or old_title == "Untitled")
                    )

                    old_desc = (existing_bm.get("description") or "").strip()
                    new_desc = (enriched.get("description") or "").strip()
                    desc_changed = bool(new_desc) and (not old_desc or (new_desc != old_desc and len(new_desc) > len(old_desc)))

                    summary_changed = bool(new_summary) and (new_summary != old_summary)
                    vpn_changed = enriched.get("requires_vpn", False) != existing_bm.get("requires_vpn", False)
                    official_changed = enriched.get("is_official_f5", False) != existing_bm.get("is_official_f5", False)

                    old_notes = (existing_bm.get("notes") or "").strip()
                    # If notes was explicitly provided in payload (and non-empty or clearing via allow_clear_notes), check if changed
                    allow_clear_notes = bool(p_dict.get("allow_clear_notes", False))
                    notes_changed = has_explicit_notes and (bool(custom_notes) or allow_clear_notes) and (custom_notes != old_notes)

                    # Check for new tags
                    existing_tags = existing_bm.setdefault("tags", {})
                    tags_enriched = False
                    for tkey in ["products", "topics", "source_types"]:
                        c_list = existing_tags.setdefault(tkey, [])
                        for it in enriched.get(tkey, []):
                            if it not in c_list:
                                c_list.append(it)
                                tags_enriched = True

                    old_hash = existing_bm.get("content_hash")
                    new_hash = enriched.get("content_hash")

                    # Content change on the website
                    content_changed = bool(old_hash and new_hash and old_hash != new_hash)

                    if missing_summary or notes_changed:
                        needs_update = True
                    elif old_hash and new_hash and old_hash == new_hash:
                        # Website content is identical and bookmark already has a summary
                        needs_update = False
                    elif not old_hash and len(old_summary) > 60:
                        # Existing bookmark has a summary; save hash to catalog to pin it
                        existing_bm["content_hash"] = new_hash
                        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                            json.dump(catalog, f, indent=2, ensure_ascii=False)
                        needs_update = False
                    else:
                        needs_update = (content_changed or desc_changed or title_improved or vpn_changed or official_changed or tags_enriched)

                    if needs_update:
                        # Create backup before updating existing entry (with automatic retention rotation)
                        backup_file = save_catalog_backup(catalog, workspace_dir, "update")

                        # Tracking update reasons
                        reasons = []
                        if notes_changed:
                            reasons.append("updated custom notes" if custom_notes else "cleared custom notes")
                        if missing_summary:
                            reasons.append("attached missing technical summary")
                        elif content_changed:
                            reasons.append("detected page content update & refreshed summary")
                        elif summary_changed and not (old_hash and new_hash and old_hash == new_hash):
                            reasons.append("updated technical summary")
                        if desc_changed and not (old_hash and new_hash and old_hash == new_hash):
                            reasons.append("updated description")
                        if title_improved:
                            reasons.append("refined title")
                        if vpn_changed:
                            reasons.append(f"vpn requirement updated ({enriched.get('requires_vpn')})")
                        if official_changed:
                            reasons.append(f"official F5 status verified ({enriched.get('is_official_f5')})")
                        if tags_enriched:
                            reasons.append("enriched tags")
                        reason_msg = "; ".join(reasons) if reasons else "updated content"

                        # Update existing entry in-place (DO NOT ADD TWICE!)
                        if notes_changed:
                            existing_bm["notes"] = custom_notes
                        elif "notes" not in existing_bm:
                            existing_bm["notes"] = old_notes
                        if new_summary and (missing_summary or content_changed):
                            existing_bm["content_summary"] = new_summary
                        if enriched.get("description") and (not existing_bm.get("description") or (desc_changed and content_changed)):
                            existing_bm["description"] = enriched["description"]
                        if title_improved:
                            existing_bm["title"] = enriched["title"]
                        if "is_official_f5" in enriched:
                            existing_bm["is_official_f5"] = enriched["is_official_f5"]
                        if "requires_vpn" in enriched:
                            existing_bm["requires_vpn"] = enriched["requires_vpn"]
                        if new_hash:
                            existing_bm["content_hash"] = new_hash
                        if not existing_bm.get("hierarchy"):
                            existing_bm["hierarchy"] = [enriched["pillar"], enriched["subcategory"]]

                        # Save catalog
                        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                            json.dump(catalog, f, indent=2, ensure_ascii=False)

                        try:
                            self.inspector.verified_metadata[final_url] = dict(existing_bm)
                            vmeta_path = os.path.join(workspace_dir, "ai_agent_server", "bookmarks_verified_metadata.json")
                            with open(vmeta_path, "w", encoding="utf-8") as vf:
                                json.dump(self.inspector.verified_metadata, vf, indent=2, ensure_ascii=False)
                        except Exception:
                            pass

                        # Trigger downstream scripts to re-render HTML files with the new summary/notes
                        try:
                            update_script = os.path.join(workspace_dir, "update_and_reorganize_bookmarks.py")
                            showcase_script = os.path.join(workspace_dir, "generate_dark_showcase.py")
                            if os.path.exists(update_script):
                                subprocess.run([sys.executable, update_script], cwd=workspace_dir, check=False)
                            if os.path.exists(showcase_script):
                                subprocess.run([sys.executable, showcase_script], cwd=workspace_dir, check=False)
                        except Exception as ex:
                            sync_error = str(ex)

                        # Reload BM25 index in memory
                        self.engine.reload()

                        target_bm = existing_bm
                        updated = True
                    else:
                        # Existing bookmark is already up to date with summary
                        reason_msg = "Bookmark already exists in catalog and content summary is up-to-date"
                        target_bm = existing_bm
                        updated = False

                else:
                    # Brand new bookmark - not in catalog
                    backup_file = save_catalog_backup(catalog, workspace_dir, "add")

                    resolved_new_notes = custom_notes if has_explicit_notes else enriched.get("notes", "")
                    target_bm = {
                        "url": final_url,
                        "title": enriched["title"],
                        "description": enriched["description"],
                        "content_summary": enriched.get("content_summary", ""),
                        "content_hash": enriched.get("content_hash", ""),
                        "notes": resolved_new_notes,
                        "hierarchy": [enriched["pillar"], enriched["subcategory"]],
                        "legacy_path": enriched.get("legacy_path", []),
                        "tags": {
                            "products": enriched.get("products", []),
                            "topics": enriched.get("topics", []),
                            "source_types": enriched.get("source_types", [])
                        },
                        "requires_vpn": enriched.get("requires_vpn", False),
                        "is_official_f5": enriched.get("is_official_f5", False),
                        "visit_count": enriched.get("visit_count", 1),
                        "add_date": enriched.get("add_date") or str(int(time.time())),
                        "icon": enriched.get("icon", "")
                    }
                    catalog.append(target_bm)

                    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                        json.dump(catalog, f, indent=2, ensure_ascii=False)

                    try:
                        self.inspector.verified_metadata[final_url] = dict(target_bm)
                        vmeta_path = os.path.join(workspace_dir, "ai_agent_server", "bookmarks_verified_metadata.json")
                        with open(vmeta_path, "w", encoding="utf-8") as vf:
                            json.dump(self.inspector.verified_metadata, vf, indent=2, ensure_ascii=False)
                    except Exception:
                        pass

                    try:
                        update_script = os.path.join(workspace_dir, "update_and_reorganize_bookmarks.py")
                        showcase_script = os.path.join(workspace_dir, "generate_dark_showcase.py")
                        if os.path.exists(update_script):
                            subprocess.run([sys.executable, update_script], cwd=workspace_dir, check=False)
                        if os.path.exists(showcase_script):
                            subprocess.run([sys.executable, showcase_script], cwd=workspace_dir, check=False)
                    except Exception as ex:
                        sync_error = str(ex)

                    self.engine.reload()
                    reason_msg = "Successfully ingested new bookmark" + (" with custom notes" if resolved_new_notes else "")
                    updated = True

                pillar_val = target_bm.get("hierarchy", [enriched["pillar"], enriched["subcategory"]])[0]
                subcat_val = target_bm.get("hierarchy", [enriched["pillar"], enriched["subcategory"]])[1]

                response_data = {
                    "success": True,
                    "is_existing": is_existing,
                    "updated": updated,
                    "reason": reason_msg,
                    "bookmark": {k: v for k, v in target_bm.items() if k not in {"icon", "_tokens", "_id"}},
                    "pillar": pillar_val,
                    "subcategory": subcat_val,
                    "notes": target_bm.get("notes", ""),
                    "is_official_f5": target_bm.get("is_official_f5", False),
                    "requires_vpn": target_bm.get("requires_vpn", False),
                    "backup_path": backup_file,
                    "sync_error": sync_error
                }
                self._send_json_resp(200, response_data, req_id=req_id, t0=t0)

            except Exception as e:
                self._send_json_resp(500, {"error": str(e)}, req_id=req_id, t0=t0)

        elif parsed.path == "/api/bookmarks/notes":
            p_dict = payload if isinstance(payload, dict) else {}
            raw_url = p_dict.get("url", "").strip()
            raw_notes_val = p_dict.get("notes", p_dict.get("custom_notes", ""))
            custom_notes = str(raw_notes_val).strip() if raw_notes_val is not None else ""
            if not raw_url:
                self._send_json_resp(400, {"error": "No valid URL provided"}, req_id=req_id, t0=t0)
                return

            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    catalog = json.load(f)

                existing_idx, existing_bm = find_catalog_entry(catalog, [raw_url])
                if existing_idx is None:
                    self._send_json_resp(404, {"error": "Bookmark not found in catalog", "url": raw_url}, req_id=req_id, t0=t0)
                    return

                old_notes = (existing_bm.get("notes") or "").strip()
                existing_bm["notes"] = custom_notes
                workspace_dir = os.path.dirname(os.path.abspath(CATALOG_PATH))

                with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(catalog, f, indent=2, ensure_ascii=False)

                final_url = existing_bm.get("url", raw_url)
                try:
                    if final_url in self.inspector.verified_metadata:
                        self.inspector.verified_metadata[final_url]["notes"] = custom_notes
                    else:
                        self.inspector.verified_metadata[final_url] = dict(existing_bm)
                    vmeta_path = os.path.join(workspace_dir, "ai_agent_server", "bookmarks_verified_metadata.json")
                    with open(vmeta_path, "w", encoding="utf-8") as vf:
                        json.dump(self.inspector.verified_metadata, vf, indent=2, ensure_ascii=False)
                except Exception:
                    pass

                sync_error = None
                try:
                    update_script = os.path.join(workspace_dir, "update_and_reorganize_bookmarks.py")
                    showcase_script = os.path.join(workspace_dir, "generate_dark_showcase.py")
                    if os.path.exists(update_script):
                        subprocess.run([sys.executable, update_script], cwd=workspace_dir, check=False)
                    if os.path.exists(showcase_script):
                        subprocess.run([sys.executable, showcase_script], cwd=workspace_dir, check=False)
                except Exception as ex:
                    sync_error = str(ex)

                self.engine.reload()
                self._send_json_resp(200, {
                    "success": True,
                    "updated": custom_notes != old_notes,
                    "url": final_url,
                    "notes": custom_notes,
                    "bookmark": {k: v for k, v in existing_bm.items() if k != "icon"},
                    "sync_error": sync_error
                }, req_id=req_id, t0=t0)
            except Exception as e:
                self._send_json_resp(500, {"error": str(e)}, req_id=req_id, t0=t0)

        elif parsed.path == "/api/bookmarks/import":
            p_dict = payload if isinstance(payload, dict) else {}
            raw_content = str(p_dict.get("content") or "").strip()
            filename = str(p_dict.get("filename") or "").strip()
            raw_urls = p_dict.get("urls") if isinstance(p_dict.get("urls"), list) else []
            raw_items = p_dict.get("items") if isinstance(p_dict.get("items"), list) else []
            dry_run = bool(p_dict.get("dry_run", False))
            skip_existing = bool(p_dict.get("skip_existing", True))
            max_items = int(p_dict.get("max_items", 20) or 20)
            default_notes = str(p_dict.get("notes") or p_dict.get("custom_notes") or "").strip() or None

            items_to_import = []
            if raw_items:
                items_to_import.extend(raw_items)
            if raw_urls:
                for u in raw_urls:
                    if isinstance(u, str) and u.strip():
                        items_to_import.append({"url": u.strip()})
                    elif isinstance(u, dict) and u.get("url"):
                        items_to_import.append(u)
            if raw_content:
                items_to_import.extend(parse_bookmarks_import_payload(raw_content, filename=filename))

            if not items_to_import:
                self._send_json_resp(400, {
                    "success": False,
                    "error": "No valid bookmark URLs or importable content found in payload."
                }, req_id=req_id, t0=t0)
                return

            try:
                result = self.inspector.import_bookmarks_batch(
                    items_to_import,
                    dry_run=dry_run,
                    skip_existing=skip_existing,
                    max_items=max_items,
                    regenerate_html=not dry_run,
                    default_notes=default_notes,
                )
                if not dry_run and (result.get("ingested_count", 0) > 0 or result.get("updated_count", 0) > 0):
                    self.engine.reload()
                self._send_json_resp(200, result, req_id=req_id, t0=t0)
            except Exception as e:
                self._send_json_resp(500, {"success": False, "error": str(e)}, req_id=req_id, t0=t0)

        else:
            self._send_json_resp(404, {"error": "Not Found", "path": parsed.path}, req_id=req_id, t0=t0)

    def log_message(self, format, *args):
        # Clean custom logger
        sys.stderr.write(f"[{time.strftime('%X')}] HTTP {args[0]} {args[1]}\n")

class AIAgentServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def main():
    if any(flag in sys.argv for flag in ("--ingest-url", "--import-file", "--update-notes", "--help", "-h")):
        import argparse
        parser = argparse.ArgumentParser(description="F5 Bookmarks AI Agent Server & Bookmark Ingestion / Import CLI")
        parser.add_argument("--ingest-url", default=None, help="Single URL to inspect, enrich, and persist")
        parser.add_argument("--import-file", default=None, metavar="PATH", help="Import bookmarks from a Netscape HTML export, Chrome/Edge Bookmarks JSON, catalog JSON, or plain-text URL list")
        parser.add_argument("--dry-run", action="store_true", help="Preview parsed bookmarks, duplicate counts, and predicted 9-pillar placement without modifying files")
        parser.add_argument("--max-import", type=int, default=25, help="Maximum number of new bookmarks to inspect and ingest in a single batch (default: 25)")
        parser.add_argument("--include-existing", action="store_true", help="Re-inspect and update bookmarks that already exist in bookmarks_catalog.json")
        parser.add_argument("--update-notes", default=None, metavar="URL", help="Update custom notes on an existing bookmark URL without re-fetching page content")
        parser.add_argument("--browser-json", default=None, help="JSON string or path to JSON file from /browser inspection")
        parser.add_argument("--notes", "--custom-notes", dest="notes", default=None, help="Custom personal notes to attach to the bookmark(s)")
        parser.add_argument("--no-html", action="store_true", help="Skip regenerating HTML files")
        args, _ = parser.parse_known_args()
        if args.import_file:
            import_path = os.path.expanduser(args.import_file)
            if not os.path.exists(import_path):
                print(json.dumps({"success": False, "error": f"Import file not found: {import_path}"}, indent=2))
                sys.exit(1)
            with open(import_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_content = f.read()
            parsed_items = parse_bookmarks_import_payload(raw_content, filename=os.path.basename(import_path))
            res = AIAgentHandler.inspector.import_bookmarks_batch(
                parsed_items,
                dry_run=args.dry_run,
                skip_existing=not args.include_existing,
                max_items=args.max_import,
                regenerate_html=not (args.no_html or args.dry_run),
                default_notes=args.notes,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return
        if args.update_notes:
            workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            norm_target = BookmarkInspector.normalize_url_key(args.update_notes)
            matched = None
            for bm in catalog:
                if bm.get("url") == args.update_notes or BookmarkInspector.normalize_url_key(bm.get("url", "")) == norm_target:
                    matched = bm
                    break
            if not matched:
                print(json.dumps({"success": False, "error": f"Bookmark URL not found: {args.update_notes}"}, indent=2))
                sys.exit(1)
            custom_notes = str(args.notes or "").strip()
            matched["notes"] = custom_notes
            with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)
            verified_meta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bookmarks_verified_metadata.json")
            if os.path.exists(verified_meta_path):
                with open(verified_meta_path, "r", encoding="utf-8") as vf:
                    v_meta = json.load(vf)
                canonical_url = matched.get("url", args.update_notes)
                if canonical_url in v_meta:
                    v_meta[canonical_url]["notes"] = custom_notes
                    with open(verified_meta_path, "w", encoding="utf-8") as vf:
                        json.dump(v_meta, vf, indent=2, ensure_ascii=False)
            if not args.no_html:
                for script_name in ("update_and_reorganize_bookmarks.py", "generate_dark_showcase.py"):
                    s_path = os.path.join(workspace_dir, script_name)
                    if os.path.exists(s_path):
                        subprocess.run([sys.executable, s_path], cwd=workspace_dir, check=False)
            print(json.dumps({"success": True, "url": matched.get("url"), "notes": custom_notes}, indent=2, ensure_ascii=False))
            return
        if args.ingest_url:
            b_data = None
            if args.browser_json:
                if os.path.exists(args.browser_json):
                    with open(args.browser_json, "r", encoding="utf-8") as bf:
                        b_data = json.load(bf)
                else:
                    b_data = json.loads(args.browser_json)
            res = AIAgentHandler.inspector.ingest_and_persist(
                args.ingest_url, browser_data=b_data, regenerate_html=not args.no_html, notes=args.notes
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return
        parser.print_help()
        return

    server = AIAgentServer((HOST, PORT), AIAgentHandler)
    host_display = "localhost" if HOST in ["0.0.0.0", "127.0.0.1"] else HOST
    print("=" * 60)
    print(f"🚀 F5 Bookmarks AI Search Agent Server running on http://{host_display}:{PORT}")
    print(f"⚙️  Configuration File: {CONFIG_PATH}")
    print(f"📂 Connected Catalog: {CATALOG_PATH}")
    print(f"🧠 Active LLM Provider: {AIAgentHandler.llm.get_status()['details']}")
    logging_status = "ENABLED" if comm_logger.is_enabled() else "DISABLED (Toggle with ./run_ai_server.sh --enable-logging)"
    print(f"📜 Traffic Logging: {logging_status}")
    if comm_logger.is_enabled():
        print(f"📄 Traffic Log File: {comm_logger.log_path}")
    print(f"🌐 Serving Showcase at: http://{host_display}:{PORT}/bookmarks_showcase.html")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()

if __name__ == "__main__":
    main()
