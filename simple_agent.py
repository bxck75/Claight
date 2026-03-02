#!/usr/bin/env python3
"""
Minimal Cron Agent
------------------
--mode init   --task "..."   → analyze task, make plan, schedule self via cron
--mode worker                → pick next todo, run it, save state
--mode status                → print current state
--mode done                  → remove self from crontab

State lives in state.json.
Cron is the heartbeat.
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
AGENT_PATH  = os.path.abspath(__file__)
STATE_FILE  = Path("state.json")
LOCK_FILE   = Path("/tmp/cron_agent.lock")
CRON_TAG    = "# cron-agent-managed"
CRON_EVERY  = 5   # minutes between worker ticks

# ── LLM call (swap for llama-cpp-python or any local/remote endpoint) ─────────
def llm(system: str, user: str, json_schema: dict | None = None) -> dict | str:
    """
    Minimal LLM shim. Replace the body with your actual inference call.

    Using llama-cpp-python (local GGUF):
        from llama_cpp import Llama
        model = Llama(model_path="model.gguf", n_gpu_layers=-1, n_ctx=4096)
        resp  = model.create_chat_completion(
                    messages=[{"role":"system","content":system},
                               {"role":"user","content":user}],
                    response_format={"type":"json_object"} if json_schema else None)
        return json.loads(resp["choices"][0]["message"]["content"])

    Using Anthropic API (claude.ai):
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system,
            messages=[{"role":"user","content":user}])
        return msg.content[0].text

    For now: stub returns a fake plan so the scaffolding is testable without a model.
    """
    # ── STUB — replace with real inference ────────────────────────────────────
    if "plan" in user.lower():
        return {
            "goal":  user,
            "plan":  "Stub plan — wire up a real LLM in the llm() function.",
            "todos": [
                {"id": 1, "title": "Analyse requirements", "status": "PENDING", "result": ""},
                {"id": 2, "title": "Draft solution",       "status": "PENDING", "result": ""},
                {"id": 3, "title": "Write output file",    "status": "PENDING", "result": ""},
            ]
        }
    return {"result": f"Stub worker result for: {user}", "notes": "replace llm() stub"}
    # ─────────────────────────────────────────────────────────────────────────


# ── State helpers ──────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def log(state: dict, msg: str):
    state.setdefault("log", []).append({
        "ts":  datetime.now().isoformat(timespec="seconds"),
        "msg": msg
    })
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ── Cron management ───────────────────────────────────────────────────────────
def cron_line() -> str:
    return f"*/{CRON_EVERY} * * * * {sys.executable} {AGENT_PATH} --mode worker {CRON_TAG}"

def cron_add():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    if CRON_TAG in existing:
        return  # already scheduled
    new_crontab = existing.rstrip("\n") + "\n" + cron_line() + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
    print(f"✓ Cron added — fires every {CRON_EVERY} min")

def cron_remove():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return
    filtered = "\n".join(
        line for line in result.stdout.splitlines()
        if CRON_TAG not in line
    ) + "\n"
    subprocess.run(["crontab", "-"], input=filtered, text=True, check=True)
    print("✓ Cron removed — agent is idle")


# ── Mutex (skip tick if already running) ──────────────────────────────────────
def acquire_lock():
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock
    except BlockingIOError:
        print("Already running — skipping this tick.")
        sys.exit(0)


# ── Modes ─────────────────────────────────────────────────────────────────────
def mode_init(task: str):
    """Analyze task → plan → todos → schedule cron → run first todo."""
    print(f"\n🧠  Analyzing: {task}")

    system = (
        "You are a planning agent. Respond ONLY with valid JSON.\n"
        "Schema: {goal: str, plan: str, todos: [{id: int, title: str, status: 'PENDING', result: ''}]}\n"
        "Break the task into 3-5 concrete, actionable todos."
    )
    data = llm(system, f"Task: {task}")

    state = {
        "goal":    data["goal"],
        "plan":    data["plan"],
        "todos":   data["todos"],
        "created": datetime.now().isoformat(timespec="seconds"),
        "log":     []
    }
    log(state, f"Init — goal: {task}")
    log(state, f"Plan: {data['plan']}")
    save_state(state)

    print(f"\n📋  Plan: {data['plan']}")
    print(f"📝  Todos ({len(data['todos'])}):")
    for t in data["todos"]:
        print(f"    [{t['id']}] {t['title']}")

    cron_add()
    print("\n▶  Running first todo now…\n")
    mode_worker()


def mode_worker():
    """Pick next PENDING todo, infer, save result. If done → remove cron."""
    lock = acquire_lock()

    state = load_state()
    if not state:
        print("No state found. Run --mode init first.")
        return

    # Find next pending todo
    todo = next((t for t in state["todos"] if t["status"] == "PENDING"), None)
    if not todo:
        log(state, "All todos complete.")
        save_state(state)
        cron_remove()
        print("\n🏁  All done!")
        return

    log(state, f"Starting todo [{todo['id']}]: {todo['title']}")
    save_state(state)

    system = (
        "You are an execution agent. Respond ONLY with valid JSON.\n"
        "Schema: {result: str, notes: str}\n"
        "result: concrete deliverable (code, text, findings). NEVER just 'done'.\n"
        f"Overall goal: {state['goal']}\n"
        f"Plan: {state['plan']}"
    )
    user = f"Complete this todo: {todo['title']}"

    start = time.time()
    out   = llm(system, user)
    elapsed = round(time.time() - start, 1)

    todo["status"] = "DONE"
    todo["result"] = out.get("result", str(out))
    todo["notes"]  = out.get("notes", "")

    log(state, f"Done [{todo['id']}] in {elapsed}s — {todo['result'][:80]}…")
    save_state(state)

    pending = sum(1 for t in state["todos"] if t["status"] == "PENDING")
    print(f"\n✓  Todo {todo['id']} done.  {pending} remaining.")

    if pending == 0:
        log(state, "All todos complete — removing cron.")
        save_state(state)
        cron_remove()
        print("\n🏁  All done! Check state.json for results.")


def mode_status():
    """Pretty-print current state."""
    state = load_state()
    if not state:
        print("No active task. Run: python agent.py --mode init --task '...'")
        return

    print(f"\n🎯  Goal:   {state.get('goal', '?')}")
    print(f"📋  Plan:   {state.get('plan', '?')}\n")

    for t in state.get("todos", []):
        icon = {"DONE": "✅", "PENDING": "⏳", "ERROR": "❌"}.get(t["status"], "?")
        print(f"  {icon} [{t['id']}] {t['title']}")
        if t.get("result"):
            print(f"         → {t['result'][:120]}")

    log_tail = state.get("log", [])[-5:]
    if log_tail:
        print("\n📜  Recent log:")
        for entry in log_tail:
            print(f"  {entry['ts']}  {entry['msg']}")


def mode_done():
    """Manually remove cron (abort)."""
    cron_remove()
    state = load_state()
    if state:
        log(state, "Manually stopped.")
        save_state(state)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal Cron Agent")
    parser.add_argument("--mode", choices=["init", "worker", "status", "done"], required=True)
    parser.add_argument("--task", type=str, default="")
    args = parser.parse_args()

    if   args.mode == "init":   mode_init(args.task)
    elif args.mode == "worker": mode_worker()
    elif args.mode == "status": mode_status()
    elif args.mode == "done":   mode_done()