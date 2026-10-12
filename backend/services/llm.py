import warnings
from langchain_deepseek import ChatDeepSeek
import subprocess
import socket
import time
import atexit
from pathlib import Path
import urllib.request
import json

warnings.filterwarnings('ignore')

config_path = Path(__file__).resolve().parents[2] / "local_paths.json"
try:
    with open(config_path, "r", encoding="utf-8") as f:
        PATHS_CONFIG = json.load(f)
except FileNotFoundError:
    PATHS_CONFIG = {}

class LlamaServerManager:
    _process = None
    _current_model_path = None

    @classmethod
    def start_server_if_needed(cls, model_path, port=8080):
        if cls.is_port_in_use(port):
            if cls._current_model_path and cls._current_model_path != model_path:
                cls.stop_server()
                for _ in range(10):
                    if not cls.is_port_in_use(port):
                        break
                    time.sleep(1)

        if not cls.is_port_in_use(port):
            cmd = [
                PATHS_CONFIG.get("LLAMA_SERVER_PATH", "llama-server"),
                "-m", model_path,
                "--port", str(port),
                "-n", "8192",
                "-c", "16384"
            ]
            
            cls._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            cls._current_model_path = model_path
            atexit.register(cls.stop_server)
            
        for _ in range(300):
            if cls.is_port_in_use(port):
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
                    with urllib.request.urlopen(req, timeout=1) as response:
                        if response.getcode() == 200:
                            return
                except Exception:
                    pass
            time.sleep(0.5)

    @classmethod
    def is_port_in_use(cls, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    @classmethod
    def stop_server(cls):
        if cls._process:
            cls._process.terminate()
            cls._process.wait()
            cls._process = None
            cls._current_model_path = None

def get_llama_cpp_model(temperature=0.1, **kwargs):
    model_path = PATHS_CONFIG.get("MODEL_PATH", "")
    if not model_path:
        raise ValueError("MODEL_PATH is not configured in local_paths.json")
    model_name = PATHS_CONFIG.get("MODEL_NAME", "gemma-4-E2B-it-qat-GGUF")

    LlamaServerManager.start_server_if_needed(model_path=model_path, port=8080)

    global _warmed_up_models
    if '_warmed_up_models' not in globals():
        _warmed_up_models = set()

    if model_name not in _warmed_up_models:
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/health")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.getcode() == 200:
                    warmup_data = {
                        "model": model_name, 
                        "messages": [{"role": "user", "content": "hi"}], 
                        "max_tokens": 1, 
                        "stream": False
                    }
                    warmup_req = urllib.request.Request(
                        "http://127.0.0.1:8080/v1/chat/completions", 
                        data=json.dumps(warmup_data).encode('utf-8'), 
                        headers={'Content-Type': 'application/json'}
                    )
                    urllib.request.urlopen(warmup_req, timeout=5).read()
                    _warmed_up_models.add(model_name)
        except Exception:
            pass

    max_tokens = kwargs.get("num_predict", 8192)
    if "num_predict" in kwargs:
        del kwargs["num_predict"]

    return ChatDeepSeek(
        api_base="http://127.0.0.1:8080/v1",
        api_key="sk-no-key-required",
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        model_kwargs={
            "stream_options": {"include_usage": True},
        },
        **kwargs,
    )
