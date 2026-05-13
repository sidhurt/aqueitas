from pydantic import BaseModel, Field
from typing import Optional

class LogRequest(BaseModel):
    project_name: str = Field(..., description="Name of the repository this log belongs to.")
    git_diff: str = Field(..., description="The raw Git diff of the code changes.")
    commit_msg: Optional[str] = Field(None, description="Optional commit message to provide additional context.")

class LogResponse(BaseModel):
    status: str
    message: str
    log_id: str
