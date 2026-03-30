"""
API Routes Module - FastAPI Routers
Migrated from Flask Blueprints to FastAPI APIRouter
"""

from fastapi import APIRouter

graph_router = APIRouter()
simulation_router = APIRouter()
report_router = APIRouter()

# Import routes to register them
from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
