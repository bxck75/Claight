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
#  TELEGRAM — optional notifier
#  Add TELEGRAM_TOKEN + TELEGRAM_CHAT_ID to config.py to enable
# ─────────────────────────────────────────────

try:
    from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
    from modules.telegram_connector import create_telegram_connector
    telegram = create_telegram_connector(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    print("[telegram] notifications enabled")
except (ImportError, Exception) as e:
    telegram = None
    print(f"[telegram] disabled ({e})")


# ─────────────────────────────────────────────
#  SHIM — GPU-enabled llama_cpp from root system
#  Required: llama-cpp needs CUDA from root install
#  ShimSalaBim injects it into the venv at runtime
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


# ─────────────────────────────────────────────
#  SCHEMA UTILS
#  dict_to_str: appended to system prompt so the
#  model reads field descriptions as live instructions
#  before generating — double-binding the output contract
# ─────────────────────────────────────────────

def dict_to_str(schema: dict, indent: int = 0) -> str:
    """
    Recursively convert a JSON schema to a human-readable
    string that the LLM can read as instructions.
    Appended to every system prompt so descriptions
    become per-field micro-prompts.
    """
    lines = []
    pad   = "  " * indent
    props = schema.get("properties", {})
    for key, val in props.items():
        field_type = val.get("type", "any")
        desc       = val.get("description", "")
        required   = key in schema.get("required", [])
        req_marker = " [required]" if required else " [optional]"
        lines.append(f"{pad}{key} ({field_type}){req_marker}: {desc}")
        if "properties" in val:
            lines.append(dict_to_str(val, indent + 1))
        if field_type == "array" and "items" in val:
            item_desc = val["items"].get("description", "")
            if item_desc:
                lines.append(f"{pad}  items: {item_desc}")
    return "\n".join(lines)


def n_str_fields(schema: dict) -> int:
    """Count string-type fields in schema for token budget division."""
    count = 0
    for val in schema.get("properties", {}).values():
        if val.get("type") == "string":
            count += 1
        if "properties" in val:
            count += n_str_fields(val)
    return max(count, 1)


def make_budget(max_tokens: int, schema: dict, weight: float = 1.0) -> int:
    """Per-field token budget: total × weight ÷ n_string_fields."""
    return int((max_tokens * weight) // n_str_fields(schema))


# ─────────────────────────────────────────────
#  LLM CALL
# ─────────────────────────────────────────────

MAX_TOKENS = 1024

def ask(system: str, user: str, schema: dict) -> dict:
    """
    Single LLM call.
    - Schema appended to system prompt as plain text (dict_to_str)
      so field descriptions become live instructions before inference.
    - response_format enforces JSON shape as second layer.
    - finish_reason checked to catch max_token truncation.
    """
    full_system = system + "\n\nExpected output structure:\n" + dict_to_str(schema)

    result = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user",   "content": user},
        ],
        response_format={"type": "json_object", "schema": schema},
        temperature=0.7,
        max_tokens=MAX_TOKENS,
    )

    choice        = result["choices"][0]
    finish_reason = choice.get("finish_reason")
    raw           = choice["message"]["content"]

    if finish_reason == "length":
        raise RuntimeError(
            f"[ask] truncated — hit max_tokens ({MAX_TOKENS}). "
            "Raise MAX_TOKENS or tighten field descriptions."
        )

    return json.loads(raw)


# ─────────────────────────────────────────────
#  STATE  — agent's memory between cron wakes
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
#  CRON  — heartbeat: add / remove from crontab
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
#  SCHEMAS
#  Descriptions are per-field micro-prompts.
#  Token budgets prevent tail-field truncation.
# ─────────────────────────────────────────────

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "plan_summary": {
            "type": "string",
            "description": (
                "A numbered step-by-step plan. Each step is one short sentence. "
                "Be specific and actionable. No preamble, no padding. "
                f"(max {MAX_TOKENS} tokens)"
            ),
        }
    },
    "required": ["plan_summary"],
}

TODOS_SCHEMA = {
    "type": "object",
    "properties": {
        "todos": {
            "type": "array",
            "description": "Exactly 3-5 todos. Ordered by dependency. No duplicates.",
            "items": {
                "type": "string",
                "description": "One actionable todo. Verb-first. Max 8 words.",
            },
        }
    },
    "required": ["todos"],
}

def worker_schema() -> dict:
    """
    Result schema for mode_worker.
    Budget split: result gets 70%, notes gets 30%.
    Descriptions are commands — model reads them before generating.
    """
    result_budget = int(MAX_TOKENS * 0.70)
    notes_budget  = int(MAX_TOKENS * 0.30)
    return {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": (
                    "Concrete deliverable output of this specific task. "
                    "If research task: list actual findings, names, methods discovered. "
                    "If code task: write the actual working code. "
                    "If design task: list components, structure, decisions made. "
                    "If implementation task: describe exactly what was created and where. "
                    "NEVER restate the task name. "
                    "NEVER reply with only 'done', 'success', or 'completed'. "
                    f"(max {result_budget} tokens)"
                ),
            },
            "notes": {
                "type": "string",
                "description": (
                    "Anything the next task needs to know. "
                    "Blockers, assumptions, or dependencies discovered. "
                    "Empty string if nothing relevant. "
                    f"(max {notes_budget} tokens)"
                ),
            },
        },
        "required": ["result"],
    }

CHAT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": (
                "Direct conversational answer to the user's question. "
                "Based only on current state. "
                f"(max {MAX_TOKENS} tokens)"
            ),
        }
    },
    "required": ["answer"],
}


