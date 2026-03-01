#!/bin/bash
# Quick health check — what is Claight doing right now?

echo ""
echo "🦞 Claight — Status Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "[cron]"
CRON=$(crontab -l 2>/dev/null | grep "llm-agent-worker")
if [ -n "$CRON" ]; then
    echo "  ✓ scheduled: $CRON"
else
    echo "  ✗ not scheduled"
fi

echo "[processes]"
PROCS=$(pgrep -fa "agent.py" 2>/dev/null)
if [ -n "$PROCS" ]; then
    echo "  ✓ running:"
    echo "    $PROCS"
else
    echo "  ✗ not running"
fi

echo "[lock]"
if [ -f /tmp/agent_worker.lock ]; then
    echo "  ⚠️  lock file exists — worker may be active"
else
    echo "  ✓ no lock"
fi

echo "[log — last 5 lines]"
tail -5 /tmp/agent_cron.log 2>/dev/null || echo "  no log yet"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
