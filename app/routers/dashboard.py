"""Dashboard snapshot APIs backed by live execution state."""

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies.container import get_execution_service
from app.services.execution_service import ExecutionService
from core.streaming import ExecutionEvent
from core.streaming import ExecutionEventType

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/snapshot")
async def get_dashboard_snapshot(
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    workflow = await service.latest_workflow()
    if workflow is None:
        return _empty_snapshot()

    workflow_id = workflow.workflow_id
    telemetry = await service.get_workflow_telemetry(workflow_id)
    log_response = await service.get_logs(workflow_id)
    events = tuple(ExecutionEvent.model_validate(event) for event in log_response.events)
    event_dicts = [_frontend_event(event) for event in events]
    logs = [
        {
            "id": str(event.id),
            "timestamp": event.timestamp.isoformat(),
            "level": event.payload.get("level", "info"),
            "source": event.agent_name or "workflow",
            "message": event.message,
        }
        for event in events
        if event.type == ExecutionEventType.LOG_EMITTED
    ]
    outputs = [event for event in events if event.type == ExecutionEventType.OUTPUT_GENERATED]
    qa_events = [event for event in events if event.agent_name == "qa"]
    token_events = [event for event in events if event.type == ExecutionEventType.TOKEN_STREAMED]
    retries = sum(1 for event in events if event.type == ExecutionEventType.RETRY_STARTED)
    failures = sum(1 for event in events if event.type in {ExecutionEventType.AGENT_FAILED, ExecutionEventType.QA_FAILED})

    return {
        "workflowId": str(workflow_id),
        "agents": [
            {
                "key": node.agent_name,
                "name": node.label,
                "status": _agent_status(node.status.value),
                "currentTask": _current_task(node.status.value),
                "lastEventAt": (node.completed_at or node.started_at or workflow.updated_at).isoformat(),
                "retryCount": node.retry_count,
            }
            for node in telemetry.nodes
        ],
        "stages": [
            {
                "id": node.agent_name,
                "label": node.label,
                "status": _stage_status(node.status.value),
                "startedAt": node.started_at.isoformat() if node.started_at else None,
                "completedAt": node.completed_at.isoformat() if node.completed_at else None,
                "metadata": node.metadata,
            }
            for node in telemetry.nodes
        ],
        "events": event_dicts,
        "timeline": [
            {
                "id": item.id,
                "title": item.event_type,
                "description": item.message,
                "timestamp": item.timestamp.isoformat(),
                "status": _timeline_status(item.event_type),
            }
            for item in telemetry.timeline
        ],
        "logs": logs,
        "qaReport": _qa_report(workflow_id, qa_events),
        "docs": _docs(outputs),
        "pullRequest": _pull_request(workflow_id, outputs),
        "approvals": [],
        "observability": {
            "workflow": {
                "workflowId": str(workflow_id),
                "durationMs": telemetry.duration_ms,
                "agentCount": len(telemetry.nodes),
                "retries": retries,
                "failures": failures,
                "qaRejectionRate": 1 if any(event.type == ExecutionEventType.QA_FAILED for event in events) else 0,
                "tokenUsage": {
                    "promptTokens": 0,
                    "completionTokens": sum(int(event.payload.get("estimated_tokens", 0)) for event in token_events),
                    "totalTokens": sum(int(event.payload.get("estimated_tokens", 0)) for event in token_events),
                },
                "promptTelemetry": {
                    "messageCount": len(events),
                    "characterCount": sum(len(event.message) for event in events),
                    "estimatedTokens": sum(max(1, len(event.message) // 4) for event in events),
                },
            },
            "agents": [],
            "metrics": [
                "execution_events_total",
                "agent_retries_total",
                "agent_failures_total",
                "completion_tokens_streamed_total",
            ],
            "exporters": {
                "opentelemetryReady": True,
                "datadogReady": False,
                "prometheusReady": True,
                "grafanaReady": True,
            },
        },
        "governance": {"documents": [], "versions": []},
        "promptStudio": {
            "prompts": [],
            "versions": [],
            "testResult": {
                "preview": {"rendered": "", "missingVariables": [], "estimatedTokens": 0, "characterCount": 0},
                "executionPreview": "",
                "evaluation": {"score": 0, "passed": False, "findings": []},
            },
        },
        "workspace": {"conversations": [], "workspaces": [], "projects": [], "isolation": []},
        "visualization": _frontend_telemetry(telemetry),
        "mermaid": telemetry.mermaid,
    }


def _empty_snapshot() -> dict[str, Any]:
    workflow_id = "no-active-workflow"
    agents = ("ba", "architect", "developer", "qa", "docs", "pr")
    return {
        "workflowId": workflow_id,
        "agents": [
            {"key": agent, "name": agent, "status": "idle", "currentTask": "No active execution", "lastEventAt": "", "retryCount": 0}
            for agent in agents
        ],
        "stages": [{"id": agent, "label": agent, "status": "pending", "metadata": {}} for agent in agents],
        "events": [],
        "timeline": [],
        "logs": [],
        "qaReport": {"executionId": workflow_id, "status": "running", "coveragePercent": 0, "unitTests": 0, "integrationTests": 0, "browserTests": 0, "bugs": [], "screenshots": []},
        "docs": [],
        "pullRequest": {"id": workflow_id, "title": "No pull request generated", "status": "draft", "branch": "", "target": "", "changedFiles": 0, "riskLevel": "info", "summary": "No active execution has generated PR output."},
        "approvals": [],
        "observability": {"workflow": {"workflowId": workflow_id, "durationMs": 0, "agentCount": len(agents), "retries": 0, "failures": 0, "qaRejectionRate": 0, "tokenUsage": {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}, "promptTelemetry": {"messageCount": 0, "characterCount": 0, "estimatedTokens": 0}}, "agents": [], "metrics": [], "exporters": {"opentelemetryReady": False, "datadogReady": False, "prometheusReady": False, "grafanaReady": False}},
        "governance": {"documents": [], "versions": []},
        "promptStudio": {"prompts": [], "versions": [], "testResult": {"preview": {"rendered": "", "missingVariables": [], "estimatedTokens": 0, "characterCount": 0}, "executionPreview": "", "evaluation": {"score": 0, "passed": False, "findings": []}}},
        "workspace": {"conversations": [], "workspaces": [], "projects": [], "isolation": []},
        "visualization": {"workflowId": workflow_id, "status": "pending", "progressPercent": 0, "durationMs": 0, "nodes": [], "edges": [], "timeline": [], "mermaid": "flowchart LR", "metadata": {}},
        "mermaid": "flowchart LR",
    }


def _frontend_event(event: Any) -> dict[str, Any]:
    event_type = event.type.value
    return {
        "id": str(event.id),
        "type": event_type,
        "agent": event.agent_name or "ba",
        "message": event.message,
        "timestamp": event.timestamp.isoformat(),
        "severity": "high" if event_type in {"agent_failed", "QA_failed"} else "medium" if event_type == "retry_started" else "info",
        "payload": event.payload,
    }


def _frontend_telemetry(telemetry: Any) -> dict[str, Any]:
    return {
        "workflowId": str(telemetry.workflow_id),
        "status": telemetry.status.value,
        "activeAgent": telemetry.active_agent,
        "progressPercent": telemetry.progress_percent,
        "durationMs": telemetry.duration_ms,
        "nodes": [
            {
                "id": node.id,
                "label": node.label,
                "agentName": node.agent_name,
                "status": node.status.value,
                "startedAt": node.started_at.isoformat() if node.started_at else None,
                "completedAt": node.completed_at.isoformat() if node.completed_at else None,
                "durationMs": node.duration_ms,
                "retryCount": node.retry_count,
                "metadata": node.metadata,
            }
            for node in telemetry.nodes
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "label": edge.label,
                "condition": edge.condition,
                "isLoop": edge.is_loop,
                "metadata": edge.metadata,
            }
            for edge in telemetry.edges
        ],
        "timeline": [
            {
                "id": item.id,
                "eventType": item.event_type,
                "agentName": item.agent_name,
                "message": item.message,
                "timestamp": item.timestamp.isoformat(),
                "durationMs": item.duration_ms,
                "metadata": item.metadata,
            }
            for item in telemetry.timeline
        ],
        "mermaid": telemetry.mermaid,
        "metadata": telemetry.metadata,
    }


def _agent_status(status: str) -> str:
    return {"pending": "idle", "paused": "blocked"}.get(status, status)


def _stage_status(status: str) -> str:
    return "pending" if status == "paused" else status


def _timeline_status(event_type: str) -> str:
    if event_type in {"agent_failed", "QA_failed"}:
        return "failed"
    if event_type in {"agent_completed", "docs_generated", "PR_generated", "output_generated"}:
        return "completed"
    return "running"


def _current_task(status: str) -> str:
    return {
        "pending": "Waiting for upstream output",
        "running": "Executing",
        "paused": "Blocked by approval or pause gate",
        "completed": "Completed",
        "failed": "Failed",
    }.get(status, status)


def _qa_report(workflow_id: Any, qa_events: list[Any]) -> dict[str, Any]:
    latest = qa_events[-1] if qa_events else None
    passed = bool(latest and latest.payload.get("metadata", {}).get("passed"))
    failed = any(event.type == ExecutionEventType.QA_FAILED for event in qa_events)
    latest_output = next((event for event in reversed(qa_events) if event.type == ExecutionEventType.OUTPUT_GENERATED), None)
    metadata = latest_output.payload.get("metadata", {}) if latest_output and isinstance(latest_output.payload, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    findings = metadata.get("findings", []) if isinstance(metadata.get("findings", []), list) else []
    test_reports = metadata.get("test_reports", []) if isinstance(metadata.get("test_reports", []), list) else []
    bug_summaries = metadata.get("bug_summaries", []) if isinstance(metadata.get("bug_summaries", []), list) else []
    qa_meta = metadata.get("metadata", {}) if isinstance(metadata.get("metadata", {}), dict) else {}
    fix_requests = qa_meta.get("structured_fix_requests", []) if isinstance(qa_meta.get("structured_fix_requests", []), list) else []
    failed_tests = 0
    for report in test_reports:
        if not isinstance(report, dict):
            continue
        failed_tests += int(report.get("failed", 0) or 0)
    impacted_modules: list[str] = []
    for item in fix_requests:
        if not isinstance(item, dict):
            continue
        modules = item.get("impacted_modules", [])
        if isinstance(modules, list):
            impacted_modules.extend(str(module) for module in modules if str(module).strip())
    impacted_modules = list(dict.fromkeys(impacted_modules))[:12]
    return {
        "executionId": str(workflow_id),
        "status": "failed" if failed else "passed" if passed else "running",
        "coveragePercent": 0,
        "unitTests": len(test_reports),
        "integrationTests": 0,
        "browserTests": 0,
        "bugs": bug_summaries,
        "screenshots": [],
        "findingsCount": len(findings),
        "failedTests": failed_tests,
        "recommendedFixesCount": len(qa_meta.get("recommended_fixes", [])) if isinstance(qa_meta.get("recommended_fixes", []), list) else 0,
        "patchRequestsGenerated": len(fix_requests),
        "impactedModules": impacted_modules,
    }


def _docs(outputs: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(event.id),
            "title": event.payload.get("summary") or event.message,
            "status": "generated",
            "updatedAt": event.timestamp.isoformat(),
            "summary": event.message,
        }
        for event in outputs
        if event.agent_name == "docs"
    ]


def _pull_request(workflow_id: Any, outputs: list[Any]) -> dict[str, Any]:
    pr_output = next((event for event in reversed(outputs) if event.agent_name == "pr"), None)
    return {
        "id": str(pr_output.id if pr_output else workflow_id),
        "title": str(pr_output.payload.get("summary") if pr_output else "No pull request generated"),
        "status": "draft",
        "branch": "",
        "target": "",
        "changedFiles": 0,
        "riskLevel": "info",
        "summary": pr_output.message if pr_output else "No PR output has been generated for this execution.",
    }
