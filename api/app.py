import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.routes.chat import router as chat_router
from data.redis_memory import RedisMemoryStore, RedisUnavailableError

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI(
    title="旅行小助手",
    description="LangChain 旅行顾问智能体",
    version="0.1.0",
)

origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

frontend_dir = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(frontend_dir / "index.html")


@app.get("/api/health")
async def health():
    try:
        store = RedisMemoryStore()
        connected = True
        ttl_seconds = store.ttl_seconds
    except RedisUnavailableError:
        connected = False
        ttl_seconds = None
    return {
        "status": "healthy" if connected else "degraded",
        "service": "travel-assistant",
        "redis_connected": connected,
        "session_ttl_seconds": ttl_seconds,
    }
