import os
import sys
import logging
import backend.core.env
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import DEFAULT_HOST, DEFAULT_BACKEND_PORT
from backend.core.state import lifespan
from backend.api import api_router

# Ensure UTF-8 output on Windows CMD (Rule 8)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ==========================================
# FASTAPI APPLICATION SETUP
# ==========================================
app = FastAPI(
    title="E-Wallet & Telecom Assistant API",
    description="Hệ thống trợ lý ảo ví điện tử và tư vấn gói cước viễn thông",
    version="2.0.0",
    lifespan=lifespan
)

# Cấu hình CORS an toàn cho cả User Chatbot và Admin Dashboard
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    fe_port = os.getenv("FRONTEND_PORT", "3000").strip()
    admin_port = os.getenv("ADMIN_PORT", "3001").strip()
    allowed_origins = list({
        f"http://127.0.0.1:{fe_port}",
        f"http://127.0.0.1:{admin_port}",
        f"http://localhost:{fe_port}",
        f"http://localhost:{admin_port}",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3000",
        "http://localhost:3001",
    })

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các endpoints (/api/query, /api/init-stream, /api/health, /api/docs)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    # Luôn sử dụng IPv4 127.0.0.1 (Rule 11)
    port = int(os.getenv("BACKEND_PORT", DEFAULT_BACKEND_PORT))
    uvicorn.run("backend.main:app", host=DEFAULT_HOST, port=port, reload=True)
