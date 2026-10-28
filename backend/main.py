import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import HOST, BACKEND_PORT, FRONTEND_PORT, ADMIN_PORT
from backend.core.state import lifespan
from backend.api import api_router

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

# Cấu hình CORS cho User Chatbot và Admin Dashboard
allowed_origins = list({
    f"http://{HOST}:{FRONTEND_PORT}",
    f"http://{HOST}:{ADMIN_PORT}",
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
    uvicorn.run("backend.main:app", host=HOST, port=BACKEND_PORT, reload=True)
