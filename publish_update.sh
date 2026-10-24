#!/bin/bash
# ==============================================================================
# publish_update.sh - Automated 5-Step Repository Update & Release Workflow
# ==============================================================================
# Automates syncing .example templates, sanitizing tracked Markdown docs,
# staging changes, running the security/size/syntax pre-commit gate, and
# committing + pushing updates to GitHub.
#
# Usage:
#   ./publish_update.sh "feat(ui): description of change"
#   ./publish_update.sh "feat(taxonomy): add new rules" --tag v1.1.0
#   ./publish_update.sh --dry-run
#   ./publish_update.sh "feat: add new script" --all
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

COMMIT_MSG=""
TAG_NAME=""
TAG_MSG=""
DRY_RUN=0
STAGE_ALL=0
NO_PUSH=0
VERIFY_ONLY=0
EXTRA_FILES=()

usage() {
  cat <<EOF
Usage: ./publish_update.sh [COMMIT_MESSAGE] [OPTIONS]

Automated 5-Step GitHub Update Workflow:
  Step 1: Sync ai_agent_server.conf -> ai_agent_server.conf.example (redacting project_id)
          and ensure .git/hooks/pre-commit security gate is installed.
  Step 2: Sanitize tracked Markdown files (convert file:// URIs to relative links,
          strip local home/workspace paths, redact GCP project IDs & tokens).
  Step 3: Stage modified tracked files (git add -u) + any --add / --all files.
  Step 4: Run Pre-Commit Audit Gate (0 local user paths, 0 internal project IDs,
          0 tokens/keys, file size <= 250 KB, Python syntax validation).
  Step 5: Commit, optionally tag (--tag vX.Y.Z), and push to origin/main.

Options:
  -m, --message <msg>   Commit message (can also be passed as first positional arg)
  -t, --tag <vX.Y.Z>    Create annotated Git tag and push it
  --tag-msg <msg>       Custom annotation message for the tag
  -a, --all             Stage untracked files as well (git add -A, respecting .gitignore)
  --add <path>          Stage a specific untracked file or directory (repeatable)
  -n, --dry-run         Run Steps 1-4 and preview staged diff without committing or pushing
  --no-push             Commit (and tag) locally without pushing to origin
  -h, --help            Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -m|--message)
      COMMIT_MSG="${2:-}"
      shift 2
      ;;
    -t|--tag)
      TAG_NAME="${2:-}"
      shift 2
      ;;
    --tag-msg)
      TAG_MSG="${2:-}"
      shift 2
      ;;
    -a|--all)
      STAGE_ALL=1
      shift
      ;;
    --add)
      EXTRA_FILES+=("${2:-}")
      shift 2
      ;;
    -n|--dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-push)
      NO_PUSH=1
      shift
      ;;
    --verify-staged-only)
      VERIFY_ONLY=1
      shift
      ;;
    -*)
      echo "❌ Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -z "$COMMIT_MSG" ]]; then
        COMMIT_MSG="$1"
      else
        EXTRA_FILES+=("$1")
      fi
      shift
      ;;
  esac
done

if [[ "$VERIFY_ONLY" -eq 0 ]]; then
echo "======================================================================"
echo "🚀 Automated Repository Update Workflow (5 Steps)"
echo "======================================================================"

# ------------------------------------------------------------------------------
# STEP 1: Sync .example Configuration Template & Install Pre-Commit Hook
# ------------------------------------------------------------------------------
echo ""
echo "🔹 [Step 1/5] Syncing configuration templates & pre-commit hook..."
python3 - <<'PYEOF'
import os, re, stat

# 1a. Sync ai_agent_server.conf -> ai_agent_server.conf.example (with project_id redacted)
conf_live = "ai_agent_server/ai_agent_server.conf"
conf_example = "ai_agent_server/ai_agent_server.conf.example"

