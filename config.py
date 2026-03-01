

# ── Model ─────────────────────────────────────────────────────────────────────

LLM_MODEL_PATH = (
    #"/media/codemonkeyxl/B500/coding_folder/visual_chatbot/backend/160_poses_grab/dollhouse_project/models/DarkIdol_Llama_3_1_8B_Instruct_1_2_Uncensored_Q6_K.gguf"
    '/home/codemonkeyxl/new_coding_folder/DarkIdol_Llama_3_1_8B_Instruct_1_2_Uncensored_Q6_K.gguf'

)

# Context window — 8B Llama 3.1 supports up to 131072 but VRAM is the real limit.
# 8192 is a safe default; push to 16384 if you have the VRAM headroom.
LLM_N_CTX = 8192

# GPU offload layers.
# -1  = offload ALL layers (fastest, needs full VRAM)
#  0  = CPU only
#  N  = offload N layers, rest on CPU (tune for your GPU)
LLM_GPU_LAYERS = -1

# ── Generation ────────────────────────────────────────────────────────────────

LLM_TEMPERATURE = 0.75   # 0.7–0.9 sweet spot for creative/roleplay
LLM_MAX_TOKENS  = 1024   # per response — enough for rich structured output

# How often cron fires the worker (minutes)
CRON_INTERVAL_MINUTES = 1

# Script location (must be absolute path for cron to find it)
AGENT_SCRIPT_PATH = "/media/codemonkeyxl/TBofCode/cron_llama/agent.py"   # <-- change this

# Where state is stored between cron wakes
STATE_FILE = "data/state.json"        # <-- change this (or leave relative)
