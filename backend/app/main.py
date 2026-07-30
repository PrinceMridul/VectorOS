"""VectorOS API.

Learn by Thinking.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.graph import USING_LANGGRAPH, tutor_graph
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.features.auth.router import router as auth_router
from app.features.dashboard.router import router as dashboard_router
from app.features.goals.router import router as goals_router
from app.features.graph.router import router as graph_router
from app.features.session.router import router as session_router
from app.llm._http import close_client
from app.llm.registry import llm

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await init_db()

    if settings.auto_seed:
        from app.db.seed import seed
        from app.db.session import SessionFactory

        async with SessionFactory() as db:
            await seed(db)
            await db.commit()

    tutor_graph()  # compile the mesh once, at boot, not on the first learner
    log.info(
        "vectoros_ready",
        env=settings.env,
        provider=llm().name,
        langgraph=USING_LANGGRAPH,
        mastery_threshold=settings.mastery_threshold,
    )
    yield
    await close_client()


app = FastAPI(
    title="VectorOS",
    description="An AI-native learning operating system. An answer is not an education.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

api = APIRouter(prefix="/api")
api.include_router(auth_router)
api.include_router(goals_router)
api.include_router(graph_router)
api.include_router(session_router)
api.include_router(dashboard_router)
app.include_router(api)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "env": settings.env,
        "llm_provider": llm().name,
        "langgraph": USING_LANGGRAPH,
        "database": "postgres" if settings.is_postgres else "sqlite",
    }


@app.get("/api/pedagogy", tags=["meta"])
async def pedagogy() -> dict[str, object]:
    """The tuned constants, exposed.

    A learning system that will not say what threshold it used to declare you
    competent is asking for trust it has not earned.
    """
    return {
        "mastery_threshold": settings.mastery_threshold,
        "zpd_band": [settings.zpd_target_low, settings.zpd_target_high],
        "struggle_floor_seconds": settings.struggle_floor_seconds,
        "offload_lock_threshold": settings.offload_lock_threshold,
        "mastery_half_life_days": settings.mastery_half_life_days,
        "max_scaffold_level": settings.max_scaffold_level,
        "reflection_pass_threshold": settings.reflection_pass_threshold,
    }
