#!/usr/bin/env python3
"""
lookup.py - Search across the enriched bookmarks catalog.
Usage:
    python3 lookup.py --topic <query> [--product <name>] [--type <type>] [--min-visits <n>] [--limit <n>]
"""

import sys
import json
import argparse
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))
CATALOG_PATH = os.path.join(REPO_ROOT, "bookmarks_catalog.json")
if not os.path.exists(CATALOG_PATH):
    CATALOG_PATH = os.path.join(REPO_ROOT, "bookmarks_catalog.example.json")

def search_bookmarks(query="", product=None, source_type=None, topic=None, min_visits=0, limit=20, sort_recent=False):
    if not os.path.exists(CATALOG_PATH):
        print(f"Error: Catalog not found at {CATALOG_PATH}")
        sys.exit(1)
        
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    query_terms = query.lower().split() if query else []
    
    matches = []
    for bm in catalog:
        if bm.get("visit_count", 0) < min_visits:
            continue
            
        tags = bm.get("tags", {})
        prod_tags = tags.get("products", [])
        topic_tags = tags.get("topics", [])
        type_tags = tags.get("source_types", [])
        
        if product and not any(product.lower() in p.lower() for p in prod_tags):
            continue
        if topic and not any(topic.lower() in t.lower() for t in topic_tags):
            continue
        if source_type and not any(source_type.lower() in s.lower() for s in type_tags):
            continue
            
        if query_terms:
            searchable_text = f"{bm['title']} {bm['url']} {bm.get('description', '')} {bm.get('notes', '')} {' '.join(bm.get('legacy_path', []))} {' '.join(prod_tags)} {' '.join(topic_tags)} {' '.join(type_tags)}".lower()
            if not all(term in searchable_text for term in query_terms):
                continue
                
        matches.append(bm)
        
    if sort_recent:
        matches.sort(key=lambda x: int(x.get("add_date", 0)), reverse=True)
    else:
        matches.sort(key=lambda x: (-x.get("visit_count", 0), x.get("title", "").lower()))
    return matches[:limit]

def main():
    parser = argparse.ArgumentParser(description="Search saved bookmarks catalog.")
    parser.add_argument("query", nargs="*", help="Keywords to search for in title, URL, notes, and tags")
    parser.add_argument("--product", help="Filter by product tag (e.g. big-ip, nginx, f5-xc, f5-workforce-ai-security, rseries, velos)")
    parser.add_argument("--topic", help="Filter by topic tag (e.g. security-waf, access-identity, sizing-capacity)")
    parser.add_argument("--type", help="Filter by source type (e.g. kb-article, techdocs, github-repo, dashboard)")
    parser.add_argument("--min-visits", type=int, default=0, help="Minimum historical visit count")
    parser.add_argument("--limit", type=int, default=25, help="Maximum results to return")
    parser.add_argument("--recent", action="store_true", help="Sort results by most recently added first")
    parser.add_argument("--json", action="store_true", help="Output results in raw JSON format")
    
    args = parser.parse_args()
    query_str = " ".join(args.query) if args.query else ""
    
    results = search_bookmarks(
        query=query_str,
        product=args.product,
        source_type=args.type,
        topic=args.topic,
        min_visits=args.min_visits,
        limit=args.limit,
        sort_recent=args.recent
    )
    
    if args.json:
        print(json.dumps(results, indent=2))
        return
        
    print(f"\n🔍 Found {len(results)} matching bookmarks (query='{query_str}'):\n")
    if not results:
        print("No matching bookmarks found.")
        return
        
    for i, b in enumerate(results, 1):
        visits = f"[{b['visit_count']} visits]" if b.get("visit_count", 0) > 0 else "[unvisited]"
        tags = b.get("tags", {})
        tag_summary = []
        if tags.get("products"):
            tag_summary.append(f"prod:{','.join(tags['products'])}")
        if tags.get("topics"):
            tag_summary.append(f"topic:{','.join(tags['topics'])}")
        if tags.get("source_types"):
            tag_summary.append(f"type:{','.join(tags['source_types'])}")
        tag_str = f" ({' | '.join(tag_summary)})" if tag_summary else ""
        
        print(f"{i:2d}. {visits} {b['title']}")
        print(f"    🔗 {b['url']}")
        if b.get("notes"):
            print(f"    📝 Note: {b['notes']}")
        if tag_str:
            print(f"    🏷️ {tag_str}")
        print()

if __name__ == "__main__":
    main()
