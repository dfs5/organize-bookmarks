#!/usr/bin/env python3
"""
Local Persistent Session & Project Memory Manager for organize-bookmarks.

Commands:
  status                         Show current in-session state, project memory size, & vector index stats
  set-goal "<goal>"              Set the active session goal
  add-step "<pending step>"      Add a pending step to the session queue
  complete-step "<step>"         Mark a step completed (and remove matching pending step)
  add-note "<note>"              Record a key finding/fact in working_notes (max 12 kept)
  clear-notes                    Clear working notes
  compact [--summary "<text>"]   Roll completed session work into project_memory.md, re-index, and reset session state
  index [--force]                Chunk & embed all project memory / rule / maintenance files into memory_index.sqlite
  search "<query>" [--top-k N]   Hybrid Vector + SQLite FTS5 BM25 semantic search across indexed memory
"""

import argparse
import datetime
import json
import os
import sys

MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
if MEMORY_DIR not in sys.path:
    sys.path.insert(0, MEMORY_DIR)

from memory_indexer import MemoryVectorStore

SESSION_FILE = os.path.join(MEMORY_DIR, "session_state.json")
PROJECT_FILE = os.path.join(MEMORY_DIR, "project_memory.md")

MAX_NOTES = 12
MAX_COMPLETED = 10


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load_session() -> dict:
    if not os.path.exists(SESSION_FILE):
        return {
            "updated_at": now_iso(),
            "active_goal": "Idle / awaiting task",
            "completed_steps": [],
            "pending_steps": [],
            "working_notes": [],
            "recent_files_modified": [],
        }
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "updated_at": now_iso(),
            "active_goal": "Idle / awaiting task",
            "completed_steps": [],
            "pending_steps": [],
            "working_notes": [],
            "recent_files_modified": [],
        }


def save_session(state: dict) -> None:
    state["updated_at"] = now_iso()
    state["completed_steps"] = state.get("completed_steps", [])[-MAX_COMPLETED:]
    state["working_notes"] = state.get("working_notes", [])[-MAX_NOTES:]
    state["recent_files_modified"] = state.get("recent_files_modified", [])[-10:]
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def format_ephemeral_snapshot(state: dict) -> str:
    lines = [
        "🧠 [LOCAL SESSION MEMORY SNAPSHOT]",
        f"• Active Goal: {state.get('active_goal', 'None')}",
    ]
    completed = state.get("completed_steps", [])
    if completed:
        lines.append("• Completed in Session: " + " | ".join(completed[-5:]))
    pending = state.get("pending_steps", [])
    if pending:
        lines.append("• Pending Next Steps: " + " | ".join(pending[:5]))
    notes = state.get("working_notes", [])
    if notes:
        lines.append("• Key Working Notes: " + " ; ".join(notes[-6:]))
    files = state.get("recent_files_modified", [])
    if files:
        lines.append("• Recent Touched Files: " + ", ".join(files[-6:]))
    lines.append(
        "• Tip: Update via `python3 .agents/memory/memory_cli.py [set-goal|complete-step|add-note|search|compact]`"
    )
    return "\n".join(lines)


def cmd_status(_args):
    state = load_session()
    print(format_ephemeral_snapshot(state))
    if os.path.exists(PROJECT_FILE):
        sz = os.path.getsize(PROJECT_FILE)
        print(f"\n📚 Project Memory ({PROJECT_FILE}): {sz:,} bytes (budget: 8,000 bytes)")
    store = MemoryVectorStore()
    istats = store.get_index_stats()
    if istats.get("indexed"):
        print(
            f"🔎 Vector + FTS5 Memory Index: {istats['chunks']} chunks across {len(istats['files'])} files "
            f"({istats['db_size_bytes']:,} bytes) | Provider: {', '.join(istats['providers'])}"
        )


def cmd_set_goal(args):
    state = load_session()
    state["active_goal"] = args.goal.strip()
    if args.reset_steps:
        state["completed_steps"] = []
        state["pending_steps"] = []
    save_session(state)
    print(f"Updated active_goal -> {state['active_goal']}")


def cmd_add_step(args):
    state = load_session()
    step = args.step.strip()
    if step and step not in state["pending_steps"]:
        state["pending_steps"].append(step)
    save_session(state)
    print(f"Added pending step: {step}")


