import logging
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from database import db
from models import (
    LogRequest, LogResponse, QueryRequest, QueryResponse, SourceReference,
    MobileDispatchRequest, MobileDispatchResponse, AtlasCallbackRequest
)
from services.embedding import extract_context, generate_embedding
from services.retrieval import search_vault, synthesize_answer
from utils.prompt_forge import forge_contextual_prompt

import uuid
import sys
import os
import json
import httpx
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.aws_dispatcher import AtlasDispatcher

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    
    # Initialize the sovereign transport layer
    async with db.pool.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS atlas_missions (
                mission_id VARCHAR PRIMARY KEY,
                payload TEXT,
                status VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- Async Dispatch Helper ---
def trigger_atlas_worker(mission_id: str, mission_prompt: str):
    """
    Background task wrapper to handle the synchronous boto3 call.
    """
    my_tailscale_ip = os.environ.get("AQUEITAS_TAILSCALE_IP", "100.x.y.z")
    auth_key = os.environ.get("TAILSCALE_AUTHKEY")
    
    if not auth_key:
        logging.error("FATAL: TAILSCALE_AUTHKEY not found in environment!")
        return

    dispatcher = AtlasDispatcher()
    try:
        task_arn = dispatcher.launch_worker(
            mission_id=mission_id,
            mission_prompt=mission_prompt,
            tailscale_authkey=auth_key,
            aqueitas_tailscale_ip=my_tailscale_ip
        )
        logging.info(f"Atlas task launched in background: {task_arn}")
    except Exception as e:
        logging.error(f"Failed to launch Atlas worker in background: {e}")

# --- API Endpoints ---

@app.post("/api/mobile/dispatch", response_model=MobileDispatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def mobile_dispatch(request: MobileDispatchRequest, background_tasks: BackgroundTasks):
    """
    The Mobile Dispatch Contract.
    Intercepts the prompt, retrieves sovereign context, forges an augmented payload, and dispatches Atlas.
    """
    raw_prompt = request.mission_prompt.strip()
    logging.info(f"AQUEITAS: Mobile dispatch received. Priority: {request.priority_level}")
    
    if not db.pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized.")
    
    # 1. Mint the Tracking ID
    mission_id = f"msn-{uuid.uuid4().hex[:8]}"
    logging.info(f"ATLAS SYSTEM: Dispatch initiated. Mission ID: {mission_id}")

    try:
        # 2. The Interception: Vectorize the prompt & retrieve from the Sovereign Vault
        query_vector = await generate_embedding(raw_prompt)
        
        async with db.pool.acquire() as connection:
            # Retrieve top 5 most relevant engineering logs
            retrieved_context = await search_vault(query_vector, 5, connection)
        
        # 3. Prompt Forging
        if retrieved_context:
            logging.info(f"ATLAS SYSTEM: Context acquired. Augmenting payload.")
            final_mission_prompt = forge_contextual_prompt(raw_prompt, retrieved_context)
        else:
            logging.warning(f"ATLAS SYSTEM: No relevant context found. Firing raw payload.")
            final_mission_prompt = raw_prompt

        # 4. Store massive payload in Postgres and dispatch lightweight strike
        async with db.pool.acquire() as connection:
            await connection.execute("""
                INSERT INTO atlas_missions (mission_id, payload, status)
                VALUES ($1, $2, 'PENDING')
            """, mission_id, final_mission_prompt)

        background_tasks.add_task(trigger_atlas_worker, mission_id, "FETCH_PAYLOAD_VIA_TAILSCALE")
        
        # Immediately return 202 Accepted to the iPhone
        return MobileDispatchResponse(status="dispatched", mission_id=mission_id)

    except Exception as e:
        logging.error(f"FATAL: Dispatch pipeline collapsed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal orchestration failure.")

@app.get("/api/internal/mission/{mission_id}")
async def fetch_mission_payload(mission_id: str):
    """
    Sovereign Fetch Endpoint. Atlas pulls the massive prompt over Tailscale before execution.
    """
    if not db.pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized.")
        
    async with db.pool.acquire() as connection:
        row = await connection.fetchrow("""
            UPDATE atlas_missions 
            SET status = 'FETCHED' 
            WHERE mission_id = $1 
            RETURNING payload
        """, mission_id)
        
    if not row:
        raise HTTPException(status_code=404, detail="Mission payload not found.")
        
    return {"mission_id": mission_id, "payload": row["payload"]}

# --- Notification Stub ---
async def send_telegram_notification(mission_id: str, status: str, result_payload: dict):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        logging.warning("Telegram credentials not found in environment.")
        return
        
    emoji = "🟢" if status == "SUCCESS" else "🚨"
    
    text = (
        f"{emoji} **Atlas Mission {status}**\n\n"
        f"**ID:** `{mission_id}`\n\n"
        f"**Payload:**\n```json\n{json.dumps(result_payload, indent=2)}\n```"
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logging.info(f"Telegram notification sent for mission {mission_id}")
        except Exception as e:
            logging.error(f"Failed to send Telegram notification: {e}")

@app.post("/api/internal/atlas-callback")
async def atlas_callback(request: AtlasCallbackRequest):
    """
    The Atlas Callback Contract.
    Receives the final result payload from the ephemeral Fargate node via Tailscale.
    """
    logging.info(f"⚡ [ATLAS CALLBACK] Mission: {request.mission_id} | Status: {request.status.value}")
    
    await send_telegram_notification(
        str(request.mission_id), 
        request.status.value, 
        request.result_payload
    )
    
    return {"status": "acknowledged", "recorded_state": request.status.value}
