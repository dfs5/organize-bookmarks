#!/usr/bin/env python3
"""
sync_edge_history_bookmarks.py
Safe Browser History Visit-Count Synchronizer & Candidate Discovery Tool.

Reads SQLite History databases from Microsoft Edge (and optionally Google Chrome)
using non-locking temporary file copies, and:
  1. Updates `visit_count` on existing curated bookmarks in `bookmarks_catalog.json`
     (matching both canonical `url` and `previous_url`).
  2. Never blindly injects unverified/uncurated stub bookmarks into the catalog.
  3. Optionally reports top frequently visited unbookmarked URLs as candidates for
     canonical `/browser` inspection (`--show-candidates`).
  4. Re-generates `favorites_product_frequency_organized.html` (via
     `update_and_reorganize_bookmarks.py`) and `bookmarks_showcase.html` (via
     `generate_dark_showcase.py`) whenever visit counts change or `--rebuild` is passed.
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(WORKSPACE_DIR, "bookmarks_catalog.json")
REORGANIZE_SCRIPT = os.path.join(WORKSPACE_DIR, "update_and_reorganize_bookmarks.py")
SHOWCASE_SCRIPT = os.path.join(WORKSPACE_DIR, "generate_dark_showcase.py")

BROWSER_DIRS = {
    "Edge": os.path.expanduser("~/Library/Application Support/Microsoft Edge"),
    "Chrome": os.path.expanduser("~/Library/Application Support/Google/Chrome"),
}

MIN_CANDIDATE_VISITS = 5

TRACKING_QUERY_PARAMS = {
    "lfrm",
    "referrer",
    "sr",
    "share",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}

NOISE_PATTERNS = [
    r"login\.microsoftonline\.com",
    r"accounts\.google\.com",
    r"auth\.",
    r"oauth",
    r"sso\.",
    r"okta",
    r"/oauth_done\.html",
    r"bing\.com/search",
    r"google\.com/search",
    r"127\.0\.0\.1",
    r"localhost",
    r"file://",
    r"chrome://",
    r"edge://",
    r"about:blank",
    r"slack\.com",
    r"mail\.google\.com",
    r"teams\.microsoft\.com",
    r"outlook\.cloud\.microsoft",
    r"outlook\.office\.com",
    r"zoom\.us",
    r"access\.mcas\.ms",
    r"portal\.azure\.com/auth",
    r"ihealth\.f5\.com/qkview",
    r"safelinks\.protection\.outlook\.com",
    r"evergreen-assets/safelinks",
]

IGNORE_TITLES = {
    "working...",
    "redirecting...",
    "sign in to your account",
    "loading...",
    "you can close this page now.",
    "an error has occurred",
    "login",
    "logout",
    "sign in",
    "microsoft authentication",
    "error",
}


def clean_url(u: str) -> str:
    """
    Normalize a URL for comparison:
    - Unwraps Google redirect wrapper (`url?q=`)
    - Strips scheme (`http://`/`https://`), `www.`, fragments (`#...`), and trailing slashes
    - Strips known analytics/tracking query parameters while preserving meaningful query keys
    """
    if not u:
        return ""
    u = u.strip()
    if "url?q=" in u:
        qs = parse_qs(urlparse(u).query)
        if "q" in qs and qs["q"]:
            u = unquote(qs["q"][0])
    try:
        parsed = urlparse(u)
        if parsed.query:
            q_pairs = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {
                k: v
                for k, v in sorted(q_pairs.items())
                if k.lower() not in TRACKING_QUERY_PARAMS
            }
            new_query = urlencode(filtered, doseq=True)
        else:
            new_query = ""
        # Preserve SPA hash-routing fragments (e.g., Tableau `#/site/f5/views/...`)
        frag = parsed.fragment if parsed.fragment.startswith(("/", "!")) else ""
        rebuilt = urlunparse(
            (
                "",
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                "",
                new_query,
                frag.rstrip("/"),
            )
        ).lstrip("/")
    except Exception:
        rebuilt = u.rstrip("#").rstrip("/")
    rebuilt = re.sub(r"^(?:https?://)?(?:www\.)?", "", rebuilt, flags=re.IGNORECASE)
    return rebuilt.lower().rstrip("/")


def is_noise_entry(url: str, title: str) -> bool:
    if not url or not title:
        return True
    if title.strip().lower() in IGNORE_TITLES:
        return True
    return any(re.search(pat, url, re.IGNORECASE) for pat in NOISE_PATTERNS)


def read_browser_history(include_chrome: bool = True) -> dict:
    """
    Safely copies browser SQLite History files to temporary files and aggregates
    the maximum visit_count seen for each normalized URL across profiles.
    """
    history_map = {}
    sources = ["Edge", "Chrome"] if include_chrome else ["Edge"]

    for browser_name in sources:
        base_dir = BROWSER_DIRS.get(browser_name, "")
        if not os.path.exists(base_dir):
            continue

        for entry in sorted(os.listdir(base_dir)):
            if entry != "Default" and not entry.startswith("Profile "):
                continue
            profile_path = os.path.join(base_dir, entry)
            hist_file = os.path.join(profile_path, "History")
            if not (os.path.isdir(profile_path) and os.path.exists(hist_file)):
                continue

            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                shutil.copy2(hist_file, tmp_path)
                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT url, title, visit_count FROM urls WHERE visit_count >= 1 ORDER BY visit_count DESC"
                )
                for url, title, count in cursor.fetchall():
                    url = (url or "").strip()
                    title = (title or "").strip()
                    count = int(count or 0)
                    if not url or count <= 0:
                        continue
                    cu = clean_url(url)
                    if not cu:
                        continue
                    prev = history_map.get(cu)
                    if prev is None or count > prev["count"]:
                        history_map[cu] = {
                            "raw_url": url,
                            "title": title or (prev["title"] if prev else ""),
                            "count": count,
                            "browser": f"{browser_name}/{entry}",
                        }
                conn.close()
            except Exception as e:
                print(f"Warning reading {browser_name} ({entry}) history: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    return history_map


def main():
    parser = argparse.ArgumentParser(
        description="Safely sync browser SQLite visit_count to bookmarks_catalog.json without injecting uncurated bookmarks."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview visit_count updates without modifying files.",
    )
    parser.add_argument(
        "--edge-only",
        action="store_true",
        help="Read only Microsoft Edge history (skip Google Chrome profiles).",
    )
    parser.add_argument(
        "--show-candidates",
        action="store_true",
        help="List top unbookmarked URLs (>= 5 visits) as candidates for curated ingestion.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force regeneration of HTML outputs even if no visit counts changed.",
    )
    args = parser.parse_args()

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting safe browser history visit-count sync...")
    if not os.path.exists(CATALOG_PATH):
        print(f"Catalog file {CATALOG_PATH} does not exist.")
        sys.exit(1)

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    history_map = read_browser_history(include_chrome=not args.edge_only)
    print(f"Scanned {len(history_map):,} distinct normalized URLs from browser SQLite history.")

    matched_keys = set()
    updated_bookmarks = []

    for b in catalog:
        keys = [clean_url(b.get("url", "")), clean_url(b.get("previous_url", ""))]
        keys = [k for k in keys if k]
        best_count = int(b.get("visit_count", 0) or 0)
        old_count = best_count

        for k in keys:
            if k in history_map:
                matched_keys.add(k)
                if history_map[k]["count"] > best_count:
                    best_count = history_map[k]["count"]

        if best_count > old_count:
            b["visit_count"] = best_count
            updated_bookmarks.append((b["title"], b["url"], old_count, best_count))

    updated_bookmarks.sort(key=lambda x: -(x[3] - x[2]))
    print(f"Matched & bumped visit_count on {len(updated_bookmarks)} existing curated bookmark(s).")
    for title, u, old_c, new_c in updated_bookmarks[:15]:
        print(f"  ↑ [{old_c} -> {new_c} visits] {title[:65]} ({u[:60]})")

    if args.show_candidates:
        unbookmarked_candidates = [
            info
            for cu, info in history_map.items()
            if cu not in matched_keys
            and info["count"] >= MIN_CANDIDATE_VISITS
            and not is_noise_entry(info["raw_url"], info["title"])
        ]
        unbookmarked_candidates.sort(key=lambda x: -x["count"])
        print(f"\nTop unbookmarked candidates (>= {MIN_CANDIDATE_VISITS} visits, non-noise):")
        for c in unbookmarked_candidates[:15]:
            print(f"  ? [{c['count']} visits | {c['browser']}] {c['title'][:60]} -> {c['raw_url'][:75]}")

    if args.dry_run:
        print("Dry-run mode complete; no files were modified.")
        return

    if updated_bookmarks or args.rebuild:
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        print("Saved updated visit counts to bookmarks_catalog.json.")

        if os.path.exists(REORGANIZE_SCRIPT):
            subprocess.run([sys.executable, REORGANIZE_SCRIPT], check=True)
        if os.path.exists(SHOWCASE_SCRIPT):
            subprocess.run([sys.executable, SHOWCASE_SCRIPT], check=True)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sync and HTML rebuild completed!")
    else:
        print("No visit_count increases detected; skipping catalog write & HTML rebuild.")


if __name__ == "__main__":
    main()