def cmd_complete_step(args):
    state = load_session()
    step = args.step.strip()
    if step:
        state["completed_steps"].append(step)
        state["pending_steps"] = [
            p for p in state.get("pending_steps", []) if p.lower() != step.lower()
        ]
    save_session(state)
    print(f"Completed step: {step}")


def cmd_add_note(args):
    state = load_session()
    note = args.note.strip()
    if note and note not in state["working_notes"]:
        state["working_notes"].append(note)
    save_session(state)
    print(f"Added working note: {note}")


def cmd_clear_notes(_args):
    state = load_session()
    state["working_notes"] = []
    save_session(state)
    print("Cleared working notes.")


def cmd_compact(args):
    state = load_session()
    today = datetime.date.today().isoformat()
    summary = args.summary
    if not summary:
        goal = state.get("active_goal", "")
        done = state.get("completed_steps", [])
        if done:
            summary = f"{goal}: " + "; ".join(done)
        else:
            summary = goal

    if summary and os.path.exists(PROJECT_FILE):
        with open(PROJECT_FILE, "r", encoding="utf-8") as f:
            content = f.read().rstrip()
        entry = f"\n- **{today}**: {summary.strip()}\n"
        with open(PROJECT_FILE, "w", encoding="utf-8") as f:
            f.write(content + entry)
        print(f"Appended milestone to {PROJECT_FILE}:\n  {entry.strip()}")

    new_state = {
        "updated_at": now_iso(),
        "active_goal": "Idle / awaiting next task",
        "completed_steps": [],
        "pending_steps": [],
        "working_notes": [],
        "recent_files_modified": state.get("recent_files_modified", [])[-5:],
    }
    save_session(new_state)
    try:
        MemoryVectorStore().index_all(force=False)
    except Exception:
        pass
    print("Session state compacted, re-indexed, and reset.")


def cmd_index(args):
    store = MemoryVectorStore()
    stats = store.index_all(force=args.force)
    print(
        f"✅ Indexed {stats['chunks_total']} chunks across {stats['files']} files "
        f"({stats['chunks_embedded']} newly embedded, {stats['chunks_cached']} cached) "
        f"using [{stats['provider']}]"
    )


def cmd_search(args):
    store = MemoryVectorStore()
    results = store.search(args.query, top_k=args.top_k)
    if args.json:
        print(json.dumps(results, indent=2))
        return
    print(f"🔎 Memory Search Results for: '{args.query}' (Top {len(results)}):")
    for idx, r in enumerate(results, 1):
        print(
            f"\n[{idx}] {r['source_file']} ({r['line_range']}) — {r['section_title']} "
            f"[score={r['hybrid_score']} | vec={r['vector_sim']} | fts={r['fts_score']}]"
        )
        snippet = r["content"]
        if len(snippet) > 420:
            snippet = snippet[:420] + " ..."
        for line in snippet.splitlines():
            print(f"    {line}")


def main():
    parser = argparse.ArgumentParser(description="Session & Project Memory CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    p_goal = sub.add_parser("set-goal")
    p_goal.add_argument("goal", help="Active session goal")
    p_goal.add_argument("--reset-steps", action="store_true", help="Clear completed/pending steps")

    p_add = sub.add_parser("add-step")
    p_add.add_argument("step", help="Pending step description")

    p_done = sub.add_parser("complete-step")
    p_done.add_argument("step", help="Completed step description")

    p_note = sub.add_parser("add-note")
    p_note.add_argument("note", help="Working note or finding to persist")

    sub.add_parser("clear-notes")

    p_compact = sub.add_parser("compact")
    p_compact.add_argument("--summary", default="", help="Milestone summary to append to project_memory.md")

    p_index = sub.add_parser("index")
    p_index.add_argument("--force", action="store_true", help="Force re-embedding all chunks")

    p_search = sub.add_parser("search")
    p_search.add_argument("query", help="Semantic or keyword query")
    p_search.add_argument("--top-k", type=int, default=4, help="Max chunks to return (default: 4)")
    p_search.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    dispatch = {
        "status": cmd_status,
        "set-goal": cmd_set_goal,
        "add-step": cmd_add_step,
        "complete-step": cmd_complete_step,
        "add-note": cmd_add_note,
        "clear-notes": cmd_clear_notes,
        "compact": cmd_compact,
        "index": cmd_index,
        "search": cmd_search,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
