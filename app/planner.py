import re
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from app.schemas import Task

load_dotenv()

logger = logging.getLogger(__name__)

# ── Function definitions for OpenAI function calling ─────────────────────────

FUNCTIONS = [
    {
        "name": "cancel_order",
        "description": "Cancel a customer order by order ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The numeric order ID to cancel, e.g. '9921'",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email notification to the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Recipient email address.",
                },
                "message": {
                    "type": "string",
                    "description": "Email body content to send to the customer.",
                },
            },
            "required": ["email", "message"],
        },
    },
]


# ── OpenAI function-calling planner ──────────────────────────────────────────

def _openai_plan(query: str) -> Optional[list[Task]]:
    """
    Use OpenAI function calling to extract structured tasks from the query.
    The model will call one or more functions; we collect all calls as tasks.
    Returns None on any failure so the mock planner can take over.
    """
    try:
        import openai

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("[PLANNER] OPENAI_API_KEY not set — skipping LLM planner")
            return None

        client = openai.OpenAI(api_key=api_key)

        logger.info("[PLANNER] Calling OpenAI with function calling...")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a task planner. Given a user request, call the appropriate "
                        "functions to fulfil it. You may call multiple functions in sequence. "
                        "Always extract order IDs and email addresses precisely from the request."
                    ),
                },
                {"role": "user", "content": query},
            ],
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0,
        )

        tasks: list[Task] = []
        message = response.choices[0].message

        # Collect the first function call from the response
        if message.function_call:
            name = message.function_call.name
            params = json.loads(message.function_call.arguments)
            tasks.append(Task(action=name, params=params))
            logger.info(f"[PLANNER] LLM function call: {name}({params})")

            # If the model called one function, do a follow-up to get remaining calls
            # by feeding the result back and asking to continue
            if len(tasks) < len(FUNCTIONS):
                tasks.extend(_continue_function_calls(client, query, message, tasks))

        if not tasks:
            logger.warning("[PLANNER] OpenAI returned no function calls")
            return None

        logger.info(f"[PLANNER] LLM produced {len(tasks)} task(s): {[t.action for t in tasks]}")
        return tasks

    except Exception as exc:
        logger.warning(f"[PLANNER] LLM planner failed ({exc}) — falling back to mock")
        return None


def _continue_function_calls(client, query: str, first_message, existing_tasks: list[Task]) -> list[Task]:
    """
    Feed the first function call result back to the model and collect any
    additional function calls it wants to make (e.g. send_email after cancel_order).
    """
    additional: list[Task] = []
    try:
        # Simulate a successful result for the first call so the model continues
        first_task = existing_tasks[0]
        simulated_result = json.dumps({"status": "success", **first_task.params})

        follow_up = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a task planner. Given a user request, call the appropriate "
                        "functions to fulfil it. You may call multiple functions in sequence."
                    ),
                },
                {"role": "user", "content": query},
                first_message,  # assistant's first function call
                {
                    "role": "function",
                    "name": first_task.action,
                    "content": simulated_result,
                },
            ],
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0,
        )

        follow_msg = follow_up.choices[0].message
        if follow_msg.function_call:
            name = follow_msg.function_call.name
            params = json.loads(follow_msg.function_call.arguments)
            additional.append(Task(action=name, params=params))
            logger.info(f"[PLANNER] LLM follow-up function call: {name}({params})")

    except Exception as exc:
        logger.warning(f"[PLANNER] Follow-up function call failed ({exc})")

    return additional


# ── Mock / regex planner ──────────────────────────────────────────────────────

def _mock_plan(query: str) -> list[Task]:
    """Regex-based fallback planner."""
    tasks: list[Task] = []

    order_match = re.search(r"#(\d+)", query)
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", query)

    if order_match:
        order_id = order_match.group(1)
        tasks.append(Task(action="cancel_order", params={"order_id": order_id}))
        logger.info(f"[PLANNER] Mock: found order_id={order_id}")

    if email_match:
        email = email_match.group(0)
        message = (
            f"Your order #{order_match.group(1)} has been successfully cancelled."
            if order_match
            else "Your request has been processed."
        )
        tasks.append(Task(action="send_email", params={"email": email, "message": message}))
        logger.info(f"[PLANNER] Mock: found email={email}")

    if not tasks:
        logger.warning("[PLANNER] Mock planner could not extract any tasks from query")

    return tasks


# ── Public interface ──────────────────────────────────────────────────────────

def plan(query: str) -> list[Task]:
    """
    Try OpenAI function calling first; fall back to regex mock if unavailable.
    Validates all tasks against TOOL_REGISTRY before returning.
    """
    from app.tools import TOOL_REGISTRY

    logger.info(f"[PLANNER] Planning query: '{query}'")

    tasks = _openai_plan(query) or _mock_plan(query)

    # Validate — drop tasks with unknown actions
    valid = [t for t in tasks if t.action in TOOL_REGISTRY]
    dropped = len(tasks) - len(valid)
    if dropped:
        logger.warning(f"[PLANNER] Dropped {dropped} task(s) with unknown actions")

    logger.info(f"[PLANNER] Final plan: {[t.action for t in valid]}")
    return valid
