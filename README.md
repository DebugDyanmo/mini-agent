# Mini Agent Orchestrator

A production-quality agentic workflow system built with FastAPI. It converts natural language requests into structured tasks and executes them reliably using async tools — with guardrails, LLM fallback, and clean modular architecture.

---

## Architecture

```
User Request (POST /agent)
        │
        ▼
  ┌─────────────┐
  │   Planner   │  Converts NL query → list of Tasks
  │  (LLM/Mock) │  OpenAI first, regex fallback on failure
  └──────┬──────┘
         │  [ {action, params}, ... ]
         ▼
  ┌──────────────┐
  │ Orchestrator │  Executes tasks sequentially (async)
  │              │  Applies guardrails between steps
  └──────┬───────┘
         │
    ┌────┴────┐
    ▼         ▼
cancel_order  send_email
  (Tool)      (Tool)
```

### Components

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app, `/agent` endpoint |
| `planner.py` | NL → Task list (OpenAI + regex fallback) |
| `orchestrator.py` | Sequential async execution + guardrails |
| `tools.py` | Async tool implementations + registry |
| `schemas.py` | Pydantic request/response models |

---

## Async Execution

All tools are `async` functions. The orchestrator `await`s each tool in sequence, so the event loop is never blocked. Adding concurrent execution (e.g. `asyncio.gather`) for independent tasks is straightforward — just swap the sequential loop in `orchestrator.py`.

---

## Guardrails

If `cancel_order` returns `"status": "failed"`, the orchestrator **stops immediately** and does not call `send_email`. The response will be:

```json
{
  "status": "error",
  "message": "Order cancellation failed. Email not sent."
}
```

This prevents sending a success email when the underlying operation failed.

---

## LLM Failure Handling

1. Planner calls OpenAI with a strict system prompt requesting JSON only.
2. If `OPENAI_API_KEY` is missing, the API call throws, or JSON parsing fails — the planner automatically falls back to the regex mock parser.
3. After planning, all tasks are validated against the `TOOL_REGISTRY`. Unknown actions are dropped before execution.

---

## Setup

```bash
cd mini_agent
python -m venv .venv
source .venv/bin/activate     
pip install -r requirements.txt
```

Optional — create a `.env` file for OpenAI:

```
OPENAI_API_KEY=sk-...
```

Run the server:

```bash
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

---

## Example Request / Response

**Request**
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Cancel my order #9921 and email me at user@example.com"}'
```

**Success Response**
```json
{
  "query": "Cancel my order #9921 and email me at user@example.com",
  "plan": [
    {"action": "cancel_order", "params": {"order_id": "9921"}},
    {"action": "send_email",   "params": {"email": "user@example.com", "message": "Your order #9921 has been successfully cancelled."}}
  ],
  "results": [
    {"action": "cancel_order", "status": "success", "details": {"status": "success", "order_id": "9921"}},
    {"action": "send_email",   "status": "sent",    "details": {"status": "sent", "email": "user@example.com", "message": "..."}}
  ],
  "status": "success",
  "message": null
}
```

**Failure Response (20% chance)**
```json
{
  "query": "Cancel my order #9921 and email me at user@example.com",
  "plan": [...],
  "results": [
    {"action": "cancel_order", "status": "failed", "details": {"status": "failed", "order_id": "9921"}}
  ],
  "status": "error",
  "message": "Order cancellation failed. Email not sent."
}
```

---

## Extending the System

To add a new tool:

1. Add an `async def my_tool(...)` function in `tools.py`
2. Register it in `TOOL_REGISTRY`
3. Update the OpenAI system prompt in `planner.py` to include the new action
4. The orchestrator picks it up automatically — no other changes needed
