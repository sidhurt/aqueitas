import logging
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import db
from models import LogRequest, LogResponse, QueryRequest, QueryResponse, SourceReference
from services.embedding import extract_context, generate_embedding
from services.retrieval import search_vault, synthesize_answer

import uuid
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.aws_dispatcher import AtlasDispatcher

class WorkerTelemetry(BaseModel):
    intent_id: str
    status: str
    message: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()

app = FastAPI(
    title="Aqueitas Brain",
    description="The Intelligence Layer of the Aqueitas EngOS",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/log", response_model=LogResponse)
async def ingest_log(request: LogRequest):
    if not db.pool:
        raise HTTPException(status_code=500, detail="Database connection pool not initialized.")

    try:
        # Step 1: The Context Engine deduces intentionality from the diff
        context_summary = await extract_context(request.git_diff, request.commit_msg)
        
        # Step 2: Generate the 1536-dimensional vector for the summary
        vector_embedding = await generate_embedding(context_summary)

        # Step 3: Insert into the Sovereign Vault via asyncpg
        async with db.pool.acquire() as connection:
            # 1. Look up or create the project dynamically
            project_query = """
            INSERT INTO projects (name, description)
            VALUES ($1, $2)
            ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name
            RETURNING id
            """
            project_id = await connection.fetchval(
                project_query,
                request.project_name,
                "Auto-registered via Aqueitas Sensor"
            )

            # 2. Insert the log into the Sovereign Vault
            log_query = """
            INSERT INTO engineering_logs (project_id, log_content, content_embedding)
            VALUES ($1, $2, $3::vector)
            RETURNING id
            """
            
            # Format the python list to pgvector literal string '[1.0, 2.0, ...]'
            vector_str = f"[{','.join(str(x) for x in vector_embedding)}]"
            
            # Combine diff and summary into log_content
            combined_log = f"DIFF:\n{request.git_diff}\n\nSUMMARY:\n{context_summary}"
            
            inserted_id = await connection.fetchval(
                log_query,
                project_id,
                combined_log,
                vector_str
            )
            
            return LogResponse(
                status="success",
                message="Log successfully ingested and vectorized.",
                log_id=str(inserted_id)
            )

    except Exception as e:
        print(f"Error during ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query_vault(request: QueryRequest):
    if not db.pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized.")
        
    try:
        # Step 1: Vectorization
        query_vector = await generate_embedding(request.query)
        
        # Step 2 & 3: Proximity Query with strict database limit
        async with db.pool.acquire() as connection:
            retrieved_logs = await search_vault(query_vector, request.limit, connection)
            
        # Step 4: Zero-Hallucination Synthesis
        answer = await synthesize_answer(request.query, retrieved_logs)
        
        sources = [SourceReference(log_id=log["log_id"], project_name=log["project_name"]) for log in retrieved_logs]
        
        return QueryResponse(answer=answer, sources=sources)
    except Exception as e:
        print(f"Error during retrieval: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
async def get_recent_logs(limit: int = 10):
    """
    Retrieves the most recent engineering logs for the dashboard.
    """
    if not db.pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized.")
        
    async with db.pool.acquire() as connection:
        query = """
        SELECT l.id as log_id, p.name as project_name, l.log_content, l.created_at
        FROM engineering_logs l
        JOIN projects p ON l.project_id = p.id
        ORDER BY l.created_at DESC
        LIMIT $1
        """
        rows = await connection.fetch(query, limit)
        return [dict(row) for row in rows]

class DispatchRequest(BaseModel):
    user_request: str

def handle_complex_task(user_request: str):
    print("AQUEITAS: Task complexity exceeds local threshold. Delegating to Atlas.")
    
    # 1. Generate a unique tracking ID for this specific mission
    mission_id = f"msn-{uuid.uuid4().hex[:8]}"
    
    # 2. Define the exact IP address Atlas needs to send the data back to (Your Tailscale IP)
    my_tailscale_ip = "100.x.y.z" # Replace with your machine's actual Tailscale IP
    
    # 3. Fire the weapon
    dispatcher = AtlasDispatcher()
    
    try:
        task_arn = dispatcher.launch_worker(
            mission_id=mission_id,
            mission_prompt=user_request,
            aqueitas_tailscale_ip=my_tailscale_ip
        )
        print(f"AQUEITAS: Atlas node deployed. Awaiting callback for {mission_id}...")
        return {"status": "dispatched", "mission_id": mission_id, "task_arn": task_arn}
    except Exception as e:
        print(f"AQUEITAS: Delegation failed. {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dispatch")
async def dispatch_task(request: DispatchRequest):
    """
    Endpoint that simulates the orchestrator deciding a workload is too heavy or dangerous.
    Calls the AtlasDispatcher.
    """
    return handle_complex_task(request.user_request)

@app.post("/webhook")
async def receive_worker_telemetry(payload: WorkerTelemetry):
    logging.info(f"⚡ [AWS WORKER SIGNAL] Intent: {payload.intent_id} | Status: {payload.status} | Msg: {payload.message}")
    return {"status": "acknowledged", "recorded_state": payload.status}
