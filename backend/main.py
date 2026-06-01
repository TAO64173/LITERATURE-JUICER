"""FastAPI 应用入口（API-only，前端由 Next.js 提供）"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.api.code_api import router as code_router
from backend.api.invite_api import router as invite_router
from backend.api.payment_api import router as payment_router
from backend.api.upload_api import router as upload_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# CORS origins: Next.js dev server + production domain
_cors_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000"
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Literature Juicer", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(code_router)
app.include_router(invite_router)
app.include_router(payment_router)
app.include_router(upload_router)


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return Response(content="ok", status_code=200)


if __name__ == "__main__":
    import uvicorn

    print("[启动] Literature Juicer API 服务")
    print("[地址] http://127.0.0.1:8000")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
