#!/usr/bin/env python3
"""
Antigravity Lifecycle Hook Dispatcher for organize-bookmarks.

Modes:
  --mode pre-invocation   Injects compact session_state.json as an ephemeralMessage on Turn 1 or after compaction.
  --mode pre-tool-use     Guards against unbounded view_file on multi-MB JSON/HTML files and auto-tracks modified files.
"""

import json
import os
import sys

MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.abspath(os.path.join(MEMORY_DIR, "..", ".."))
SESSION_FILE = os.path.join(MEMORY_DIR, "session_state.json")

# Files that must NEVER be viewed without tight line bounds because they blow up the context window
GENERATED_OR_MEGA_FILES = {
    "bookmarks_showcase.html": (
        "bookmarks_showcase.html (4.0 MB) is a generated file. "
        "Edit generate_dark_showcase.py using the line ranges in AGENTS.md instead."
    ),
    "favorites_product_frequency_organized.html": (
        "favorites_product_frequency_organized.html (390 KB) is a generated file. "
        "Edit update_and_reorganize_bookmarks.py instead."
    ),
    "bookmarks_catalog.json": (
        "bookmarks_catalog.json (2.0 MB) is too large for view_file without tight StartLine/EndLine (<=120 lines). "
        "Query via `python3 .agents/skills/bookmark-lookup/lookup.py` or a small Python filter script."
    ),
    "bookmarks_verified_metadata.json": (
        "bookmarks_verified_metadata.json (2.2 MB) is too large for view_file. "
        "Inspect specific URL keys using a short inline Python snippet."
    ),
    "bookmarks_content_cache.json": (
        "bookmarks_content_cache.json (1.2 MB) is too large for view_file. "
        "Inspect specific URL keys using a short inline Python snippet."
    ),
}


def load_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def load_session() -> dict:
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def record_modified_file(abs_path: str) -> None:
    if not abs_path:
        return
    try:
        rel = os.path.relpath(abs_path, WORKSPACE_ROOT)
        if rel.startswith("..") or rel.startswith(".agents/memory/session_state"):
            return
        state = load_session()
        if not state:
            return
        recent = state.get("recent_files_modified", [])
        if rel in recent:
            recent.remove(rel)
        recent.append(rel)
        state["recent_files_modified"] = recent[-8:]
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def handle_pre_invocation(_payload: dict) -> None:
    state = load_session()
    if not state:
        print(json.dumps({}))
        return

    parts = [
        f"[Session Memory] Goal: {state.get('active_goal', 'None')}"
    ]
    done = state.get("completed_steps", [])
    if done:
        parts.append("Done: " + " | ".join(done[-4:]))
    pending = state.get("pending_steps", [])
    if pending:
        parts.append("Next: " + " | ".join(pending[:4]))
    notes = state.get("working_notes", [])
    if notes:
        parts.append("Notes: " + " ; ".join(notes[-5:]))
    files = state.get("recent_files_modified", [])
    if files:
        parts.append("Touched: " + ", ".join(files[-5:]))

    msg = " • ".join(parts)
    print(
        json.dumps(
            {
                "injectSteps": [
                    {
                        "ephemeralMessage": msg
                    }
                ]
            }
        )
    )


def handle_pre_tool_use(payload: dict) -> None:
    tool_call = payload.get("toolCall", {})
    name = tool_call.get("name", "")
    args = tool_call.get("args", {}) or {}

    if name == "view_file":
        abs_path = args.get("AbsolutePath", "")
        bname = os.path.basename(abs_path)
        start_line = args.get("StartLine")
        end_line = args.get("EndLine")

        if bname in GENERATED_OR_MEGA_FILES:
            # Allow only if explicit tight line range (<= 150 lines) is given
            if start_line is None or end_line is None or (end_line - start_line) > 150:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": f"[Context Guard] {GENERATED_OR_MEGA_FILES[bname]}",
                        }
                    )
                )
                return

        # Also guard large Python scripts (>100KB) from full-file view_file without line bounds
        if bname in ("ai_agent_server.py", "generate_dark_showcase.py"):
            if start_line is None and end_line is None:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": (
                                f"[Context Guard] {bname} is over 2,600 lines. "
                                "Consult the Code Map in AGENTS.md and specify StartLine and EndLine (<= 250 lines)."
                            ),
                        }
                    )
                )
                return

    elif name in ("replace_file_content", "multi_replace_file_content", "write_to_file"):
        target = args.get("TargetFile", "")
        record_modified_file(target)

    print(json.dumps({"decision": "allow"}))


def main():
    mode = "pre-invocation"
    if len(sys.argv) >= 3 and sys.argv[1] == "--mode":
        mode = sys.argv[2]

    payload = load_stdin_json()
    if mode == "pre-tool-use":
        handle_pre_tool_use(payload)
    else:
        handle_pre_invocation(payload)


if __name__ == "__main__":
    main()
