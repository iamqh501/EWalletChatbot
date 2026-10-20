import os
import sys
from dotenv import load_dotenv
from backend.core.config import BASE_DIR

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Đường dẫn tới thư mục gốc của dự án và file .env
ENV_FILE = os.path.join(BASE_DIR, ".env")


def sync_windows_registry_env():
    """Đồng bộ biến môi trường từ Windows Registry (HKCU/HKLM) nếu chưa có trong os.environ."""
    if os.name != "nt":
        return
    try:
        import winreg
        targets = [
            (winreg.HKEY_CURRENT_USER, r"Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        ]
        for hive, subkey in targets:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    count = winreg.QueryInfoKey(key)[1]
                    for i in range(count):
                        name, val, _ = winreg.EnumValue(key, i)
                        if name not in os.environ and isinstance(val, str):
                            os.environ[name] = val
            except Exception:
                pass
    except Exception:
        pass


def load_environment():
    """Nạp file .env và đồng bộ các biến môi trường hệ thống/người dùng."""
    if os.path.exists(ENV_FILE):
        load_dotenv(dotenv_path=ENV_FILE, override=False)
    else:
        load_dotenv(override=False)

    sync_windows_registry_env()

    # Đồng bộ chéo giữa HF_API_KEY và HF_TOKEN
    if "HF_API_KEY" in os.environ and "HF_TOKEN" not in os.environ:
        os.environ["HF_TOKEN"] = os.environ["HF_API_KEY"]
    elif "HF_TOKEN" in os.environ and "HF_API_KEY" not in os.environ:
        os.environ["HF_API_KEY"] = os.environ["HF_TOKEN"]


# Tự động thực thi khi module được nạp
load_environment()
