<p align="center">
  <img src="workspace/claight.png" alt="CLAIGHT — Brother of CLAWD" width="480"/>
</p>

<h1 align="center">CLAIGHT — Brother of CLAWD</h1>

<p align="center">
  <em>A self-scheduling autonomous local LLM agent.<br>
  Runs on your GPU. Plans its own work. Schedules its own heartbeat. Never phones home.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.001-ff6b6b?style=for-the-badge" alt="version 0.001"/>
  <img src="https://img.shields.io/badge/status-Work%20In%20Progress-ffaa00?style=for-the-badge" alt="WIP"/>
  <img src="https://img.shields.io/badge/runs%20on-your%20GPU-00cc88?style=for-the-badge" alt="local"/>
</p>

> ⚠️ **v0.001 — Work In Progress.** The loop works. The soul files load. The cron heartbeat beats. The structured output holds. But this is the skeleton — expect rough edges, missing features, and the occasional existential crisis in `/tmp/agent_cron.log`. Contributions welcome.

---

## Why

Every LLM agent framework out there hands you a cloud endpoint, an API key, and a bill at the end of the month. CLAIGHT is the other option.

It runs on **your hardware**, using a **local GGUF model** via llama-cpp. No OpenAI. No Anthropic. No data leaving your machine. You give it a task, it makes a plan, schedules itself via cron, and works through that plan one todo at a time — waking up, thinking, writing results to disk, and going back to sleep until the next tick.

The core insight: **the LLM is just the cortex**. The cron loop is the heartbeat. The state file is the memory. The workspace files are the soul. The whole organism only exists because all the parts run together.

---

## How It Works

```
You: python agent.py --mode init --task "your task"
         │
         ▼
    LLM CALL #1 → make a plan
    LLM CALL #2 → break plan into todos
    → saves to data/state.json
    → writes itself into crontab
    → runs first todo immediately
         │
         ▼
    ════ CRON FIRES every N minutes ════
         │
         ▼
    agent.py --mode worker
    → reads state.json          (memory)
    → reads workspace/SOUL.md   (identity)
    → reads workspace/USER.md   (context)
    → finds first PENDING todo
    → LLM infers with full context
    → marks todo DONE, saves result
    → if all done: removes cron, writes summary
         │
         ▼
    ════ repeat until finished ════
```

Meanwhile, at any time:

```bash
python agent.py --mode chat --msg "what are you working on?"
python agent.py --mode status
```

---

## Key Design Patterns

### Key-Bound Structured JSON
Every LLM call uses `response_format` JSON schema enforcement **plus** the schema is rendered as plain text and appended to the system prompt via `dict_to_str()`. The model reads field descriptions as **per-field micro-prompts** before generating — double-binding the output contract at two levels simultaneously.

```python
"result": {
    "type": "string",
    "description": (
        "Concrete deliverable. If code task: write actual code. "
        "If research: list real findings. NEVER just say 'done'. "
        f"(max {result_budget} tokens)"
    )
}
```

### Token Budget Per Field
Dividing `max_tokens` across schema string fields and embedding the per-field budget in each description prevents the model from spending the entire token budget on early fields and arriving at later ones with nothing left. Every field gets its allocation. No silent truncation.

### ShimSalaBim — The CUDA Bridge
llama-cpp with CUDA must be installed into the root system Python to access GPU drivers. Running it inside a venv normally means CPU-only inference. `ShimSalaBim` injects the root system's llama-cpp directly into the venv at runtime — giving you full GPU acceleration without polluting your project environment.

### Mutex Lock
Cron fires every N minutes. Model inference takes ~60 seconds. Without a lock, multiple instances spawn, fight over the GPU, and corrupt `state.json`. `fcntl.flock` ensures only one worker runs at a time — subsequent cron ticks skip cleanly.

### Workspace Soul Files
The agent has a persistent identity that loads on every cron wake:

```
workspace/
  SOUL.md     ← who it is, how it behaves
  USER.md     ← who it's helping, their context
  AGENTS.md   ← capabilities and rules
  TOOLS.md    ← local specifics
  memory/     ← daily logs, YYYY-MM-DD.md
```

These files are injected into every system prompt. The LLM has no memory between calls — the files **are** the memory.

---

## Requirements

- Linux
- Python 3.10
- llama-cpp-python installed **with CUDA** in root/user Python:
  ```bash
  CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python --force-reinstall
  ```
- A GGUF model (tested on `DarkIdol_Llama_3_1_8B_Instruct_1_2_Uncensored_Q6_K.gguf`)
- `rich` (`pip install rich`)

---

## Quickstart

**1. Clone and configure:**
```bash
git clone https://github.com/codemonkeyxl/Claight.git
cd Claight
```

Edit `config.py`:
```python
LLM_MODEL_PATH    = "/path/to/your-model.gguf"
AGENT_SCRIPT_PATH = "/full/absolute/path/to/agent.py"  # cron needs absolute
STATE_FILE        = "/full/absolute/path/to/data/state.json"
LLM_GPU_LAYERS    = 32   # or -1 for all layers
LLM_N_CTX         = 8192
CRON_INTERVAL_MINUTES = 3
```

**2. Fill your soul files:**
```bash
nano workspace/SOUL.md   # who the agent is
nano workspace/USER.md   # who it's helping (you)
```

**3. Give it a task:**
```bash
python agent.py --mode init --task "research and write a Python file watcher script"
```

**4. Watch it work:**
```bash
# live cron log
tail -f /tmp/agent_cron.log

# check progress
python agent.py --mode status

# talk to it
python agent.py --mode chat --msg "what have you done so far?"
```

**5. When done**, find your summary at `data/summary.json`.

---

## Project Structure

```
Claight/
├── agent.py              ← the organism
├── config.py             ← model path, cron interval, GPU layers
├── modules/
│   └── shimsalabim.py    ← CUDA bridge (the secret sauce)
├── workspace/
│   ├── SOUL.md           ← agent identity
│   ├── USER.md           ← user context  [gitignored]
│   ├── AGENTS.md         ← behavioral rules
│   ├── TOOLS.md          ← local specifics  [gitignored]
│   └── memory/           ← daily logs  [gitignored]
├── data/                 ← state.json, summary.json  [gitignored]
├── requirements.txt
└── .gitignore
```

---

## Modes

| Command | What it does |
|---|---|
| `--mode init --task "..."` | Start a new task — plan, todos, cron, first worker |
| `--mode worker` | Process next pending todo (called by cron automatically) |
| `--mode chat --msg "..."` | Ask the agent about its current state |
| `--mode status` | Pretty-print progress |

---

## Tested On

- Ubuntu 22.04 / 24.04
- RTX 3060 12GB / RTX 4090
- Python 3.10
- DarkIdol Llama 3.1 8B Instruct Q6_K (recommended — excellent structured output compliance)

---

<p align="center">
  <em>The intelligence was always in the weights.<br>
  It just needed a body.</em>
</p>
