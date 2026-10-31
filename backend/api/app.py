from contextlib import asynccontextmanager
import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routes import router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.api.runtime import AssistantRuntime

    app.state.runtime = AssistantRuntime()
    try:
        await asyncio.to_thread(app.state.runtime.warmup)
        yield
    finally:
        app.state.runtime.close()


app = FastAPI(title="Voice Assistant API", version="1.0.0", lifespan=lifespan)
allowed_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": app.title,
        "docs": "/docs",
        "health": "/api/v1/health",
        "frontend": "Запустите Reflex отдельно из папки frontend.",
    }


def main():
    import uvicorn

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    uvicorn.run("backend.api.app:app", host="0.0.0.0", port=int(os.getenv("API_PORT", "8000")), reload=False)


if __name__ == "__main__":
    main()
