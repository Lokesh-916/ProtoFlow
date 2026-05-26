"""
crew.py — ProtoFlow Pipeline Orchestrator
─────────────────────────────────────────
Assembles the CrewAI crew from YAML config and runs the full pipeline.

Key responsibilities:
  - Load agents and tasks from config/agents.yaml and config/tasks.yaml
  - Fan out parallel stages (db, api, ui, auth) via asyncio.gather
  - Run the repair loop (max 3 attempts) after validation failures
  - Emit SSE events at every stage transition
  - Hold the pipeline on HITL events using asyncio.Event
  - Write structured logs via the logging module (remove debug calls later)

All LLM calls go through Groq via crewai LiteLLM routing. Temperature is set per-agent via
the LLM config in main.py (not in YAML, because YAML does not support
the full LLM config object).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Optional

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from compiler.tools.json_repair_tool import JSONRepairTool, extract_json
from compiler.tools.mermaid_generator_tool import MermaidGeneratorTool
from compiler.tools.schema_diff_tool import SchemaDiffTool
from compiler.tools.llm_cache import llm_cache

if TYPE_CHECKING:
    from compiler.schemas.contracts import (
        ValidationReport,
        RepairReport,
        FinalOutput,
    )

logger = logging.getLogger("protoflow.crew")

# ── Type alias for the SSE emitter callback ───────────────────────────────────
# crew.py calls this to push events to the session's SSE queue.
# Signature: async (session_id: str, event_type: str, payload: dict) -> None
SSEEmitter = Callable[[str, str, dict], Coroutine[Any, Any, None]]

import os
MAX_REPAIR_LOOPS = int(os.getenv("MAX_REPAIR_LOOPS", "3"))
HITL_TIMEOUT_SECONDS = int(os.getenv("HITL_TIMEOUT_SECONDS", "300"))


# ── CrewBase class ────────────────────────────────────────────────────────────

@CrewBase
class ProtoFlowCrew:
    """
    ProtoFlow compiler crew.
    Agents and tasks are loaded from config/agents.yaml and config/tasks.yaml.
    Python code here only wires tools and assembles the crew — no agent logic.
    """

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ── Shared tools (attached to agents that need them) ──────────────────────

    _json_repair_tool = JSONRepairTool()
    _schema_diff_tool = SchemaDiffTool()
    _mermaid_tool = MermaidGeneratorTool()

    # ── Agent factory methods ─────────────────────────────────────────────────

    @agent
    def intent_extractor(self) -> Agent:
        logger.debug("[crew] Building intent_extractor agent.")
        return Agent(
            config=self.agents_config["intent_extractor"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def system_architect(self) -> Agent:
        logger.debug("[crew] Building system_architect agent.")
        return Agent(
            config=self.agents_config["system_architect"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def db_schema_agent(self) -> Agent:
        logger.debug("[crew] Building db_schema_agent agent.")
        return Agent(
            config=self.agents_config["db_schema_agent"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def api_schema_agent(self) -> Agent:
        logger.debug("[crew] Building api_schema_agent agent.")
        return Agent(
            config=self.agents_config["api_schema_agent"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def ui_schema_agent(self) -> Agent:
        logger.debug("[crew] Building ui_schema_agent agent.")
        return Agent(
            config=self.agents_config["ui_schema_agent"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def auth_agent(self) -> Agent:
        logger.debug("[crew] Building auth_agent agent.")
        return Agent(
            config=self.agents_config["auth_agent"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def validator_agent(self) -> Agent:
        logger.debug("[crew] Building validator_agent agent.")
        return Agent(
            config=self.agents_config["validator_agent"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def repair_agent(self) -> Agent:
        logger.debug("[crew] Building repair_agent agent.")
        return Agent(
            config=self.agents_config["repair_agent"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def runtime_validator(self) -> Agent:
        logger.debug("[crew] Building runtime_validator agent.")
        return Agent(
            config=self.agents_config["runtime_validator"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def progress_logger(self) -> Agent:
        logger.debug("[crew] Building progress_logger agent.")
        return Agent(
            config=self.agents_config["progress_logger"],  # type: ignore[index]
            verbose=True,
        )

    # ── Task factory methods ──────────────────────────────────────────────────

    @task
    def task_extract_intent(self) -> Task:
        logger.debug("[crew] Building task_extract_intent.")
        return Task(
            config=self.tasks_config["task_extract_intent"],  # type: ignore[index]
        )

    @task
    def task_design_architecture(self) -> Task:
        logger.debug("[crew] Building task_design_architecture.")
        return Task(
            config=self.tasks_config["task_design_architecture"],  # type: ignore[index]
        )

    @task
    def task_generate_db_schema(self) -> Task:
        logger.debug("[crew] Building task_generate_db_schema.")
        return Task(
            config=self.tasks_config["task_generate_db_schema"],  # type: ignore[index]
        )

    @task
    def task_generate_api_schema(self) -> Task:
        logger.debug("[crew] Building task_generate_api_schema.")
        return Task(
            config=self.tasks_config["task_generate_api_schema"],  # type: ignore[index]
        )

    @task
    def task_generate_ui_schema(self) -> Task:
        logger.debug("[crew] Building task_generate_ui_schema.")
        return Task(
            config=self.tasks_config["task_generate_ui_schema"],  # type: ignore[index]
        )

    @task
    def task_generate_auth_schema(self) -> Task:
        logger.debug("[crew] Building task_generate_auth_schema.")
        return Task(
            config=self.tasks_config["task_generate_auth_schema"],  # type: ignore[index]
        )

    @task
    def task_validate_schemas(self) -> Task:
        logger.debug("[crew] Building task_validate_schemas.")
        return Task(
            config=self.tasks_config["task_validate_schemas"],  # type: ignore[index]
        )

    @task
    def task_repair_schemas(self) -> Task:
        logger.debug("[crew] Building task_repair_schemas.")
        return Task(
            config=self.tasks_config["task_repair_schemas"],  # type: ignore[index]
        )

    @task
    def task_validate_runtime(self) -> Task:
        logger.debug("[crew] Building task_validate_runtime.")
        return Task(
            config=self.tasks_config["task_validate_runtime"],  # type: ignore[index]
        )

    @task
    def task_log_progress(self) -> Task:
        logger.debug("[crew] Building task_log_progress.")
        return Task(
            config=self.tasks_config["task_log_progress"],  # type: ignore[index]
        )

    # ── Crew assembly ─────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """
        Assembles the ProtoFlow crew in sequential process.
        The parallel fan-out (db/api/ui/auth) is handled by the async
        pipeline runner below, not by CrewAI's process — CrewAI sequential
        is used as the base so task context passing works correctly.
        """
        logger.info("[crew] Assembling ProtoFlow crew (sequential process).")
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=False,  # No OpenAI embedder available; context passed via task context[]
        )


# ── Session state ─────────────────────────────────────────────────────────────

class PipelineSession:
    """
    Holds all mutable state for one pipeline run.
    One instance per session_id, stored in the session store in main.py.
    """

    def __init__(self, session_id: str, prompt: str, skip_hitl: bool = False) -> None:
        self.session_id = session_id
        self.prompt = prompt
        self.skip_hitl = skip_hitl
        self.started_at = time.monotonic()

        # HITL synchronisation
        self.hitl_event: asyncio.Event = asyncio.Event()
        self.hitl_answers: list[str] = []
        self.hitl_chosen_option: Optional[str] = None

        # Accumulated outputs
        self.intent: Optional[dict] = None
        self.architecture: Optional[dict] = None
        self.db_schema: Optional[dict] = None
        self.api_schema: Optional[dict] = None
        self.ui_schema: Optional[dict] = None
        self.auth_schema: Optional[dict] = None
        self.validation_report: Optional[dict] = None
        self.repair_report: Optional[dict] = None
        self.runtime_report: Optional[dict] = None
        self.log_output: Optional[dict] = None

        # Metrics
        self.repair_count: int = 0
        self.hitl_count: int = 0
        self.stage_latencies: dict[str, int] = {}
        self.total_tokens: int = 0

        # SSE event buffer for reconnection replay
        self.event_buffer: list[dict] = []
        self.sse_queue: asyncio.Queue = asyncio.Queue()

        logger.info(
            "[session:%s] Created. prompt_length=%d chars.", session_id, len(prompt)
        )

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started_at) * 1000)

    def resume_hitl(self, answers: list[str], chosen_option: Optional[str] = None) -> None:
        """Called by POST /clarify to unblock the pipeline."""
        logger.info(
            "[session:%s] HITL resumed. answers=%s chosen=%s",
            self.session_id, answers, chosen_option,
        )
        self.hitl_answers = answers
        self.hitl_chosen_option = chosen_option
        self.hitl_count += 1
        self.hitl_event.set()


# ── Async pipeline runner ─────────────────────────────────────────────────────

async def _emit(session: PipelineSession, event_type: str, payload: dict) -> None:
    """
    Push an SSE event onto the session queue and into the replay buffer.
    Logs every emission so you can trace the exact event sequence.
    """
    event = {"event": event_type, "session_id": session.session_id, **payload}
    session.event_buffer.append(event)
    await session.sse_queue.put(event)
    logger.debug(
        "[session:%s] SSE emitted. event=%s keys=%s",
        session.session_id, event_type, list(payload.keys()),
    )


async def _wait_for_hitl(
    session: PipelineSession,
    stage: str,
    trigger_reason: str,
    questions: list[str],
    options: Optional[list[str]] = None,
    timeout_seconds: int = HITL_TIMEOUT_SECONDS,
) -> list[str]:
    """
    Emit a hitl_required event, then block until POST /clarify sets the event.
    Returns the answers list.
    """
    if getattr(session, 'skip_hitl', False):
        logger.info("[session:%s] HITL skipped (eval mode).", session.session_id)
        return []

    logger.info(
        "[session:%s] HITL required. stage=%s reason=%s questions=%s",
        session.session_id, stage, trigger_reason, questions,
    )
    session.hitl_event.clear()
    session.hitl_answers = []

    await _emit(session, "hitl_required", {
        "stage": stage,
        "trigger_reason": trigger_reason,
        "questions": questions,
        "options": options,
        "timeout_seconds": timeout_seconds,
    })

    try:
        await asyncio.wait_for(session.hitl_event.wait(), timeout=timeout_seconds)
        logger.info(
            "[session:%s] HITL answered. answers=%s",
            session.session_id, session.hitl_answers,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[session:%s] HITL timed out after %ds. Proceeding with empty answers.",
            session.session_id, timeout_seconds,
        )

    return session.hitl_answers


async def _run_stage(
    session: PipelineSession,
    stage_name: str,
    model: str,
    coro: Coroutine,
) -> Any:
    """
    Wrap a single pipeline stage coroutine with:
      - stage_update running event
      - timing
      - stage_update complete/failed event
      - LLM cache stats logging
    """
    logger.info("[session:%s] Stage START: %s", session.session_id, stage_name)
    if getattr(session, 'tpm_limit_hit', False):
        logger.warning("[session:%s] Skipping stage %s due to prior TPM limit hit.", session.session_id, stage_name)
        await _emit(session, "stage_update", {
            "stage": stage_name, "status": "failed", "model": model, "latency_ms": 0,
            "output_summary": "Bypassed due to Groq TPM limits."
        })
        return {}
    t0 = time.monotonic()

    await _emit(session, "stage_update", {
        "stage": stage_name,
        "status": "running",
        "model": model,
        "latency_ms": 0,
        "output_summary": "",
    })

    try:
        result = await coro
        latency_ms = int((time.monotonic() - t0) * 1000)
        session.stage_latencies[stage_name] = latency_ms

        # Summarise output for SSE (first 120 chars of JSON)
        summary = ""
        if result:
            try:
                summary = json.dumps(result)[:120]
            except Exception:
                summary = str(result)[:120]

        await _emit(session, "stage_update", {
            "stage": stage_name,
            "status": "complete",
            "model": model,
            "latency_ms": latency_ms,
            "output_summary": summary,
        })

        logger.info(
            "[session:%s] Stage DONE: %s latency=%dms cache_stats=%s",
            session.session_id, stage_name, latency_ms, llm_cache.stats(),
        )
        return result

    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        session.stage_latencies[stage_name] = latency_ms
        if "Request size exceeds TPM limit" in str(exc) or "TPM" in str(exc):
            logger.error("[session:%s] TPM limit hit in stage %s. Bypassing.", session.session_id, stage_name)
            setattr(session, 'tpm_limit_hit', True)
            await _emit(session, "stage_update", {
                "stage": stage_name, "status": "failed", "model": model, "latency_ms": latency_ms,
                "output_summary": f"Bypassed: {exc}"
            })
            return {}
        logger.error(
            "[session:%s] Stage FAILED: %s error=%s latency=%dms",
            session.session_id, stage_name, exc, latency_ms, exc_info=True,
        )
        await _emit(session, "stage_update", {
            "stage": stage_name,
            "status": "failed",
            "model": model,
            "latency_ms": latency_ms,
            "output_summary": f"ERROR: {exc}",
        })
        raise


async def run_pipeline(session: PipelineSession) -> None:
    """
    Full async pipeline runner.

    Stage order:
      1. intent_extraction  (sequential, HITL always-on)
      2. architecture       (async)
      3. db + api + ui + auth  (parallel fan-out via asyncio.gather)
      4. validation         (sequential)
      5. repair loop        (sequential, max MAX_REPAIR_LOOPS)
      6. runtime_validation (sequential)
      7. logging            (async)
      8. pipeline_complete  SSE event
    """
    logger.info(
        "[session:%s] Pipeline START. prompt=%r",
        session.session_id, session.prompt[:80],
    )

    crew_instance = ProtoFlowCrew()

    # ── Read raw YAML once so we can look up agent names by task name ─────────
    import yaml as _yaml
    _yaml_path = os.path.join(os.path.dirname(__file__), "config", "tasks.yaml")
    with open(_yaml_path, "r", encoding="utf-8") as _f:
        _raw_tasks_yaml: dict = _yaml.safe_load(_f)
    logger.debug("[crew] Loaded raw tasks YAML. keys=%s", list(_raw_tasks_yaml.keys()))

    # ── Helper: kick off a single CrewAI task and parse JSON output ───────────
    async def _kickoff_task(task_name: str, inputs: dict) -> dict:
        """
        Run a single task by creating a temporary single-task Crew.
        Reads agent name from raw YAML (not from instantiated Task objects)
        to avoid the 'attribute name must be string, not Agent' error.
        """
        logger.debug(
            "[session:%s] _kickoff_task: %s inputs_keys=%s",
            session.session_id, task_name, list(inputs.keys()),
        )

        # Get agent name string from raw YAML dict
        raw_task_def = _raw_tasks_yaml.get(task_name, {})
        agent_name: str = raw_task_def.get("agent", "")
        logger.debug(
            "[session:%s] _kickoff_task: task=%s agent_name=%r",
            session.session_id, task_name, agent_name,
        )

        # Instantiate agent via the @agent method on the crew class
        agent = None
        if agent_name and isinstance(agent_name, str):
            agent_creator = getattr(crew_instance, agent_name, None)
            if callable(agent_creator):
                agent = agent_creator()
                logger.debug("[session:%s] Agent instantiated: %s", session.session_id, agent_name)
            else:
                logger.warning(
                    "[session:%s] No @agent method found for name=%r on ProtoFlowCrew",
                    session.session_id, agent_name,
                )
        else:
            logger.warning(
                "[session:%s] agent_name is not a string: %r (type=%s). "
                "Check tasks.yaml for task '%s'.",
                session.session_id, agent_name, type(agent_name).__name__, task_name,
            )

        # Instantiate task via the @task method
        task_creator = getattr(crew_instance, task_name, None)
        if not callable(task_creator):
            raise ValueError(f"No @task method found for '{task_name}' on ProtoFlowCrew")
        task_obj = task_creator()

        # Assign agent to task (overrides YAML assignment for single-task crew)
        if agent:
            task_obj.agent = agent

        temp_crew = Crew(
            agents=[agent] if agent else [],
            tasks=[task_obj],
            verbose=True,
            memory=False,  # No OpenAI embedder; avoids ChromaDB CHROMA_OPENAI_API_KEY error
        )

        # Run in a thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        
        import re
        max_retries = 5
        result = None
        for attempt in range(max_retries):
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: temp_crew.kickoff(inputs=inputs),
                )
                break  # Success
            except Exception as e:
                err_str = str(e)
                if "RateLimitError" in type(e).__name__ or "rate_limit" in err_str.lower() or "rate limit reached" in err_str.lower():
                    if "Request too large" in err_str:
                        raise ValueError(f"Request size exceeds TPM limit: {err_str}")
                    if attempt < max_retries - 1:
                        # Parse "Please try again in 21.665s." or fallback to 30s
                        wait_time = 30.0
                        match = re.search(r'try again in (?:(\d+)m)?([\d\.]+)s', err_str)
                        if match:
                            m_str = match.group(1)
                            s_str = match.group(2)
                            minutes = int(m_str) if m_str else 0
                            seconds = float(s_str)
                            wait_time = (minutes * 60) + seconds + 2.0  # 2s buffer
                        logger.warning(
                            "[session:%s] Rate limit hit for %s. Sleeping %.1fs before attempt %d. Error: %s",
                            session.session_id, task_name, wait_time, attempt + 2, err_str.split('"message":')[1].split(',"type"')[0] if '"message":' in err_str else err_str[:100]
                        )
                        await asyncio.sleep(wait_time)
                        continue
                # If it's not a rate limit error, or we're out of retries, raise it
                raise e
        
        # Token extraction
        if hasattr(result, 'token_usage'):
            usage = result.token_usage
            if hasattr(usage, 'total_tokens'):
                session.total_tokens += usage.total_tokens
            elif isinstance(usage, dict):
                session.total_tokens += usage.get('total_tokens', 0)

        raw = result.raw if hasattr(result, "raw") else str(result)
        logger.debug(
            "[session:%s] _kickoff_task raw output length: %d chars",
            session.session_id, len(raw),
        )
        parsed = extract_json(raw)
        if not isinstance(parsed, dict):
            logger.error(
                "[session:%s] LLM output parsed as %s instead of dict. Coercing to empty dict.",
                session.session_id, type(parsed).__name__
            )
            return {}
        return parsed

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 1 — Intent Extraction (always HITL)
    # ─────────────────────────────────────────────────────────────────────────
    async def _stage_intent() -> dict:
        result = await _kickoff_task(
            "task_extract_intent",
            {"user_prompt": session.prompt},
        )
        confidence = result.get("confidence", 1.0)
        logger.info(
            "[session:%s] Intent extracted. confidence=%.2f assumptions=%d",
            session.session_id, confidence, len(result.get("assumptions", [])),
        )

        # HITL is always-on — build question based on confidence
        if confidence < 0.75:
            questions = [
                "What is the primary purpose of this application?",
                "Who are the main user types and what can each do?",
                "Are there any premium or paid features?",
            ]
            trigger = "low_confidence"
        else:
            questions = [
                f"I'm assuming {result.get('app_type', 'a web app')} with "
                f"JWT auth and a REST API — does that work for you?"
            ]
            trigger = "always_on"

        answers = await _wait_for_hitl(
            session, "intent_extraction", trigger, questions
        )
        result["clarifications_received"] = answers
        session.intent = result
        return result

    session.intent = await _run_stage(
        session, "intent_extraction",
        "groq/llama-3.3-70b-versatile", _stage_intent()
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 2 — Architecture Design
    # ─────────────────────────────────────────────────────────────────────────
    async def _stage_architecture() -> dict:
        result = await _kickoff_task(
            "task_design_architecture",
            {
                "user_prompt": session.prompt,
                "intent_schema": json.dumps(session.intent),
            },
        )
        session.architecture = result
        logger.info(
            "[session:%s] Architecture designed. entities=%d relations=%d",
            session.session_id,
            len(result.get("entities", [])),
            len(result.get("relations", [])),
        )
        return result

    session.architecture = await _run_stage(
        session, "architecture_design",
        "groq/llama-3.3-70b-versatile", _stage_architecture()
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 3 — Parallel fan-out: DB + API + UI + Auth
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("[session:%s] Starting parallel schema generation.", session.session_id)

    arch_json = json.dumps(session.architecture or {}, separators=(',', ':'))

    async def _stage_db() -> dict:
        result = await _kickoff_task(
            "task_generate_db_schema",
            {"architecture_schema": arch_json, "user_prompt": session.prompt},
        )
        session.db_schema = result
        logger.info(
            "[session:%s] DB schema generated. tables=%d",
            session.session_id, len(result.get("tables", [])),
        )
        return result

    async def _stage_api() -> dict:
        result = await _kickoff_task(
            "task_generate_api_schema",
            {
                "architecture_schema": arch_json,
                "db_schema": json.dumps(session.db_schema or {}, separators=(',', ':')),
                "user_prompt": session.prompt,
            },
        )
        session.api_schema = result
        logger.info(
            "[session:%s] API schema generated. endpoints=%d",
            session.session_id, len(result.get("endpoints", [])),
        )
        return result

    async def _stage_ui() -> dict:
        result = await _kickoff_task(
            "task_generate_ui_schema",
            {
                "architecture_schema": arch_json,
                "api_schema": json.dumps(session.api_schema or {}),
                "user_prompt": session.prompt,
            },
        )
        session.ui_schema = result
        logger.info(
            "[session:%s] UI schema generated. pages=%d",
            session.session_id, len(result.get("pages", [])),
        )
        return result

    async def _stage_auth() -> dict:
        result = await _kickoff_task(
            "task_generate_auth_schema",
            {
                "architecture_schema": arch_json,
                "ui_schema": json.dumps(session.ui_schema or {}),
                "user_prompt": session.prompt,
            },
        )
        session.auth_schema = result
        logger.info(
            "[session:%s] Auth schema generated. roles=%s",
            session.session_id, result.get("roles", []),
        )
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # STAGES 3-6 — Sequential Execution (formerly parallel fan-out)
    # We run these sequentially to avoid hitting Groq's 12,000 TPM rate limit
    # ─────────────────────────────────────────────────────────────────────────
    async def _run_schema_stage(stage_name: str, task_coro, model: str) -> dict:
        await _emit(session, "stage_update", {
            "stage": stage_name, "status": "running",
            "model": model, "latency_ms": 0, "output_summary": "",
        })
        t_start = time.monotonic()
        result = await task_coro()
        latency_ms = int((time.monotonic() - t_start) * 1000)
        await _emit(session, "stage_update", {
            "stage": stage_name, "status": "complete",
            "model": model, "latency_ms": latency_ms,
            "output_summary": json.dumps(result)[:120],
        })
        return result

    db_result = await _run_schema_stage("db_schema", _stage_db, "groq/llama-3.3-70b-versatile")
    api_result = await _run_schema_stage("api_schema", _stage_api, "groq/llama-3.3-70b-versatile")
    ui_result = await _run_schema_stage("ui_schema", _stage_ui, "groq/llama-3.3-70b-versatile")
    auth_result = await _run_schema_stage("auth_schema", _stage_auth, "groq/llama-3.3-70b-versatile")

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 4 + 5 — Validation + Repair loop
    # ─────────────────────────────────────────────────────────────────────────
    all_schemas_json = json.dumps({
        "db_schema": session.db_schema,
        "api_schema": session.api_schema,
        "ui_schema": session.ui_schema,
        "auth_schema": session.auth_schema,
    }, separators=(',', ':'))

    for attempt in range(1, MAX_REPAIR_LOOPS + 1):
        logger.info(
            "[session:%s] Validation attempt %d/%d.",
            session.session_id, attempt, MAX_REPAIR_LOOPS,
        )

        async def _stage_validate() -> dict:
            result = await _kickoff_task(
                "task_validate_schemas",
                {
                    "all_schemas": all_schemas_json,
                    "user_prompt": session.prompt,
                },
            )
            session.validation_report = result
            is_valid = result.get("is_valid", False)
            error_count = len(result.get("errors", []))
            logger.info(
                "[session:%s] Validation result: is_valid=%s errors=%d warnings=%d",
                session.session_id, is_valid, error_count,
                len(result.get("warnings", [])),
            )
            return result

        validation = await _run_stage(
            session, "validation",
            "groq/llama-3.3-70b-versatile", _stage_validate()
        )

        if validation.get("is_valid", False):
            logger.info(
                "[session:%s] Schemas valid after attempt %d.", session.session_id, attempt
            )
            break

        errors = validation.get("errors", [])
        logger.warning(
            "[session:%s] Validation FAILED. %d errors. Triggering repair (attempt %d).",
            session.session_id, len(errors), attempt,
        )

        await _emit(session, "stage_update", {
            "stage": "validation",
            "status": "repair_triggered",
            "model": "groq/llama-3.3-70b-versatile",
            "latency_ms": session.stage_latencies.get("validation", 0),
            "output_summary": f"{len(errors)} errors found",
            "conflicts": [e.get("description", "") for e in validation.get("conflicts", [])],
        })

        # If same errors persist after 2 attempts, escalate to HITL
        if attempt >= 2:
            unresolved = [e.get("description", str(e)) for e in errors[:3]]
            logger.warning(
                "[session:%s] Repair attempt %d — escalating to HITL. unresolved=%s",
                session.session_id, attempt, unresolved,
            )
            await _wait_for_hitl(
                session,
                stage="repair",
                trigger_reason="repair_failed",
                questions=[
                    f"Repair attempt {attempt} could not fix: {err}. "
                    f"How should this be resolved?"
                    for err in unresolved
                ],
                timeout_seconds=HITL_TIMEOUT_SECONDS,
            )

        async def _stage_repair() -> dict:
            result = await _kickoff_task(
                "task_repair_schemas",
                {
                    "validation_report": json.dumps(session.validation_report),
                    "all_schemas": all_schemas_json,
                    "repair_attempt_number": attempt,
                    "user_prompt": session.prompt,
                },
            )
            session.repair_report = result
            session.repair_count += 1
            logger.info(
                "[session:%s] Repair complete. repairs=%d unresolved=%d",
                session.session_id,
                len(result.get("repairs", [])),
                len(result.get("unresolved_errors", [])),
            )
            # Merge updated schemas back into session
            updated = result.get("updated_schemas", {})
            if "db_schema" in updated:
                session.db_schema = updated["db_schema"]
                logger.debug("[session:%s] db_schema updated by repair.", session.session_id)
            if "api_schema" in updated:
                session.api_schema = updated["api_schema"]
                logger.debug("[session:%s] api_schema updated by repair.", session.session_id)
            if "ui_schema" in updated:
                session.ui_schema = updated["ui_schema"]
                logger.debug("[session:%s] ui_schema updated by repair.", session.session_id)
            if "auth_schema" in updated:
                session.auth_schema = updated["auth_schema"]
                logger.debug("[session:%s] auth_schema updated by repair.", session.session_id)
            # Rebuild all_schemas_json for next validation pass
            return result

        await _run_stage(
            session, "repair",
            "groq/llama-3.3-70b-versatile", _stage_repair()
        )
        if getattr(session, 'tpm_limit_hit', False):
            break

        # Rebuild for next validation pass
        all_schemas_json = json.dumps({
            "db_schema": session.db_schema,
            "api_schema": session.api_schema,
            "ui_schema": session.ui_schema,
            "auth_schema": session.auth_schema,
        }, separators=(',', ':'))

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 6 — Runtime Validation
    # ─────────────────────────────────────────────────────────────────────────
    async def _stage_runtime() -> dict:
        result = await _kickoff_task(
            "task_validate_runtime",
            {
                "all_schemas": all_schemas_json,
                "validation_report": json.dumps(session.validation_report),
                "user_prompt": session.prompt,
            },
        )
        session.runtime_report = result
        viable = result.get("execution_viable", False)
        logger.info(
            "[session:%s] Runtime validation: viable=%s flows=%d blocking=%d",
            session.session_id, viable,
            len(result.get("simulated_flows", [])),
            len(result.get("blocking_issues", [])),
        )
        return result

    await _run_stage(
        session, "runtime_validation",
        "groq/llama-3.3-70b-versatile", _stage_runtime()
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 7 — Progress Logging + Mermaid generation
    # ─────────────────────────────────────────────────────────────────────────
    async def _stage_logging() -> dict:
        result = await _kickoff_task(
            "task_log_progress",
            {
                "all_schemas": all_schemas_json,
                "validation_report": json.dumps(session.validation_report),
                "runtime_report": json.dumps(session.runtime_report),
                "stage_latencies": json.dumps(session.stage_latencies),
                "repair_count": session.repair_count,
                "hitl_count": session.hitl_count,
                "user_prompt": session.prompt,
                "session_id": session.session_id,
            },
        )
        session.log_output = result
        logger.info(
            "[session:%s] Logging complete. mermaid keys=%s",
            session.session_id,
            [k for k in result if "mermaid" in k],
        )
        # Stream log entries as SSE
        for entry in result.get("log_entries", []):
            await _emit(session, "log_update", {
                "content": json.dumps(entry) if isinstance(entry, dict) else str(entry),
            })
        return result

    await _run_stage(
        session, "logging",
        "groq/llama-3.3-70b-versatile", _stage_logging()
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 8 — pipeline_complete SSE event
    # ─────────────────────────────────────────────────────────────────────────
    total_ms = session.elapsed_ms()
    log_out = session.log_output or {}

    mermaid = {
        "pipeline_flow": log_out.get("mermaid_pipeline", ""),
        "er_diagram": log_out.get("mermaid_er", ""),
        "api_sequence": log_out.get("mermaid_sequence", ""),
    }

    final_schema = {
        "session_id": session.session_id,
        "prompt": session.prompt,
        "intent": session.intent,
        "architecture": session.architecture,
        "db_schema": session.db_schema,
        "api_schema": session.api_schema,
        "ui_schema": session.ui_schema,
        "auth_schema": session.auth_schema,
        "validation_report": session.validation_report,
        "repair_report": session.repair_report,
        "runtime_report": session.runtime_report,
    }

    from compiler.schemas.contracts import FinalOutput
    try:
        FinalOutput.model_validate(final_schema)
        logger.info("[session:%s] FinalOutput Pydantic validation passed.", session.session_id)
    except Exception as e:
        logger.warning("[session:%s] FinalOutput Pydantic validation failed (non-blocking): %s", session.session_id, e)

    await _emit(session, "pipeline_complete", {
        "total_latency_ms": total_ms,
        "total_tokens": session.total_tokens,
        "repair_count": session.repair_count,
        "hitl_count": session.hitl_count,
        "final_schema": final_schema,
        "mermaid_diagrams": mermaid,
        "assumptions": session.intent.get("assumptions", []) if session.intent else [],
        "conflicts": session.validation_report.get("conflicts", []) if session.validation_report else [],
    })

    # Signal SSE stream to close
    await session.sse_queue.put(None)

    logger.info(
        "[session:%s] Pipeline COMPLETE. total_ms=%d repairs=%d hitl=%d cache=%s",
        session.session_id, total_ms, session.repair_count,
        session.hitl_count, llm_cache.stats(),
    )
