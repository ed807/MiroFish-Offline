"""
Report API Routes - FastAPI Version
Provides interfaces for simulation report generation, retrieval, and conversation
Migrated from Flask to FastAPI with async support
"""

import os
import traceback
import threading
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel

from . import report_router
from ..config import Config
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..services.graph_tools import GraphToolsService
from ..utils.logger import get_logger
from ..storage import Neo4jStorage

logger = get_logger('mirofish.api.report')


def _get_storage():
    """Get Neo4jStorage singleton"""
    storage = Neo4jStorage()
    if not storage:
        raise ValueError("GraphStorage not initialized")
    return storage


# Pydantic models for request validation
class ReportGenerateRequest(BaseModel):
    simulation_id: str
    force_regenerate: bool = False


class ReportChatRequest(BaseModel):
    simulation_id: str
    message: str
    chat_history: Optional[list] = None


class TaskStatusRequest(BaseModel):
    task_id: Optional[str] = None
    simulation_id: Optional[str] = None


# ============== Report Generation Interface ==============

@report_router.post('/generate', response_model=Dict[str, Any])
async def generate_report(request_data: ReportGenerateRequest, background_tasks: BackgroundTasks):
    try:
        simulation_id = request_data.simulation_id
        force_regenerate = request_data.force_regenerate
        
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Simulation does not exist: {simulation_id}")

        if not force_regenerate:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return {"success": True, "data": {
                    "simulation_id": simulation_id,
                    "report_id": existing_report.report_id,
                    "status": "completed",
                    "message": "Report already exists",
                    "already_generated": True
                }}

        project = ProjectManager.get_project(state.project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project does not exist: {state.project_id}")

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            raise HTTPException(status_code=400, detail="Missing graph ID, please ensure graph is built")

        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            raise HTTPException(status_code=400, detail="Missing simulation requirement description")

        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"

        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="report_generate",
            metadata={"simulation_id": simulation_id, "graph_id": graph_id, "report_id": report_id}
        )

        # Initialize graph_tools
        storage = _get_storage()
        graph_tools = GraphToolsService(storage=storage)

        def run_generate():
            try:
                task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=0, message="Initializing Report Agent...")
                agent = ReportAgent(
                    graph_id=graph_id,
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    graph_tools=graph_tools
                )
                def progress_callback(stage, progress, message):
                    task_manager.update_task(task_id, progress=progress, message=f"[{stage}] {message}")
                report = agent.generate_report(progress_callback=progress_callback, report_id=report_id)
                ReportManager.save_report(report)
                if report.status == ReportStatus.COMPLETED:
                    task_manager.complete_task(task_id, result={"report_id": report.report_id, "simulation_id": simulation_id, "status": "completed"})
                else:
                    task_manager.fail_task(task_id, report.error or "Report generation failed")
            except Exception as e:
                logger.error(f"Report generation failed: {str(e)}")
                task_manager.fail_task(task_id, str(e))

        background_tasks.add_task(run_generate)

        return {"success": True, "data": {
            "simulation_id": simulation_id,
            "report_id": report_id,
            "task_id": task_id,
            "status": "generating",
            "message": "Report generation task started. Query progress via /api/report/generate/status",
            "already_generated": False
        }}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start report generation task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@report_router.post('/generate/status', response_model=Dict[str, Any])
