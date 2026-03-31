import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from app.schemas import AgentRequest, AgentResponse
from app.planner import plan
from app.orchestrator import execute

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Mini Agent Orchestrator",
    description="Converts natural language requests into structured tasks and executes them.",
    version="1.0.0",
)


@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(request: AgentRequest):
    logger.info(f"[API] Received query: '{request.query}'")

    # 1. Plan
    tasks = plan(request.query)
    if not tasks:
        raise HTTPException(status_code=422, detail="Could not extract any valid tasks from the query.")

    # 2. Execute
    status, message, results = await execute(tasks)

    logger.info(f"[API] Execution complete — status={status}")

    return AgentResponse(
        query=request.query,
        plan=tasks,
        results=results,
        status=status,
        message=message,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
