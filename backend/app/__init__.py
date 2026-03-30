"""
MiroFish Backend - FastAPI Application Factory
Migrated from Flask to FastAPI for async support and better performance
"""

import os
import warnings
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Suppress multiprocessing resource_tracker warnings (from third-party libraries like transformers)
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Config
from .utils.logger import setup_logger, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """FastAPI lifespan manager for startup and shutdown events"""
    logger = get_logger('mirofish')
    
    # Startup
    logger.info("=" * 50)
    logger.info("MiroFish-Offline Backend starting...")
    logger.info("=" * 50)
    
    # Initialize Neo4jStorage singleton
    from .storage import Neo4jStorage
    try:
        neo4j_storage = Neo4jStorage()
        app.state.neo4j_storage = neo4j_storage
        logger.info("Neo4jStorage initialized (connected to %s)", Config.NEO4J_URI)
    except Exception as e:
        logger.error("Neo4jStorage initialization failed: %s", e)
        app.state.neo4j_storage = None
    
    # Register simulation process cleanup function
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    logger.info("Simulation process cleanup function registered")
    
    logger.info("MiroFish-Offline Backend startup complete")
    
    yield
    
    # Shutdown
    logger.info("MiroFish-Offline Backend shutting down...")
    # Add any cleanup logic here if needed


def create_app() -> FastAPI:
    """FastAPI application factory function"""
    app = FastAPI(
        title="MiroFish-Offline API",
        description="Multi-agent social simulation backend with smart LLM rotation",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger = get_logger('mirofish.request')
        logger.debug(f"Request: {request.method} {request.url.path}")
        
        if request.method in ["POST", "PUT"] and 'json' in request.headers.get('content-type', ''):
            try:
                body = await request.json()
                logger.debug(f"Request body: {body}")
            except Exception:
                pass
        
        response = await call_next(request)
        logger.debug(f"Response: {response.status_code}")
        return response
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger = get_logger('mirofish.error')
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": type(exc).__name__}
        )
    
    # Include routers
    from .api import graph_router, simulation_router, report_router
    app.include_router(graph_router, prefix="/api/graph", tags=["Graph"])
    app.include_router(simulation_router, prefix="/api/simulation", tags=["Simulation"])
    app.include_router(report_router, prefix="/api/report", tags=["Report"])
    
    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "MiroFish-Offline Backend"}
    
    # LLM Metrics endpoint (for monitoring rotation)
    @app.get("/api/v1/llm/metrics")
    async def llm_metrics():
        from .utils.llm_rotator import SmartLLMRotator
        rotator = SmartLLMRotator()
        return rotator.get_metrics()
    
    return app