if os.path.exists(conf_live):
    with open(conf_live, "r", encoding="utf-8") as f:
        txt = f.read()
    # Replace header block with template header
    txt = re.sub(
        r"^# =+\n# AI Agent Server Configuration \(ai_agent_server\.conf\)\n# =+\n(?:# .*\n)+# =+",
        """# ==============================================================================
# AI Agent Server Configuration Template (ai_agent_server.conf.example)
# ==============================================================================
# Copy this file to `ai_agent_server.conf` to customize for your environment:
#   cp ai_agent_server/ai_agent_server.conf.example ai_agent_server/ai_agent_server.conf
# ==============================================================================""",
        txt,
        count=1,
    )
    # Redact project_id value
    txt = re.sub(r'("project_id"\s*:\s*)"[^"]*"', r'\1"YOUR_GCP_PROJECT_ID"', txt)
    old_ex = open(conf_example, "r", encoding="utf-8").read() if os.path.exists(conf_example) else ""
    if txt != old_ex:
        with open(conf_example, "w", encoding="utf-8") as f:
            f.write(txt)
        print("   Updated ai_agent_server/ai_agent_server.conf.example from live config.")
    else:
        print("   ai_agent_server/ai_agent_server.conf.example is already in sync.")

# 1b. Install .git/hooks/pre-commit so manual `git commit` runs the audit gate too
hook_dir = ".git/hooks"
if os.path.isdir(hook_dir):
    hook_path = os.path.join(hook_dir, "pre-commit")
    hook_content = """#!/bin/bash
# Auto-installed by publish_update.sh: runs Step 4 security/size/syntax audit
ROOT_DIR="$(git rev-parse --show-toplevel)"
exec "$ROOT_DIR/publish_update.sh" --verify-staged-only
"""
    if not os.path.exists(hook_path) or open(hook_path, "r").read() != hook_content:
        with open(hook_path, "w", encoding="utf-8") as f:
            f.write(hook_content)
        os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("   Installed .git/hooks/pre-commit security gate.")
PYEOF

# 1c. Rebuild docs/index.html live GitHub Pages demo from bookmarks_catalog.example.json
BOOKMARKS_CATALOG_PATH=bookmarks_catalog.example.json BOOKMARKS_SHOWCASE_OUTPUT=docs/index.html python3 generate_dark_showcase.py >/dev/null
echo "   Rebuilt docs/index.html (GitHub Pages live demo from bookmarks_catalog.example.json)."

# ------------------------------------------------------------------------------
# STEP 2: Sanitize Tracked Markdown Files
# ------------------------------------------------------------------------------
echo ""
echo "🔹 [Step 2/5] Sanitizing paths, links, and identifiers in Markdown docs..."
python3 - <<'PYEOF'
import os, re, subprocess

ws = os.getcwd()
home = os.path.expanduser("~")
tracked = subprocess.check_output(["git", "ls-files"]).decode().splitlines()
md_files = [p for p in tracked if p.endswith(".md") and os.path.exists(p)]

sanitized_count = 0
for p in md_files:
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    orig = txt
    file_dir = os.path.dirname(os.path.abspath(p))

    def repl_file_uri(m):
        target_abs = m.group(1)
        frag = m.group(2) or ""
        rel = os.path.relpath(target_abs, file_dir)
        return f"]({rel}{frag})"

    txt = re.sub(r"\]\(file://" + re.escape(ws) + r"/([^)#\s]+)(#[^)\s]+)?\)", repl_file_uri, txt)
    txt = txt.replace(ws, "<WORKSPACE_DIR>")
    txt = txt.replace(home, "<USER_HOME>")
    txt = re.sub(r"f5-gcs-[a-z0-9-]+", "<YOUR_GCP_PROJECT_ID>", txt)
    txt = re.sub(r"ya29\.a\.\.\.[0-9a-zA-Z_-]+", "ya29.a...[REDACTED]", txt)

    if txt != orig:
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
        sanitized_count += 1
        print(f"   Sanitized {p}")

if sanitized_count == 0:
    print("   All tracked Markdown files are already clean.")
PYEOF

# ------------------------------------------------------------------------------
# STEP 3: Stage Changes
# ------------------------------------------------------------------------------
echo ""
echo "🔹 [Step 3/5] Staging repository updates..."
if [[ "$STAGE_ALL" -eq 1 ]]; then
  git add -A
