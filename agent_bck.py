"""
agent.py — Self-scheduling LLM agent
--------------------------------------
USAGE:
  python agent.py --mode init  --task "Build a simple todo CLI app"
  python agent.py --mode worker        # called by cron automatically
  python agent.py --mode chat --msg "what are you working on?"
  python agent.py --mode status        # print the state file pretty
"""

import json
import argparse
import subprocess
import sys
import fcntl
from pathlib import Path
from datetime import datetime

from config import LLM_MODEL_PATH, CRON_INTERVAL_MINUTES, AGENT_SCRIPT_PATH, STATE_FILE
from modules.shimsalabim import ShimSalaBim

# ─────────────────────────────────────────────
#  SHIM — GPU-enabled llama_cpp from root
# ─────────────────────────────────────────────

global_packages_folder = '/home/codemonkeyxl/.local/lib/python3.10/site-packages'
global_pkgs = [
    ('llama_cpp',           global_packages_folder),
    ('torch',               global_packages_folder),
    ('torchvision',         global_packages_folder),
    ('langchain',           global_packages_folder),
    ('langchain_community', global_packages_folder),
    ('accelerate',          global_packages_folder),
    ('safetensors',         global_packages_folder),
    ('gguf',                global_packages_folder),
]

shim = ShimSalaBim(global_pkgs, classes_to_wrap={})
Llama = shim.llama_cpp.Llama
if not Llama:
    from llama_cpp import Llama


# ─────────────────────────────────────────────
#  LLM  — loaded once, used by all modes
# ─────────────────────────────────────────────

llm = Llama(
    model_path=LLM_MODEL_PATH,
    chat_format="llama-3",
    n_gpu_layers=31,
    n_ctx=12000,
    verbose=False,
)


def ask(system: str, user: str, schema: dict) -> dict:
    """Single LLM call. Always returns a dict (enforced by JSON schema)."""
    result = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        response_format={"type": "json_object", "schema": schema},
        temperature=0.7,
        max_tokens=1024,
    )
    raw = result["choices"][0]["message"]["content"]
    return json.loads(raw)


# ─────────────────────────────────────────────
#  STATE  — the agent's memory between wakes
# ─────────────────────────────────────────────

def load_state() -> dict:
    p = Path(STATE_FILE)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save_state(state: dict):
    p = Path(STATE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2))


# ─────────────────────────────────────────────
#  CRON  — add / remove this script from crontab
# ─────────────────────────────────────────────

CRON_TAG  = "# llm-agent-worker"
LOCK_FILE = "/tmp/agent_worker.lock"


def cron_add():
    cron_line = (
        f"*/{CRON_INTERVAL_MINUTES} * * * * "
        f"{sys.executable} {AGENT_SCRIPT_PATH} --mode worker "
        f">> /tmp/agent_cron.log 2>&1 {CRON_TAG}"
    )
    current = subprocess.getoutput("crontab -l 2>/dev/null")
    if CRON_TAG in current:
        return
    new_crontab = current.rstrip() + "\n" + cron_line + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab.encode(), check=True)
    print(f"[cron] scheduled every {CRON_INTERVAL_MINUTES} min → log: /tmp/agent_cron.log")


def cron_remove():
    current = subprocess.getoutput("crontab -l 2>/dev/null")
    lines = [l for l in current.splitlines() if CRON_TAG not in l]
    new_crontab = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab.encode(), check=True)
    print("[cron] removed — agent finished all work")


# ─────────────────────────────────────────────
#  MODES
# ─────────────────────────────────────────────

def mode_init(task: str):
    print(f"\n[init] Goal: {task}")

    plan_resp = ask(
        system="You are a project planner. Output JSON only.",
        user=f"Write a concise step-by-step plan for this task: {task}",
        schema={
            "type": "object",
            "properties": {"plan_summary": {"type": "string"}},
            "required": ["plan_summary"],
        },
    )
    plan_text = plan_resp["plan_summary"]
    print(f"[init] Plan:\n{plan_text}\n")

    todos_resp = ask(
        system="You are a project planner. Output JSON only.",
        user=(
            f"Break this plan into 3-5 concrete, actionable todos (short titles).\n"
            f"Plan: {plan_text}"
        ),
        schema={
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["todos"],
        },
    )
    todos = [
        {"id": i, "task": t, "status": "PENDING", "result": None}
        for i, t in enumerate(todos_resp["todos"])
    ]
    print(f"[init] Todos: {[t['task'] for t in todos]}")

    state = {
        "goal": task,
        "plan": plan_text,
        "todos": todos,
        "started_at": datetime.now().isoformat(),
        "log": [],
    }
    save_state(state)
    cron_add()

    print("\n[init] Running first todo immediately...\n")
    mode_worker()


