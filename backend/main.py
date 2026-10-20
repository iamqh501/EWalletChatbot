import os
import sys
import backend.core.env
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.state import lifespan
from backend.api import api_router

# Ensure UTF-8 output on Windows CMD (Rule 8)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"


# ==========================================
# FASTAPI APPLICATION SETUP
# ==========================================
app = FastAPI(
    title="E-Wallet & Telecom Assistant API",
    description="Hệ thống trợ lý ảo ví điện tử và tư vấn gói cước viễn thông",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các endpoints (/api/query, /api/init-stream, /api/health)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    # Luôn sử dụng IPv4 127.0.0.1 (Rule 11)
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=True)
