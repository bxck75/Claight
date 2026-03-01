# Claight 🤖

> A self-scheduling autonomous local LLM agent with cron heartbeat, persistent identity, and key-bound structured JSON output.

Born on an **RTX 4070 SUPER** running **DarkIdol Llama 3.1 8B Instruct Q6_K** — a local model that proved itself flawless on 3-deep nested schemas with 30+ fields. No cloud. No API keys. No subscriptions. Just a GPU, a GGUF, and a cron job.

---

## What It Does

You give it one task. It plans, breaks it into todos, schedules itself via cron, works through each todo one inference at a time, and puts itself to sleep when done. While it works you can ask it what it's doing.

```
you:     python agent.py --mode init --task "build me a file read/write tool"
         ↓
agent:   makes a plan
         breaks plan into 3-5 todos
         saves state.json
         adds itself to crontab
         runs first todo immediately
         ↓
cron:    fires every N minutes
         picks next PENDING todo
         infers
         saves result
         sleeps
         ↓
agent:   all done → removes itself from crontab → writes summary
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  agent.py                                   │
│                                             │
│  mode_init    → plan + todos + cron_add     │
│  mode_worker  → mutex → infer → save state  │
│  mode_chat    → state as context → answer   │
│  mode_status  → pretty print state          │
└─────────────────────────────────────────────┘
        ↕                      ↕
┌──────────────┐      ┌─────────────────────┐
│  state.json  │      │  workspace/         │
│  (memory)    │      │  SOUL.md            │
│              │      │  USER.md            │
│  goal        │      │  AGENTS.md          │
│  plan        │      │  TOOLS.md           │
│  todos[]     │      │  memory/YYYY-MM-DD  │
│  log[]       │      │  (persistent        │
└──────────────┘      │   identity)         │
                      └─────────────────────┘
        ↕
┌─────────────────────────────────────────────┐
│  crontab                                    │
│  */3 * * * * python agent.py --mode worker  │
│  (added by agent, removed when done)        │
└─────────────────────────────────────────────┘
```

The LLM has no memory between calls. `state.json` is the memory. `workspace/` is the identity. The cron is the heartbeat. Together they make something that behaves like it's continuous — because the files are.

---

## Key Design Patterns

### 1. Key-Bound Structured JSON

Every schema field carries a `description` that becomes a **per-field micro-prompt**. The schema is appended to the system prompt via `dict_to_str()` — so the model reads the output contract as plain-text instructions before generating the first token.

```python
"result": {
    "type": "string",
    "description": (
        "Concrete deliverable. If code task: write actual code. "
        "If research: list real findings. "
        "NEVER reply with just 'done' or 'success'. "
        f"(max {budget} tokens)"
    )
}
```

Two enforcement layers on every field:
- `response_format` enforces the **shape**
- `description` in system prompt enforces the **content intent**

### 2. Token Budget Per Field

Tail fields in a schema are always at risk of truncation — the model spends tokens on early fields and arrives at the last ones empty. The fix: append `(max N tokens)` to each field description. The model self-caps early fields to protect the tail.

```python
result_budget = int(MAX_TOKENS * 0.70)  # result gets 70%
notes_budget  = int(MAX_TOKENS * 0.30)  # notes gets 30%
```

### 3. ShimSalaBim — The CUDA Venv Bridge

`llama-cpp-python` with CUDA must be installed into the **root system Python** to access the GPU drivers. But the project runs in a **venv**. ShimSalaBim injects the root-installed package into the venv at runtime — the only reliable way to get GPU inference inside a venv without reinstalling everything.

```python
shim = ShimSalaBim(global_pkgs, classes_to_wrap={})
Llama = shim.llama_cpp.Llama
```

### 4. Mutex-Protected Cron Worker

Inference takes ~60 seconds. Cron fires every minute. Without a lock, multiple instances pile up and fight over the GPU and state.json simultaneously. `fcntl.flock` ensures only one worker runs at a time — concurrent cron ticks skip cleanly.

```python
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
# BlockingIOError → already running → skip this tick
```

---

## Model

**DarkIdol Llama 3.1 8B Instruct 1.2 Uncensored Q6_K**  
6GB VRAM · 131k context · chatml format · flawless structured output

```
https://huggingface.co/bartowski/DarkIdol-Llama-3.1-8B-Instruct-1.2-Uncensored-GGUF
```

Direct download:
```bash
wget "https://huggingface.co/bartowski/DarkIdol-Llama-3.1-8B-Instruct-1.2-Uncensored-GGUF/resolve/main/DarkIdol-Llama-3.1-8B-Instruct-1.2-Uncensored-Q6_K.gguf?download=true" \
     -O DarkIdol-Llama-3.1-8B-Instruct-1.2-Uncensored-Q6_K.gguf
```

This model was chosen after a year of production use on procedural multi-step tasks. It handles 1200+ token system prompts, 3-deep nested schemas with 30+ fields, and never hallucinates structure. An uncensored base model is an advantage for agent tasks — it just does the task without hedging mid-JSON.

---

## Requirements

- Linux
- Python 3.10
- NVIDIA GPU with CUDA
- `llama-cpp-python` installed to root system with CUDA:

```bash
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python --force-reinstall
```

---

## Setup

```bash
# 1. clone
git clone https://github.com/bxck75/Claight.git
cd Claight

# 2. create venv
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. edit config.py
#    set LLM_MODEL_PATH to your .gguf file
#    set AGENT_SCRIPT_PATH to absolute path of agent.py
#    set STATE_FILE to absolute path of data/state.json

# 4. fill in workspace/SOUL.md and workspace/USER.md

# 5. run
python agent.py --mode init --task "your task here"
```

---

## Usage

```bash
# give it a task — starts the whole loop
python agent.py --mode init --task "research and write a Python file watcher script"

# check progress
python agent.py --mode status

# talk to it while it works
python agent.py --mode chat --msg "what have you done so far?"

# manually trigger a worker cycle
python agent.py --mode worker

# watch cron log live
tail -f /tmp/agent_cron.log
```

---

## Workspace Files

```
workspace/
├── SOUL.md       ← who the agent is, how it behaves
├── USER.md       ← who it's helping (gitignored)
├── AGENTS.md     ← capabilities and rules
├── TOOLS.md      ← local specifics (gitignored)
├── IDENTITY.md   ← name, vibe, emoji (gitignored)
└── memory/       ← daily logs YYYY-MM-DD.md (gitignored)
```

Loaded into every system prompt on every cron wake. The agent is never amnesiac — it knows who it is and who it serves on every inference call.

---

## License

MIT — do what you want with it.

---

*Built on a Tuesday morning while deriving transfusers from first principles.*