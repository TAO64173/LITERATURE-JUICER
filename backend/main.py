"""FastAPI 应用入口"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.code_api import router as code_router
from backend.api.upload_api import router as upload_router
from backend.db_manager import init_db
from backend.cache import init_cache

# 配置日志，确保 Render 日志中能看到调试信息
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

frontend = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_cache()
    yield


app = FastAPI(title="Literature Juicer", version="1.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(code_router)
app.include_router(upload_router)

# 静态文件
app.mount("/static", StaticFiles(directory=frontend / "static"), name="static")


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return Response(content="ok", status_code=200)


@app.get("/")
def index():
    return FileResponse(frontend / "templates" / "index.html")


if __name__ == "__main__":
    import uvicorn

    print("[启动] Literature Juicer 服务")
    print("[地址] http://127.0.0.1:8000")
    print("[调试] reload=True 已启用")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
