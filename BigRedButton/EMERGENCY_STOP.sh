#!/bin/bash
# ╔══════════════════════════════════════════════╗
# ║         CLAIGHT — BIG RED BUTTON            ║
# ║   Use when agent goes feral                 ║
# ║   Stops ALL agent activity immediately      ║
# ╚══════════════════════════════════════════════╝

echo ""
echo "🔴 EMERGENCY STOP — Claight"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Nuke all cron entries
echo "[1] Removing cron entries..."
crontab -l 2>/dev/null | grep -v "llm-agent-worker" | crontab -
echo "    ✓ cron cleared"

# 2. Kill any running worker processes
echo "[2] Killing worker processes..."
pkill -f "agent.py --mode worker" 2>/dev/null && echo "    ✓ workers killed" || echo "    ✓ no workers running"
pkill -f "agent.py --mode init"   2>/dev/null

# 3. Release the mutex lock
echo "[3] Releasing mutex lock..."
rm -f /tmp/agent_worker.lock && echo "    ✓ lock released" || echo "    ✓ no lock found"

# 4. Show what's left running
echo "[4] Checking for survivors..."
REMAINING=$(pgrep -f "agent.py" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "    ⚠️  $REMAINING process(es) still running:"
    pgrep -fa "agent.py"
    echo ""
    echo "    Nuclear option: kill -9 \$(pgrep -f agent.py)"
else
    echo "    ✓ all clear"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Agent stopped. South Korea and Belgium are safe."
echo ""
echo "State preserved in data/state.json"
echo "Resume with: python agent.py --mode worker"
echo "Restart with: python agent.py --mode init --task '...'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