def mode_worker():
    """Mutex-protected worker — safe to call from cron every minute."""
    lock = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[worker] already running — skipping this cron tick")
        lock.close()
        return

    try:
        state = load_state()

        if not state:
            print("[worker] No state file found. Run --mode init first.")
            return

        pending = [t for t in state["todos"] if t["status"] == "PENDING"]

        if not pending:
            print("[worker] All todos complete!")
            cron_remove()
            _write_summary(state)
            return

        todo = pending[0]
        print(f"\n[worker] Working on: '{todo['task']}'")

        completed_context = "\n".join(
            f"- {t['task']}: {t['result']}"
            for t in state["todos"]
            if t["status"] == "DONE"
        ) or "None yet."

        result_resp = ask(
            system="You are an AI agent executing tasks. Be concise. Output JSON only.",
            user=(
                f"Overall goal: {state['goal']}\n"
                f"Work completed so far:\n{completed_context}\n\n"
                f"Your current task: {todo['task']}\n"
                f"Do this task. Provide a short result/output."
            ),
            schema={
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                    "notes":  {"type": "string"},
                },
                "required": ["result"],
            },
        )

        todo["status"] = "DONE"
        todo["result"] = result_resp["result"]
        state["log"].append({
            "time":   datetime.now().isoformat(),
            "todo":   todo["task"],
            "result": result_resp["result"],
        })
        save_state(state)

        remaining = len([t for t in state["todos"] if t["status"] == "PENDING"])
        print(f"[worker] ✓ Done. {remaining} todo(s) remaining.")

        if remaining == 0:
            print("[worker] All done! Removing cron...")
            cron_remove()
            _write_summary(state)

    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def mode_chat(message: str):
    state = load_state()
    if not state:
        print("No active task. Start one with --mode init --task '...'")
        return

    todos_summary = "\n".join(
        f"  [{t['status']}] {t['task']}"
        for t in state["todos"]
    )

    resp = ask(
        system=(
            "You are an AI agent mid-task. Answer the user's question based on "
            "your current state. Be concise and conversational. Output JSON only."
        ),
        user=(
            f"My current goal: {state['goal']}\n"
            f"My todos:\n{todos_summary}\n\n"
            f"User asks: {message}"
        ),
        schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    )
    print(f"\nAgent: {resp['answer']}\n")


def mode_status():
    state = load_state()
    if not state:
        print("No state file found.")
        return

    done = [t for t in state["todos"] if t["status"] == "DONE"]
    print(f"\n{'─'*50}")
    print(f"  Goal    : {state.get('goal')}")
    print(f"  Started : {state.get('started_at')}")
    print(f"  Progress: {len(done)}/{len(state['todos'])} todos done")
    print(f"{'─'*50}")
    for t in state.get("todos", []):
        mark = "✓" if t["status"] == "DONE" else "○"
        print(f"  {mark}  {t['task']}")
        if t["result"]:
            print(f"       → {t['result'][:100]}...")
    print(f"{'─'*50}\n")


def _write_summary(state: dict):
    summary = {
        "goal":            state["goal"],
        "completed_todos": [t["task"] for t in state["todos"]],
        "log":             state["log"],
        "finished_at":     datetime.now().isoformat(),
    }
    out = Path("data/summary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(f"[agent] Summary written to {out}")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["init", "worker", "chat", "status"], required=True)
    parser.add_argument("--task", help="Initial task  (--mode init)")
    parser.add_argument("--msg",  help="Chat message  (--mode chat)")
    args = parser.parse_args()

    if args.mode == "init":
        assert args.task, "Provide --task with --mode init"
        mode_init(args.task)

    elif args.mode == "worker":
        mode_worker()

    elif args.mode == "chat":
        assert args.msg, "Provide --msg with --mode chat"
        mode_chat(args.msg)

    elif args.mode == "status":
        mode_status()
        