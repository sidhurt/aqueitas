from pydantic import BaseModel, Field
from typing import Optional, List

class LogRequest(BaseModel):
    project_name: str = Field(..., description="Name of the repository this log belongs to.")
    git_diff: str = Field(..., description="The raw Git diff of the code changes.")
    commit_msg: Optional[str] = Field(None, description="Optional commit message to provide additional context.")
    commit_hash: Optional[str] = Field(None, description="Full SHA of the commit; enables deduplication and safe replays.")
    author: Optional[str] = Field(None, description="Commit author, e.g. 'Name <email>'.")
    committed_at: Optional[str] = Field(None, description="ISO-8601 committer date of the commit.")

class LogResponse(BaseModel):
    status: str
    message: str
    log_id: str

class SourceReference(BaseModel):
    log_id: str
    project_name: str
    created_at: Optional[str] = Field(None, description="When this memory was ingested.")
    excerpt: Optional[str] = Field(None, description="Leading excerpt of the underlying record, for grounding.")

class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query to search the vault.")
    limit: int = Field(5, description="Maximum number of logs to retrieve.")

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceReference]