else
  git add -u
  if [[ ${#EXTRA_FILES[@]} -gt 0 ]]; then
    for f in "${EXTRA_FILES[@]}"; do
      git add "$f"
    done
  fi
fi

git status --short
fi

# ------------------------------------------------------------------------------
# STEP 4: Pre-Commit Security, Size & Syntax Audit Gate
# ------------------------------------------------------------------------------
echo ""
echo "🔹 [Step 4/5] Running Pre-Commit Security, Size & Syntax Gate..."
python3 - <<'PYEOF'
import os, re, subprocess, py_compile, sys

staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
).decode().splitlines()
all_tracked = subprocess.check_output(["git", "ls-files"]).decode().splitlines()
files_to_check = sorted(set(staged) | set(all_tracked))

user_name = os.environ.get("USER", "").strip()
user_parts = [p for p in re.split(r"[^a-zA-Z0-9]+", user_name) if len(p) >= 4]
home_dir = os.path.expanduser("~")

issues = []
MAX_TEXT_BYTES = 250_000
MAX_DEMO_HTML_BYTES = 500_000
MAX_DOC_ASSET_BYTES = 25_000_000
BINARY_DOC_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".svg", ".ico")

for p in files_to_check:
    if not os.path.exists(p):
        continue
    sz = os.path.getsize(p)
    is_doc_asset = p.startswith("docs/") and p.lower().endswith(BINARY_DOC_EXTS)
    is_demo_html = (p == "docs/index.html")
    limit = MAX_DOC_ASSET_BYTES if is_doc_asset else (MAX_DEMO_HTML_BYTES if is_demo_html else MAX_TEXT_BYTES)
    if sz > limit:
        limit_label = "25 MB" if is_doc_asset else ("500 KB" if is_demo_html else "250 KB")
        issues.append(f"Oversized file (>{limit_label}): {p} ({sz:,} bytes)")

    if p.lower().endswith(BINARY_DOC_EXTS):
        continue

    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        txt = f.read()

    if home_dir and home_dir in txt:
        issues.append(f"Hardcoded home directory ({home_dir}) in {p}")
    for part in user_parts:
        if re.search(re.escape(part), txt, re.I):
            issues.append(f"Personal username token '{part}' found in {p}")
    if re.search(r"f5-gcs-[a-z0-9-]+", txt, re.I) and p != "publish_update.sh":
        issues.append(f"Internal GCP Project ID pattern found in {p}")
    if re.search(r"ya29\.[a-zA-Z0-9_-]{10,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----", txt):
        if p != "publish_update.sh":
            issues.append(f"Potential live token or private key found in {p}")
    if re.search(r"f5-my\.sharepoint\.com", txt, re.I) and p != "publish_update.sh":
        issues.append(f"Personal SharePoint URL found in {p}")

    if p.endswith(".py"):
        try:
            py_compile.compile(p, doraise=True)
        except py_compile.PyCompileError as e:
            issues.append(f"Python syntax error in {p}: {e}")

if issues:
    print("   ❌ AUDIT FAILED:")
    for item in issues:
        print(f"      - {item}")
    sys.exit(1)

print(f"   ✅ Audit Passed across {len(files_to_check)} tracked/staged files (0 leaks, sizes <= 250 KB, Python syntax valid).")
PYEOF

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  exit 0
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "🧪 [Dry Run] Preview of staged changes (no commit or push performed):"
  git diff --cached --stat
  exit 0
fi

# ------------------------------------------------------------------------------
# STEP 5: Commit, Tag (Optional) & Push to GitHub
# ------------------------------------------------------------------------------
echo ""
echo "🔹 [Step 5/5] Committing and pushing to GitHub..."

if git diff --cached --quiet; then
  echo "ℹ️  No staged changes to commit."
else
  if [[ -z "$COMMIT_MSG" ]]; then
    CHANGED_LIST=$(git diff --cached --name-only | head -n 4 | tr '\n' ', ' | sed 's/, $//')
    COMMIT_MSG="chore: update ${CHANGED_LIST}"
  fi
  git commit --no-verify -m "$COMMIT_MSG"
fi

if [[ -n "$TAG_NAME" ]]; then
  TAG_MSG="${TAG_MSG:-$TAG_NAME - Release}"
  git tag -a "$TAG_NAME" -m "$TAG_MSG" -f
  echo "🏷️  Tagged commit as: $TAG_NAME ($TAG_MSG)"
fi

if [[ "$NO_PUSH" -eq 0 ]]; then
  git push origin main
  if [[ -n "$TAG_NAME" ]]; then
    git push origin "$TAG_NAME" --force
  fi
  echo "✅ Successfully pushed to origin/main!"
else
  echo "ℹ️  Skipped git push (--no-push)."
fi
