"""End-to-end MVP demo verifier for the alpha Docker Compose platform."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class VerifierError(RuntimeError):
    """Verification failure."""


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 30.0,
) -> Any:
    request_headers = {"Accept": "application/json", **(headers or {})}
    data: bytes | None = body
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return None
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return json.loads(raw)
            return raw
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VerifierError(f"{method} {url} failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise VerifierError(f"{method} {url} failed: {exc.reason}") from exc


def _multipart_body(files: list[Path]) -> tuple[bytes, str]:
    boundary = "----LegionAgentsMvpVerifierBoundary"
    lines: list[bytes] = []
    for file_path in files:
        mime, _ = mimetypes.guess_type(file_path.name)
        content_type = mime or "application/octet-stream"
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(
            (
                f'Content-Disposition: form-data; name="files"; filename="{file_path.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        lines.append(file_path.read_bytes())
        lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(lines), f"multipart/form-data; boundary={boundary}"


def _wait_for_workflow(api_base: str, workflow_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = _request("GET", f"{api_base}/executions/{workflow_id}/status")
        if status["status"] in {"completed", "failed", "cancelled"}:
            return status
        time.sleep(1.0)
    raise VerifierError(f"Workflow {workflow_id} did not finish in {timeout_seconds}s.")


def verify(api_base: str, workspace_root: Path, timeout_seconds: int) -> None:
    print("1) Checking health and readiness endpoints...")
    health = _request("GET", f"{api_base}/health")
    readiness = _request("GET", f"{api_base}/health/readiness")
    if health.get("status") != "ok":
        raise VerifierError("Health endpoint is not ok.")
    if readiness.get("checks", {}).get("api") != "ok":
        raise VerifierError("Readiness API check is not ok.")

    print("2) Verifying governance preload and editing/versioning...")
    governance = _request("GET", f"{api_base}/governance/configs")
    documents = governance.get("documents", [])
    if len(documents) == 0:
        raise VerifierError("No governance documents were preloaded.")
    target = next((doc for doc in documents if doc.get("kind") in {"personality", "anti_gravity"}), documents[0])
    updated_markdown = f'{target.get("markdown", "").rstrip()}\n\n- alpha-verifier-note: updated by mvp_demo_verifier'
    saved = _request(
        "POST",
        f"{api_base}/governance/configs",
        payload={
            "scope": target["scope"],
            "kind": target["kind"],
            "name": target["name"],
            "markdown": updated_markdown,
            "agent_name": target.get("agent_name"),
            "updated_by": "alpha-verifier",
            "change_summary": "Alpha verifier edit",
        },
    )
    document_id = saved["document"]["id"]
    versions = _request("GET", f"{api_base}/governance/configs/{document_id}/versions").get("versions", [])
    if len(versions) < 1:
        raise VerifierError("Governance version history was not produced.")

    print("3) Verifying provider CRUD and health...")
    created_provider = _request(
        "POST",
        f"{api_base}/providers",
        payload={
            "name": "AlphaVerifierProvider",
            "kind": "custom",
            "base_url": "http://localhost:11434/v1",
            "api_key": "alpha-verifier-api-key",
            "default_model": "gpt-4o-mini",
            "status": "active",
        },
    )["provider"]
    provider_id = created_provider["id"]
    _request(
        "PUT",
        f"{api_base}/providers/{provider_id}",
        payload={
            "name": "AlphaVerifierProvider",
            "kind": "custom",
            "base_url": "http://localhost:11434/v1",
            "api_key": "alpha-verifier-api-key-updated",
            "default_model": "gpt-4o-mini",
            "status": "active",
        },
    )
    _request("GET", f"{api_base}/providers/{provider_id}/health")

    print("4) Uploading markdown/txt files through upload API...")
    uploads_dir = workspace_root / "outputs" / "mvp_verifier"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    requirement_md = uploads_dir / "requirement.md"
    requirement_txt = uploads_dir / "requirement.txt"
    requirement_md.write_text(
        "# Requirement\nAnalyze this requirement and generate user stories.\n\nAs a user, I want role-based dashboard views.",
        encoding="utf-8",
    )
    requirement_txt.write_text("Need robust audit logging and workflow visibility.", encoding="utf-8")
    multipart, content_type = _multipart_body([requirement_md, requirement_txt])
    uploaded = _request(
        "POST",
        f"{api_base}/uploads/files",
        headers={"Content-Type": content_type},
        body=multipart,
    )
    if not isinstance(uploaded, list) or len(uploaded) < 1:
        raise VerifierError("Upload API did not return uploaded files.")
    upload_id = uploaded[0]["upload_id"]

    print("5) Verifying chat workflow trigger and execution observability...")
    conversation = _request(
        "POST",
        f"{api_base}/workspace/chat/conversations",
        payload={"title": "Alpha verifier demo", "created_by": "alpha-verifier"},
    )["conversation"]
    conversation_id = conversation["id"]
    message = _request(
        "POST",
        f"{api_base}/workspace/chat/conversations/{conversation_id}/messages",
        payload={
            "content": "Analyze this requirement and generate user stories",
            "trigger_workflow": True,
            "metadata": {"mode": "ba"},
        },
    )
    workflow = message.get("workflow")
    if not workflow:
        raise VerifierError("Chat message did not start a workflow.")
    workflow_id = workflow["workflow_id"]
    status = _wait_for_workflow(api_base, workflow_id, timeout_seconds=timeout_seconds)
    if status["status"] != "completed":
        raise VerifierError(f"Workflow did not complete successfully: {status['status']}")
    logs = _request("GET", f"{api_base}/executions/{workflow_id}/logs")
    if len(logs.get("events", [])) == 0:
        raise VerifierError("No execution events were recorded.")
    report = _request("GET", f"{api_base}/reports/qa/{workflow_id}")
    if report.get("workflow_id") != workflow_id:
        raise VerifierError("QA report endpoint did not return expected workflow output.")

    print("6) Verifying workflow endpoint with uploaded context...")
    workflow_from_upload = _request(
        "POST",
        f"{api_base}/workflows",
        payload={
            "task": "Implement story from upload",
            "upload_id": upload_id,
            "thread_id": f"alpha-verifier-{int(time.time())}",
        },
    )
    _wait_for_workflow(api_base, workflow_from_upload["workflow_id"], timeout_seconds=timeout_seconds)

    print("7) Cleaning up verifier provider...")
    _request("DELETE", f"{api_base}/providers/{provider_id}")

    print("\nMVP demo verification passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MVP alpha demo verification against a running API.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8080/api", help="Base API URL.")
    parser.add_argument("--workspace-root", default=str(Path.cwd()), help="Workspace root path.")
    parser.add_argument("--timeout-seconds", type=int, default=240, help="Workflow completion timeout.")
    args = parser.parse_args()
    try:
        verify(args.api_base.rstrip("/"), Path(args.workspace_root), args.timeout_seconds)
        return 0
    except VerifierError as exc:
        print(f"\nMVP demo verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
