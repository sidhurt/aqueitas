from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum

class LogRequest(BaseModel):
    project_name: str = Field(..., description="Name of the repository this log belongs to.")
    git_diff: str = Field(..., description="The raw Git diff of the code changes.")
    commit_msg: Optional[str] = Field(None, description="Optional commit message to provide additional context.")

class LogResponse(BaseModel):
    status: str
    message: str
    log_id: str

class SourceReference(BaseModel):
    log_id: str
    project_name: str

class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query to search the vault.")
    limit: int = Field(5, description="Maximum number of logs to retrieve.")

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceReference]

# --- Mobile Dispatch API Models ---

class MobileDispatchRequest(BaseModel):
    mission_prompt: str = Field(..., description="The complex task or prompt from the mobile client.")
    priority_level: Optional[str] = Field(None, description="Optional priority level for the mission.")

class MobileDispatchResponse(BaseModel):
    status: str = Field(..., description="Status of the dispatch request.")
    mission_id: str = Field(..., description="The generated UUID for tracking this specific mission.")

# --- Atlas Callback API Models ---

class AtlasCallbackStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class AtlasCallbackRequest(BaseModel):
    mission_id: str = Field(..., description="The string tracking ID of the completed mission.")
    status: AtlasCallbackStatus = Field(..., description="Outcome of the external computation.")
    result_payload: Dict[str, Any] = Field(..., description="The JSON results or error details from the Atlas node.")
