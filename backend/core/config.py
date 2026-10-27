import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Persistent storage directories
QDRANT_PATH = os.path.join(BASE_DIR, "local_qdrant")
STORE_PATH = os.path.join(BASE_DIR, "parent_store")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

# Qdrant collection name
COLLECTION_NAME = "knowledge"

# Knowledge categories
CATEGORIES = ("knowledge", "faq", "telecom", "navigation")

# Categorized subdirectories
KNOWLEDGE_DIR = os.path.join(DOCS_DIR, "knowledge")
FAQ_DIR = os.path.join(DOCS_DIR, "faq")
TELECOM_DIR = os.path.join(DOCS_DIR, "telecom")
NAVIGATION_DIR = os.path.join(DOCS_DIR, "navigation")

# State & metadata tracking
ENV_FILE = os.path.join(BASE_DIR, ".env")
STATE_FILE = os.path.join(DOCS_DIR, "file_state.json")

# Specific domain knowledge files
TELECOM_PACKAGES_FILE = os.path.join(TELECOM_DIR, "goi_cuoc.json")
TELECOM_EXCEL_FILE = os.path.join(TELECOM_DIR, "goi_cuoc.xlsx")
NAVIGATION_MAP_FILE = os.path.join(NAVIGATION_DIR, "navigation_map.json")
APP_GUIDE_FILE = os.path.join(NAVIGATION_DIR, "cach_dung_app.md")
APP_GUIDE_REL_PATHS = [
    "navigation/cach_dung_app.md",
    "navigation\\cach_dung_app.md"
]
FAQ_EXCEL_FILE = os.path.join(FAQ_DIR, "qa.xlsx")

# Default model identifiers & endpoints
DEFAULT_HF_LLM_MODEL = "inclusionAI/Ling-3.0-flash:fastest"
DEFAULT_HF_VLM_MODEL = "inclusionAI/Ling-3.0-flash-VL:fastest"
DEFAULT_EMBEDDING_MODEL = "google/embeddinggemma-300m"
DEFAULT_SPARSE_MODEL = "Qdrant/bm25"
DEFAULT_RERANKER_MODEL = "jev-latest"
HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"

# Default networking
DEFAULT_HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 8000

# Create directories if not existing
for _dir_path in [QDRANT_PATH, STORE_PATH, DOCS_DIR, KNOWLEDGE_DIR, FAQ_DIR, TELECOM_DIR, NAVIGATION_DIR]:
    os.makedirs(_dir_path, exist_ok=True)
