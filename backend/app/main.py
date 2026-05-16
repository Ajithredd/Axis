"""Axis — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api import auth, graph, projects, search, webhooks
from app.connectors.registry import connector_registry


from app.database.qdrant import init_qdrant_collections, close_qdrant_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # --- Startup ---
    await init_db()
    await init_qdrant_collections()
    connector_registry.discover()
    print(f"✓ Registered connectors: {list(connector_registry.list_connectors().keys())}")
    yield
    # --- Shutdown ---
    await close_qdrant_client()
    print("Axis shutting down.")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered alignment engine for software teams",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(graph.router, prefix="/api/graph", tags=["Intelligence Graph"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    connectors = connector_registry.list_connectors()
    return {
        "status": "healthy",
        "service": settings.app_name,
        "connectors": list(connectors.keys()),
    }