# ─────────────────────────────────────────────
#  MODES
# ─────────────────────────────────────────────

def mode_init(task: str):
    """
    Called once by you.
    1. LLM makes a plan
    2. LLM breaks plan into todos
    3. Save state
    4. Add cron heartbeat
    5. Run first todo immediately
    """
    print(f"\n[init] Goal: {task}")

    # ── Step 1: Plan ──────────────────────────────
    plan_resp = ask(
        system="You are a project planner. Output JSON only.",
        user=f"Write a concise step-by-step plan for this task: {task}",
        schema=PLAN_SCHEMA,
    )
    plan_text = plan_resp["plan_summary"]
    print(f"[init] Plan:\n{plan_text}\n")

    # ── Step 2: Todos ─────────────────────────────
    todos_resp = ask(
        system="You are a project planner. Output JSON only.",
        user=(
            f"Break this plan into 3-5 concrete, actionable todos.\n"
            f"Plan: {plan_text}"
        ),
        schema=TODOS_SCHEMA,
    )
    todos = [
        {"id": i, "task": t, "status": "PENDING", "result": None}
        for i, t in enumerate(todos_resp["todos"])
    ]
    print(f"[init] Todos:")
    for t in todos:
        print(f"  ○  {t['task']}")

    # ── Step 3: Save state ────────────────────────
    state = {
        "goal":       task,
        "plan":       plan_text,
        "todos":      todos,
        "started_at": datetime.now().isoformat(),
        "log":        [],
    }
    save_state(state)

    # ── Step 4: Schedule cron heartbeat ───────────
    cron_add()

    # ── Step 5: Do first todo now ─────────────────
    print("\n[init] Running first todo immediately...\n")
    mode_worker()


def mode_worker():
    """
    Called by cron every N minutes.
    Mutex-protected — concurrent cron instances skip safely.
    Picks next PENDING todo → infers → saves result.
    When all done: removes cron, writes summary.
    """
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
            if telegram:
                telegram.notify_all_done(state["goal"])
            _write_summary(state)
            return

        todo = pending[0]
        print(f"\n[worker] Working on: '{todo['task']}'")

        # ── Telegram: task started ─────────────────
        if telegram:
            telegram.notify_worker_start(todo["task"])

        # Full context from completed work — this is the agent's memory
        completed_context = "\n".join(
            f"- {t['task']}: {t['result']}"
            for t in state["todos"]
            if t["status"] == "DONE"
        ) or "None yet."

        schema = worker_schema()

        result_resp = ask(
            system=(
                "You are an AI agent executing tasks one at a time. "
                "Be specific and concrete. Output JSON only."
            ),
            user=(
                f"Overall goal: {state['goal']}\n"
                f"Work completed so far:\n{completed_context}\n\n"
                f"Your current task: {todo['task']}\n\n"
                f"Execute this task fully. Produce a real, concrete result."
            ),
            schema=schema,
        )

        # Update state
        todo["status"] = "DONE"
        todo["result"] = result_resp["result"]
        state["log"].append({
            "time":   datetime.now().isoformat(),
            "todo":   todo["task"],
            "result": result_resp["result"],
            "notes":  result_resp.get("notes", ""),
        })
        save_state(state)

        remaining = len([t for t in state["todos"] if t["status"] == "PENDING"])
        print(f"[worker] ✓ Done. Result: {result_resp['result'][:120]}")
        print(f"[worker]   {remaining} todo(s) remaining.")

        # ── Telegram: todo done ────────────────────
        if telegram:
            telegram.notify_todo_done(todo["task"], result_resp["result"], remaining)

        if remaining == 0:
            print("[worker] All done! Removing cron...")
            cron_remove()
            if telegram:
                telegram.notify_all_done(state["goal"])
            _write_summary(state)

    except Exception as e:
        print(f"[worker] ERROR: {e}")
        if telegram:
            telegram.notify_error(str(e))
        raise

    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def mode_chat(message: str):
    """
    Talk to the agent while it works.
    State file is the entire memory — LLM has no other context.
    """
    state = load_state()
    if not state:
        print("No active task. Start one with --mode init --task '...'")
        return

    todos_summary = "\n".join(
        f"  [{t['status']}] {t['task']}"
        + (f"\n    → {t['result'][:80]}" if t.get("result") else "")
        for t in state["todos"]
    )

    resp = ask(
        system=(
            "You are an AI agent mid-task. "
            "Answer the user's question based on your current state. "
            "Be concise and conversational. Output JSON only."
        ),
        user=(
            f"My current goal: {state['goal']}\n"
            f"My todos:\n{todos_summary}\n\n"
            f"User asks: {message}"
        ),
        schema=CHAT_SCHEMA,
    )
    print(f"\nAgent: {resp['answer']}\n")


def mode_status():
    """Pretty-print current state."""
    state = load_state()
    if not state:
        print("No state file found.")
        return

    done = [t for t in state["todos"] if t["status"] == "DONE"]
    print(f"\n{'─'*55}")
    print(f"  Goal    : {state.get('goal')}")
    print(f"  Started : {state.get('started_at')}")
    print(f"  Progress: {len(done)}/{len(state['todos'])} todos done")
    print(f"{'─'*55}")
    for t in state.get("todos", []):
        mark = "✓" if t["status"] == "DONE" else "○"
        print(f"  {mark}  {t['task']}")
        if t.get("result"):
            print(f"       → {t['result'][:100]}...")
    print(f"{'─'*55}\n")


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

        