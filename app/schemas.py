from pydantic import BaseModel, EmailStr
from typing import Any, Optional


class AgentRequest(BaseModel):
    query: str


class Task(BaseModel):
    action: str
    params: dict[str, Any]


class TaskResult(BaseModel):
    action: str
    status: str
    details: dict[str, Any]


class AgentResponse(BaseModel):
    query: str
    plan: list[Task]
    results: list[TaskResult] | None = None
    status: str
    message: Optional[str] = None
