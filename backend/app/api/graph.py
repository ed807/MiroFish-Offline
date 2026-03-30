"""
Graph-related API Routes - FastAPI Version
Uses project context mechanism with server-side state persistence
Migrated from Flask to FastAPI with async support
"""

import os
import traceback
import threading
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel

from . import graph_router
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# Get logger
logger = get_logger('mirofish.api')


def _get_storage():
    """Get Neo4jStorage from FastAPI app state."""
    from fastapi import Request
    # This will be called within request context
    try:
        from app import create_app
        # Storage is singleton, access directly
        from ..storage import Neo4jStorage
        storage = Neo4jStorage()
        if not storage:
            raise ValueError("GraphStorage not initialized — check Neo4j connection")
        return storage
    except Exception as e:
        logger.error(f"Storage access error: {e}")
        raise HTTPException(status_code=503, detail="GraphStorage not initialized")


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# Pydantic models for request/response validation
class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    document_type: Optional[str] = "general"


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    created_at: str
    updated_at: str
    document_type: Optional[str]


class TaskResponse(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    progress: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============== Project Management Interface ==============

@graph_router.get('/project/{project_id}', response_model=Dict[str, Any])
async def get_project(project_id: str):
    """Get project details"""
    try:
        project = ProjectManager.get_project(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        
        return {
            "success": True,
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status.value,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
                "document_type": getattr(project, 'document_type', 'general')
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.post('/project', response_model=Dict[str, Any])
async def create_project(request_data: ProjectCreateRequest):
    """Create a new project"""
    try:
        project = ProjectManager.create_project(
            name=request_data.name,
            description=request_data.description,
            document_type=request_data.document_type
        )
        
        return {
            "success": True,
            "message": f"Project '{project.name}' created successfully",
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status.value
            }
        }
    except Exception as e:
        logger.error(f"Error creating project: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.delete('/project/{project_id}', response_model=Dict[str, Any])
async def delete_project(project_id: str):
    """Delete a project"""
    try:
        success = ProjectManager.delete_project(project_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        
        return {
            "success": True,
            "message": f"Project {project_id} deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.get('/projects', response_model=Dict[str, Any])
async def list_projects():
    """List all projects"""
    try:
        projects = ProjectManager.list_projects()
        
        return {
            "success": True,
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status.value,
                    "created_at": p.created_at.isoformat()
                }
                for p in projects
            ]
        }
    except Exception as e:
        logger.error(f"Error listing projects: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Document Upload and Processing ==============

@graph_router.post('/project/{project_id}/upload', response_model=Dict[str, Any])
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """Upload and process a document for a project"""
    try:
        # Validate project exists
        project = ProjectManager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        
        # Validate file
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {Config.ALLOWED_EXTENSIONS}"
            )
        
        # Save file temporarily
        temp_dir = Config.TEMP_DIR
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{project_id}_{file.filename}")
        
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Process document asynchronously
        def process_document():
            try:
                ProjectManager.update_project_status(project_id, ProjectStatus.PROCESSING)
                
                # Parse file
                parser = FileParser()
                text_content = parser.parse_file(temp_path)
                
                # Build graph
                builder = GraphBuilderService()
                builder.build_graph_from_text(text_content, project_id=project_id)
                
                ProjectManager.update_project_status(project_id, ProjectStatus.COMPLETED)
                
                # Cleanup temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
            except Exception as e:
                logger.error(f"Document processing failed: {e}")
                ProjectManager.update_project_status(project_id, ProjectStatus.FAILED)
        
        if background_tasks:
            background_tasks.add_task(process_document)
        else:
            # Run synchronously if no background tasks available
            process_document()
        
        return {
            "success": True,
            "message": f"Document '{file.filename}' uploaded and processing started",
            "project_id": project_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Graph Query Interface ==============

@graph_router.get('/project/{project_id}/graph/stats', response_model=Dict[str, Any])
async def get_graph_stats(project_id: str):
    """Get graph statistics for a project"""
    try:
        storage = _get_storage()
        
        stats = storage.get_graph_stats(project_id=project_id)
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting graph stats: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.post('/project/{project_id}/graph/query', response_model=Dict[str, Any])
async def query_graph(project_id: str, query_data: Dict[str, Any]):
    """Execute a Cypher query on the graph"""
    try:
        storage = _get_storage()
        
        cypher = query_data.get('cypher')
        if not cypher:
            raise HTTPException(status_code=400, detail="Cypher query required")
        
        params = query_data.get('params', {})
        results = storage.execute_query(cypher, params=params, project_id=project_id)
        
        return {
            "success": True,
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying graph: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Entity and Relationship Management ==============

@graph_router.get('/project/{project_id}/entities', response_model=Dict[str, Any])
async def list_entities(project_id: str, entity_type: Optional[str] = None):
    """List entities in the graph"""
    try:
        storage = _get_storage()
        
        entities = storage.get_entities(project_id=project_id, entity_type=entity_type)
        
        return {
            "success": True,
            "entities": entities,
            "count": len(entities)
        }
    except Exception as e:
        logger.error(f"Error listing entities: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.get('/project/{project_id}/relationships', response_model=Dict[str, Any])
async def list_relationships(project_id: str, relationship_type: Optional[str] = None):
    """List relationships in the graph"""
    try:
        storage = _get_storage()
        
        relationships = storage.get_relationships(
            project_id=project_id,
            relationship_type=relationship_type
        )
        
        return {
            "success": True,
            "relationships": relationships,
            "count": len(relationships)
        }
    except Exception as e:
        logger.error(f"Error listing relationships: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
