"""FastAPI 应用入口。

通过 ``create_app()`` 创建应用，注册 CORS、路由和异常处理器。
``startup`` 事件自动创建所有表；``shutdown`` 事件释放引擎。
"""
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import User, Novel, Chapter, CharacterProfile, WorldSetting  # noqa: F401 — register models on Base
from app.models import PendingMemory, PlotFact, Foreshadowing  # noqa: F401 — register models on Base
from app.api import auth, memory, novels, planning, revisions, writing
from app.ai import router as ai_router
from app.core.config import settings
from app.core.database import engine, Base
from app.core.handlers import register_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("novel_agent")


def create_app() -> FastAPI:
    app = FastAPI(title="Novel Agent", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(novels.router, prefix="/api/v1")
    app.include_router(memory.router, prefix="/api/v1")
    app.include_router(ai_router.router, prefix="/api/v1")
    app.include_router(writing.router, prefix="/api/v1")
    app.include_router(planning.router, prefix="/api/v1")
    app.include_router(revisions.router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Environment: %s", settings.APP_ENV)
        logger.info("Database: %s", settings.db_driver)
        logger.info("Listening at http://0.0.0.0:8000")
        routes_count = len([r for r in app.routes if hasattr(r, "methods")])
        logger.info("Routes registered: %d", routes_count)

    @app.on_event("shutdown")
    async def shutdown():
        await engine.dispose()

    return app


app = create_app()

if __name__ == "__main__":
    logger.info("Starting server at http://0.0.0.0:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
