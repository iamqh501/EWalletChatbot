import os
import sys

# Ensure UTF-8 output on Windows CMD (Rule 8)
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.state import app_state, lifespan, session_manager
from backend.api import api_router

# Aliases cho backward compatibility nếu có script bên ngoài import
from backend.tools import (
    load_package_data,
    execute_search_general_knowledge as global_search_general_knowledge,
    execute_search_telecom_packages as global_search_telecom_packages
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
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
