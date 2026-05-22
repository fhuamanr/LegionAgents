"""Autonomous QA Agent runtime."""

import asyncio
import logging
import shlex
from dataclasses import dataclass

from pydantic import ValidationError

from core.agents.qa.browser import BrowserAutomationService, ScreenshotPathFactory
from core.agents.qa.contracts import BrowserAction, BrowserAutomationStep, QARuntimeConfig
from core.agents.qa.parser import QAOutputParser, format_validation_error
from core.agents.qa.prompts import QAPromptBuilder
from core.agents.qa.severity import SeverityClassifier
from core.agents.qa.telemetry import NoopQATelemetryHook, QATelemetryHook
from core.agents.runtime import AgentModelClient, AgentRuntime
from core.context import FileSystemAgentContextLoader
from core.contracts.agents import AgentDefinition, AgentStatus
from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.context import ContextLoadRequest
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.outputs import ExecutionLog, OutputContract, OutputSeverity, QAOutput, QualityFinding, ScreenshotEvidence, TestReport
from core.contracts.qa_sandbox import SandboxBrowserEngine, SandboxExecutionConfig, SandboxStep, SandboxStepAction
from core.qa_sandbox import QASandboxExecutor
from core.runtime.retry import RetryEngine, RetryPolicy


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class QAAgentRuntime(AgentRuntime):
    """Autonomous QA runtime with structured evidence generation."""

    def __init__(
        self,
        config: QARuntimeConfig,
        model_client: AgentModelClient,
        context_loader: FileSystemAgentContextLoader | None = None,
        prompt_builder: QAPromptBuilder | None = None,
        output_parser: QAOutputParser | None = None,
        browser_service: BrowserAutomationService | None = None,
        severity_classifier: SeverityClassifier | None = None,
        sandbox_executor: QASandboxExecutor | None = None,
        retry_engine: RetryEngine | None = None,
        telemetry_hook: QATelemetryHook | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._model_client = model_client
        self._context_loader = context_loader or FileSystemAgentContextLoader()
        self._prompt_builder = prompt_builder or QAPromptBuilder()
        self._output_parser = output_parser or QAOutputParser()
        self._browser_service = browser_service or BrowserAutomationService()
        self._severity_classifier = severity_classifier or SeverityClassifier()
        self._sandbox_executor = sandbox_executor or QASandboxExecutor()
        self._retry_engine = retry_engine or RetryEngine(RetryPolicy(max_attempts=2))
        self._telemetry_hook = telemetry_hook or NoopQATelemetryHook()
        self._logger = logger or logging.getLogger(f"{__name__}.{config.agent_name}")

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        if request.agent_name != self._config.agent_name:
            return self._failed_result(
                request=request,
                errors=(f"QA runtime cannot execute request for agent: {request.agent_name}",),
                warnings=tuple(),
            )

        self._logger.info("qa_agent_execution_started", extra={"agent": self._config.agent_name})
        await self._telemetry_hook.emit(
            "qa_agent_execution_started",
            {"agent": self._config.agent_name, "execution_id": str(request.execution_id)},
        )

        context_result = await self._context_loader.load_request(
            ContextLoadRequest(
                agent_name=self._config.agent_name,
                root_path=self._config.context_path,
                max_token_hint=self._config.max_context_token_hint,
            )
        )
        required_rules, rule_warnings = self._load_required_rules()
        messages = await self._prompt_builder.build(
            request=request,
            config=self._config,
            agent_context=context_result.context,
            required_rules=required_rules,
        )

        try:
            raw_output = await self._retry_engine.run(lambda: self._model_client.complete(messages))
            structured_output = self._output_parser.parse(
                raw_output=raw_output,
                agent_name=self._config.agent_name,
            )
            structured_output = await self._enrich_output(structured_output, request)
        except ValidationError as exc:
            return self._failed_result(
                request=request,
                errors=(format_validation_error(exc),),
                warnings=context_result.warnings + rule_warnings,
            )
        except ValueError as exc:
            return self._failed_result(
                request=request,
                errors=(str(exc),),
                warnings=context_result.warnings + rule_warnings,
            )
        except Exception as exc:
            self._logger.exception("qa_agent_execution_failed")
            return self._failed_result(
                request=request,
                errors=(str(exc),),
                warnings=context_result.warnings + rule_warnings,
            )

        output_artifact = Artifact(
            id=f"{self._config.agent_name}-{request.execution_id}",
            kind=ArtifactKind.TEST_REPORT,
            name="QA Structured Output",
            producer_agent=self._config.agent_name,
            content=structured_output.model_dump_json(indent=2),
            metadata={"contract_kind": structured_output.contract_kind.value},
        )
        result = AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self._config.agent_name,
            status=AgentStatus.COMPLETED,
            summary=structured_output.summary,
            artifacts=structured_output.artifacts + (output_artifact,),
            metadata={
                "context_warnings": context_result.warnings + rule_warnings,
                "loaded_rule_files": tuple(sorted(required_rules)),
                "prompt_message_count": len(messages),
                "structured_output": structured_output.model_dump(mode="json"),
                "route_signal": "continue" if structured_output.passed else "reject",
            },
        )
        await self._telemetry_hook.emit(
            "qa_agent_execution_completed",
            {
                "agent": self._config.agent_name,
                "execution_id": str(request.execution_id),
                "status": result.status.value,
                "passed": structured_output.passed,
            },
        )
        self._logger.info("qa_agent_execution_completed", extra={"agent": self._config.agent_name})
        return result

    @classmethod
    def from_agent_definition(
        cls,
        agent: AgentDefinition,
        output_contract: OutputContract,
        model_client: AgentModelClient,
    ) -> "QAAgentRuntime":
        return cls(
            config=QARuntimeConfig(
                agent_name=agent.name,
                context_path=agent.context_path,
                repository_path=agent.context_path.parents[1],
                output_contract=output_contract,
            ),
            model_client=model_client,
        )

    async def _enrich_output(self, output: QAOutput, request: AgentExecutionRequest) -> QAOutput:
        output = await self._run_test_commands(output)
        output = await self._run_browser_sandbox(output, request)
        screenshots = list(output.screenshots)
        if not screenshots and output.bug_summaries:
            factory = ScreenshotPathFactory(self._config.evidence_output_path)
            step = BrowserAutomationStep(
                action=BrowserAction.SCREENSHOT,
                value=factory.create("qa-evidence"),
                description="Capture QA evidence screenshot.",
            )
            results = await self._browser_service.run((step,))
            for result in results:
                if result.screenshot_path:
                    screenshots.append(
                        ScreenshotEvidence(
                            name="QA Evidence",
                            path=result.screenshot_path,
                            description=result.message or "Screenshot evidence.",
                        )
                    )

        bug_summaries = []
        for bug in output.bug_summaries:
            if bug.severity:
                bug_summaries.append(bug)
                continue
            classification = await self._severity_classifier.classify(bug.title, bug.actual or "")
            bug_summaries.append(bug.model_copy(update={"severity": classification.severity}))

        return output.model_copy(
            update={
                "screenshots": tuple(screenshots),
                "bug_summaries": tuple(bug_summaries),
            }
        )

    async def _run_test_commands(self, output: QAOutput) -> QAOutput:
        reports: list[TestReport] = []
        logs: list[ExecutionLog] = list(output.execution_logs)
        findings: list[QualityFinding] = list(output.findings)
        passed = output.passed

        for report in output.test_reports:
            if not report.command:
                reports.append(report)
                continue
            try:
                result = await self._run_command(report.command)
            except Exception as exc:
                result = CommandResult(returncode=1, stdout="", stderr=str(exc))
            command_passed = result.returncode == 0
            passed = passed and command_passed
            logs.append(
                ExecutionLog(
                    message=f"$ {report.command}\n{result.stdout}\n{result.stderr}".strip(),
                    level="info" if command_passed else "error",
                    source="qa-test-runner",
                )
            )
            reports.append(
                report.model_copy(
                    update={
                        "passed": max(report.passed, 1 if command_passed else 0),
                        "failed": max(report.failed, 0 if command_passed else 1),
                        "details": (result.stdout + "\n" + result.stderr).strip() or report.details,
                    }
                )
            )
            if not command_passed:
                findings.append(
                    QualityFinding(
                        id=f"QA-CMD-{len(findings) + 1:03d}",
                        title=f"Test command failed: {report.name}",
                        severity=OutputSeverity.HIGH,
                        evidence=(result.stderr or result.stdout or "Command returned non-zero exit code.").strip(),
                        recommendation="Inspect the failing test output and fix the implementation before approval.",
                    )
                )

        return output.model_copy(
            update={
                "test_reports": tuple(reports),
                "execution_logs": tuple(logs),
                "findings": tuple(findings),
                "passed": passed,
            }
        )

    async def _run_browser_sandbox(self, output: QAOutput, request: AgentExecutionRequest) -> QAOutput:
        sandbox_steps = output.metadata.get("sandbox_steps") or request.metadata.get("sandbox_steps")
        if not sandbox_steps:
            return output
        steps = tuple(self._sandbox_step(item) for item in sandbox_steps)
        engine = SandboxBrowserEngine(str(output.metadata.get("sandbox_engine") or request.metadata.get("sandbox_engine") or SandboxBrowserEngine.PLAYWRIGHT))
        result = await self._sandbox_executor.execute(
            config=SandboxExecutionConfig(engine=engine),
            steps=steps,
            agent_name=self._config.agent_name,
            thread_id=str(request.metadata.get("thread_id", request.workflow_id)),
        )
        screenshots = list(output.screenshots)
        logs = list(output.execution_logs)
        findings = list(output.findings)
        for artifact in result.artifacts:
            if artifact.kind.value == "screenshot":
                screenshots.append(
                    ScreenshotEvidence(
                        name=artifact.name,
                        path=artifact.path.as_posix(),
                        description=artifact.description,
                    )
                )
        logs.extend(
            ExecutionLog(message=log, level="info", source="qa-browser-sandbox")
            for log in result.logs
        )
        if result.errors:
            findings.append(
                QualityFinding(
                    id=f"QA-BROWSER-{len(findings) + 1:03d}",
                    title="Browser automation failed",
                    severity=OutputSeverity.HIGH,
                    evidence="\n".join(result.errors),
                    recommendation="Review browser evidence and reproduce the failing interaction.",
                )
            )
        report = TestReport(
            name=f"{engine.value}-browser-automation",
            test_type="browser",
            passed=1 if not result.errors else 0,
            failed=0 if not result.errors else 1,
            details="\n".join(result.logs + result.errors),
        )
        return output.model_copy(
            update={
                "screenshots": tuple(screenshots),
                "execution_logs": tuple(logs),
                "findings": tuple(findings),
                "test_reports": output.test_reports + (report,),
                "passed": output.passed and not result.errors,
            }
        )

    async def _run_command(self, command: str) -> CommandResult:
        args = shlex.split(command, posix=False)
        if not args:
            raise ValueError("QA test command cannot be empty.")
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=self._config.repository_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return CommandResult(
            returncode=process.returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

    def _sandbox_step(self, payload: dict) -> SandboxStep:
        return SandboxStep(
            action=SandboxStepAction(str(payload["action"])),
            target=payload.get("target"),
            value=payload.get("value"),
            description=payload.get("description") or str(payload["action"]),
            metadata=payload.get("metadata", {}),
        )

    def _load_required_rules(self) -> tuple[dict[str, str], tuple[str, ...]]:
        rules: dict[str, str] = {}
        warnings: list[str] = []
        for file_name in self._config.required_rule_files:
            path = self._config.context_path / file_name
            if not path.exists():
                warnings.append(f"Required QA rule file missing: {file_name}")
                continue
            rules[file_name] = path.read_text(encoding="utf-8")
        return rules, tuple(warnings)

    def _failed_result(
        self,
        request: AgentExecutionRequest,
        errors: tuple[str, ...],
        warnings: tuple[str, ...],
    ) -> AgentExecutionResult:
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self._config.agent_name,
            status=AgentStatus.FAILED,
            errors=errors,
            metadata={"context_warnings": warnings},
        )
