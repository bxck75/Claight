#!/bin/bash
# push_to_git.sh — Create new GitHub repo "Claight" and push
# ─────────────────────────────────────────────────────────────
# BEFORE RUNNING:
#   1. Install GitHub CLI:  sudo apt install gh
#   2. Authenticate:        gh auth login
#   3. Run from your project root:  bash push_to_git.sh
# ─────────────────────────────────────────────────────────────

set -e  # stop on any error

REPO_NAME="Claight"
DESCRIPTION="A self-scheduling autonomous local LLM agent with cron heartbeat, persistent identity, and key-bound structured JSON output"
PROJECT_DIR="/media/codemonkeyxl/TBofCode/cron_llama"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Claight → GitHub"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: go to project ─────────────────────
cd "$PROJECT_DIR"
echo "[1/7] Working in: $(pwd)"

# ── Step 2: write .gitignore ──────────────────
echo "[2/7] Writing .gitignore..."
cat > .gitignore << 'EOF'
# personal — never commit
workspace/USER.md
workspace/TOOLS.md
workspace/IDENTITY.md
workspace/memory/

# runtime state
data/
/tmp/agent_*.log
/tmp/agent_worker.lock

# models — never commit
*.gguf
*.bin

# python
__pycache__/
*.pyc
*.pyo
.env
venv/
env/
.venv/

# editor
.vscode/
.idea/
*.swp
EOF

# ── Step 3: write requirements.txt ───────────
echo "[3/7] Writing requirements.txt..."
cat > requirements.txt << 'EOF'
# llama-cpp-python must be installed manually with CUDA flags:
# CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python --force-reinstall
#
# pip install -r requirements.txt
rich
pathlib
EOF

# ── Step 4: git init + first commit ──────────
echo "[4/7] Initialising git..."
git init
git add .
git commit -m "init: Claight — self-scheduling local LLM agent

- cron heartbeat loop with mutex lock
- local llama-cpp CUDA via ShimSalaBim venv shim
- key-bound structured JSON schema with description micro-prompts
- token budget per schema field prevents tail truncation
- workspace/ soul files for persistent agent identity
- state.json memory between cron wakes
- modes: init / worker / chat / status"

# ── Step 5: create GitHub repo ───────────────
echo "[5/7] Creating GitHub repo: $REPO_NAME..."
gh repo create "$REPO_NAME" \
    --public \
    --description "$DESCRIPTION" \
    --source=. \
    --remote=origin

# ── Step 6: push ─────────────────────────────
echo "[6/7] Pushing to GitHub..."
git branch -M main
git push -u origin main

# ── Step 7: done ─────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Done!"
echo "  → https://github.com/$(gh api user --jq .login)/$REPO_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""