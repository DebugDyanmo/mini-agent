import logging
from app.schemas import Task, TaskResult
from app.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


async def execute(tasks: list[Task]) -> tuple[str, str | None, list[TaskResult]]:
    """
    Execute tasks sequentially.

    Guardrail: if cancel_order fails, stop immediately and do NOT send email.

    Returns:
        (status, message, results)
        status  — "success" | "error"
        message — human-readable summary (None on full success)
        results — list of TaskResult for completed steps
    """
    results: list[TaskResult] = []

    for i, task in enumerate(tasks, start=1):
        logger.info(f"[ORCHESTRATOR] Step {i}/{len(tasks)}: executing '{task.action}' with {task.params}")

        tool = TOOL_REGISTRY.get(task.action)
        if tool is None:
            logger.error(f"[ORCHESTRATOR] Unknown tool '{task.action}' — aborting")
            return (
                "error",
                f"Unknown tool '{task.action}'.",
                results,
            )

        result = await tool(**task.params)
        logger.info(f"[ORCHESTRATOR] '{task.action}' result: {result}")

        results.append(TaskResult(action=task.action, status=result.get("status", "unknown"), details=result))

        # ── Guardrail ──────────────────────────────────────────────────────
        if task.action == "cancel_order" and result.get("status") == "failed":
            logger.warning("[ORCHESTRATOR] Guardrail triggered: cancellation failed — halting pipeline")
            return (
                "error",
                "Order cancellation failed. Email not sent.",
                results,
            )

    logger.info("[ORCHESTRATOR] All tasks completed successfully")
    return "success", None, results