async def get_generate_status(request_data: TaskStatusRequest):
    try:
        task_id = request_data.task_id
        simulation_id = request_data.simulation_id

        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return {"success": True, "data": {
                    "simulation_id": simulation_id,
                    "report_id": existing_report.report_id,
                    "status": "completed",
                    "progress": 100,
                    "message": "Report generated",
                    "already_completed": True
                }}

        if not task_id:
            raise HTTPException(status_code=400, detail="Please provide task_id or simulation_id")

        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task does not exist: {task_id}")

        return {"success": True, "data": task.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Report Retrieval Interface ==============

@report_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    try:
        report = ReportManager.get_report(report_id)
        if not report:
            return jsonify({"success": False, "error": f"Report does not exist: {report_id}"}), 404
        return jsonify({"success": True, "data": report.to_dict()})
    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
def get_report_by_simulation(simulation_id: str):
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        if not report:
            return jsonify({"success": False, "error": f"No report available for this simulation: {simulation_id}", "has_report": False}), 404
        return jsonify({"success": True, "data": report.to_dict()})
    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/list', methods=['GET'])
def list_reports():
    try:
        simulation_id = request.args.get('simulation_id')
        limit = request.args.get('limit', 50, type=int)
        reports = ReportManager.list_reports(simulation_id=simulation_id, limit=limit)
        return jsonify({"success": True, "data": [r.to_dict() for r in reports], "count": len(reports)})
    except Exception as e:
        logger.error(f"Failed to list reports: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    try:
        report = ReportManager.get_report(report_id)
        if not report:
            return jsonify({"success": False, "error": f"Report does not exist: {report_id}"}), 404

        md_path = ReportManager._get_report_markdown_path(report_id)
        if not os.path.exists(md_path):
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(report.markdown_content)
                temp_path = f.name
            return send_file(temp_path, as_attachment=True, download_name=f"{report_id}.md")

        return send_file(md_path, as_attachment=True, download_name=f"{report_id}.md")

    except Exception as e:
        logger.error(f"Failed to download report: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    try:
        success = ReportManager.delete_report(report_id)
        if not success:
            return jsonify({"success": False, "error": f"Report does not exist: {report_id}"}), 404
        return jsonify({"success": True, "message": f"Report deleted: {report_id}"})
    except Exception as e:
        logger.error(f"Failed to delete report: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== Report Agent Chat Interface ==============

@report_bp.route('/chat', methods=['POST'])
def chat_with_report_agent():
    try:
        data = request.get_json() or {}
        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])

        if not simulation_id:
            return jsonify({"success": False, "error": "Please provide simulation_id"}), 400
        if not message:
            return jsonify({"success": False, "error": "Please provide message"}), 400

        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            return jsonify({"success": False, "error": f"Simulation does not exist: {simulation_id}"}), 404

        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({"success": False, "error": f"Project does not exist: {state.project_id}"}), 404

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({"success": False, "error": "Missing graph ID"}), 400

        simulation_requirement = project.simulation_requirement or ""

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized — check Neo4j connection")
        graph_tools = GraphToolsService(storage=storage)

        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            graph_tools=graph_tools
        )

        result = agent.chat(message=message, chat_history=chat_history)
        return jsonify({"success": True, "data": {"response": result, "simulation_id": simulation_id}})

    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== Report Progress and Section Retrieval Interface ==============

@report_bp.route('/<report_id>/progress', methods=['GET'])
def get_report_progress(report_id: str):
    try:
        progress = ReportManager.get_progress(report_id)
        if not progress:
            return jsonify({"success": False, "error": f"Report does not exist or progress info unavailable: {report_id}"}), 404
        return jsonify({"success": True, "data": progress})
    except Exception as e:
        logger.error(f"Failed to get report progress: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/<report_id>/sections', methods=['GET'])
def get_report_sections(report_id: str):
    try:
        sections = ReportManager.get_generated_sections(report_id)
        report = ReportManager.get_report(report_id)
        is_complete = report is not None and report.status == ReportStatus.COMPLETED
        return jsonify({"success": True, "data": {
            "report_id": report_id,
            "sections": sections,
            "total": len(sections),
            "is_complete": is_complete
        }})
    except Exception as e:
        logger.error(f"Failed to get section list: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/<report_id>/section/<int:section_index>', methods=['GET'])
def get_single_section(report_id: str, section_index: int):
    try:
        section_path = ReportManager._get_section_path(report_id, section_index)
        if not os.path.exists(section_path):
            return jsonify({"success": False, "error": f"Section does not exist: section_{section_index:02d}.md"}), 404
        with open(section_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"success": True, "data": {"filename": f"section_{section_index:02d}.md", "content": content}})
    except Exception as e:
        logger.error(f"Failed to get section content: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== Report Status Check Interface ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
def check_report_status(simulation_id: str):
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        has_report = report is not None
        report_status = report.status.value if report and hasattr(report.status, 'value') else (report.status if report else None)
        report_id = report.report_id if report else None
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED
        return jsonify({"success": True, "data": {
            "simulation_id": simulation_id,
            "has_report": has_report,
            "report_id": report_id,
            "report_status": report_status,
            "interview_unlocked": interview_unlocked
        }})
    except Exception as e:
        logger.error(f"Failed to check report status: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== Agent Log Interface ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
def get_agent_log(report_id: str):
    try:
        from_line = request.args.get('from_line', 0, type=int)
        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)
        return jsonify({"success": True, "data": log_data})
    except Exception as e:
        logger.error(f"Failed to get agent log: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
def stream_agent_log(report_id: str):
    try:
        logs = ReportManager.get_agent_log_stream(report_id)
        return jsonify({"success": True, "data": {"logs": logs, "count": len(logs)}})
    except Exception as e:
        logger.error(f"Failed to get agent log: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== Console Log Interface ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
def get_console_log(report_id: str):
    try:
        from_line = request.args.get('from_line', 0, type=int)
        log_data = ReportManager.get_console_log(report_id, from_line=from_line)
        return jsonify({"success": True, "data": log_data})
    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
def stream_console_log(report_id: str):
    try:
        logs = ReportManager.get_console_log_stream(report_id)
        return jsonify({"success": True, "data": {"logs": logs, "count": len(logs)}})
    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== Tool Call Interface (For Debugging) ==============

@report_bp.route('/tools/search', methods=['POST'])
def search_graph_tool():
    try:
        data = request.get_json() or {}
        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)
        if not graph_id or not query:
            return jsonify({"success": False, "error": "Please provide graph_id and query"}), 400
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized — check Neo4j connection")
        tools = GraphToolsService(storage=storage)
        result = tools.search_graph(graph_id=graph_id, query=query, limit=limit)
        return jsonify({"success": True, "data": result.to_dict()})
    except Exception as e:
        logger.error(f"Graph search failed: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@report_bp.route('/tools/statistics', methods=['POST'])
def get_graph_statistics_tool():
    try:
        data = request.get_json() or {}
        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({"success": False, "error": "Please provide graph_id"}), 400
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized — check Neo4j connection")
        tools = GraphToolsService(storage=storage)
        result = tools.get_graph_statistics(graph_id)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Failed to get graph statistics: {str(e)}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500