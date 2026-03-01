#!/bin/bash
# ⚠️  WIPE everything — stop agent AND clear state
# Use when you want a completely fresh start
# This is the "forget everything" button

PROJECT_DIR="/media/codemonkeyxl/TBofCode/cron_llama"

echo ""
echo "💣 NUKE STATE — Claight"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  This will:"
echo "   - Stop all agent activity"
echo "   - DELETE data/state.json"
echo "   - DELETE data/summary.json"
echo "   - Clear cron"
echo "   - Clear logs"
echo ""
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

cd "$PROJECT_DIR"

# stop everything
crontab -l 2>/dev/null | grep -v "llm-agent-worker" | crontab -
pkill -f "agent.py" 2>/dev/null
rm -f /tmp/agent_worker.lock
rm -f /tmp/agent_cron.log

# wipe state
rm -f data/state.json
rm -f data/summary.json

echo "✓ All clear. Claight has amnesia."
echo ""
echo "Fresh start: python agent.py --mode init --task '...'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
