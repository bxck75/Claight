#!/bin/bash
# Resume agent after emergency stop or crash
# Picks up from where it left off — does NOT restart from scratch

PROJECT_DIR="/media/codemonkeyxl/TBofCode/cron_llama"

echo ""
echo "▶️  Resuming Claight..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$PROJECT_DIR"

# check state exists
if [ ! -f "data/state.json" ]; then
    echo "❌ No state.json found — nothing to resume."
    echo "   Start fresh with: python agent.py --mode init --task '...'"
    exit 1
fi

# show current state
echo "[state]"
python3 -c "
import json
s = json.load(open('data/state.json'))
done    = [t for t in s['todos'] if t['status'] == 'DONE']
pending = [t for t in s['todos'] if t['status'] == 'PENDING']
print(f'  goal: {s[\"goal\"]}')
print(f'  progress: {len(done)}/{len(s[\"todos\"])} done')
if pending:
    print(f'  next: {pending[0][\"task\"]}')
"

# release stale lock if exists
rm -f /tmp/agent_worker.lock

# re-add cron
source venv/bin/activate 2>/dev/null
python agent.py --mode worker

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Resumed. Cron will continue automatically."
echo ""
