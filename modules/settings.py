import os
from pathlib import Path
# config.py — edit this before running anything
from shimsalabim import ShimSalaBim
from dotenv import load_dotenv,find_dotenv
load_dotenv(find_dotenv())
BASE_DIR = Path(__file__).parent

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


# I shim in the llama-cpp from the root system  into the venv this schript runs in(only way to have it use GPU)
global_packages_folder = '/home/codemonkeyxl/.local/lib/python3.10/site-packages'

global_pkgs = [
    ('llama_cpp', global_packages_folder),
    ('torch', global_packages_folder),
    ('torchvision', global_packages_folder),
    ('langchain', global_packages_folder),
    ('langchain_community', global_packages_folder),
    ('accelerate', global_packages_folder),
    ('safetensors', global_packages_folder),
    ('gguf', global_packages_folder),
]


# Specify which classes you want to monitor usage for
classes_to_monitor = {
    'llama_cpp': ['Llama'],
    'torch': ['nn.Module'],
    'torchvision': ['transforms.Compose'],
    'langchain_huggingface': ['transformers.pipeline'], 
    'langchain_community': ['embeddings.HuggingFaceEmbeddings'],
    'accelerate': ['AcceleratorState'],
    'safetensors': ['safetensors.torch.SFT', 'safetensors.torch.SFT.from_pretrained'],
    'gguf': ['gguf.GGUF'],
}

shim = ShimSalaBim(global_pkgs, classes_to_wrap={})

Llama = shim.llama_cpp.Llama
torch = shim.torch
torchvision = shim.torchvision
langchain_huggingface = shim.langchain_huggingface
langchain_community = shim.langchain_community
accelerate = shim.accelerate
safetensors = shim.safetensors
gguf = shim.gguf

if not Llama:
    from llama_cpp import Llama

# Llama shim
LLAMA_CPP = Llama

# ── LLM ───────────────────────────────────────────────────────────────────────
DEFAULT_LLM_MODEL_PATH = os.getenv(
    "LLM_MODEL_PATH_BIG",
    "/media/codemonkeyxl/B500/coding_folder/visual_chatbot/backend/Another_electron/backend/models/DarkIdol_Llama_3_1_8B_Instruct_1_2_Uncensored_Q6_K.gguf",
)
DEFAULT_CTX         = 4096
DEFAULT_GPU_LAYERS  = 16
MAX_HISTORY_TURNS   = 8
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS  = 512

# ── Paths ─────────────────────────────────────────────────────────────────────
STOCK_FILE   = BASE_DIR / "data" / "stock.json"
ORDERS_DIR   = BASE_DIR / "orders"
ORDERS_LOG   = BASE_DIR / "orders" / "orders_log.jsonl"

ORDERS_DIR.mkdir(parents=True, exist_ok=True)

# ── Business rules ────────────────────────────────────────────────────────────
MAX_QTY_PER_ITEM  = 50
MAX_CART_ITEMS    = 10
MIN_ORDER_TOTAL   = 0.01

# ── Payment (stub — replace with real provider) ───────────────────────────────
PAYMENT_BASE_URL  = os.getenv("PAYMENT_BASE_URL", "https://pay.yourshop.com")
