#!/bin/bash
# git_push.sh — Stage all changes + new files and push
# ─────────────────────────────────────────────────────
# USAGE:
#   bash git_push.sh                        # auto commit message
#   bash git_push.sh "your commit message"  # custom message
# ─────────────────────────────────────────────────────

set -e

# ── Config ────────────────────────────────────────────
PROJECT_DIR="/media/codemonkeyxl/TBofCode/cron_llama"
BRANCH="main"

# ── Commit message ────────────────────────────────────
if [ -n "$1" ]; then
    COMMIT_MSG="$1"
else
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
    COMMIT_MSG="update: $TIMESTAMP"
fi

# ── Go to project ─────────────────────────────────────
cd "$PROJECT_DIR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Claight → git push"
echo "  Dir:    $(pwd)"
echo "  Branch: $BRANCH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check for anything to commit ──────────────────────
if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
    echo "  ✓ Nothing to commit — working tree clean."
    echo ""
    exit 0
fi

# ── Show what's changing ──────────────────────────────
echo "[1/3] Changes to be committed:"
git status --short
echo ""

# ── Stage everything ──────────────────────────────────
echo "[2/3] Staging all changes..."
git add -A

# ── Commit ────────────────────────────────────────────
echo "[3/3] Committing: \"$COMMIT_MSG\""
git commit -m "$COMMIT_MSG"

# ── Push ──────────────────────────────────────────────
echo ""
echo "  Pushing to origin/$BRANCH..."
git push origin "$BRANCH"

# ── Done ──────────────────────────────────────────────
REPO_URL=$(git remote get-url origin 2>/dev/null | sed 's/git@github.com:/https:\/\/github.com\//' | sed 's/\.git$//')
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Pushed!"
[ -n "$REPO_URL" ] && echo "  → $REPO_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
