import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QDRANT_PATH = os.path.join(BASE_DIR, "local_qdrant")
STORE_PATH = os.path.join(BASE_DIR, "parent_store")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
STATE_FILE = os.path.join(DOCS_DIR, "file_state.json")

os.makedirs(QDRANT_PATH, exist_ok=True)
os.makedirs(STORE_PATH, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
