import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Use the OS certificate store for TLS (same fix pip adopted): corporate
# proxies and AV products intercept HTTPS with roots that certifi doesn't
# know, silently breaking every provider call. Must run before any SSL
# context is created.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from dotenv import load_dotenv

BRAIN_DIR = Path(__file__).parent.absolute()
ROOT_DIR = BRAIN_DIR.parent

# Root .env is the source of truth; brain/.env may layer local overrides.
# (load_dotenv never overwrites variables that are already set.)
load_dotenv(BRAIN_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import db
from models import LogRequest, LogResponse, QueryRequest, QueryResponse, SourceReference
from services.embedding import extract_context, generate_embedding
from services.retrieval import search_vault, synthesize_answer

logger = logging.getLogger(__name__)

# Optional Atlas remote-worker integration — fully feature-flagged so the
# core vault never depends on AWS/Tailscale/Telegram.
ATLAS_ENABLED = os.getenv("ATLAS_ENABLED", "").strip().lower() in ("1", "true", "yes")

CORE_SCHEMA_FILE = ROOT_DIR / "infrastructure" / "db" / "init.sql"


async def apply_core_schema():
    """Re-apply the idempotent vault schema at every startup so volumes
    initialized by older versions pick up new tables, columns, and indexes."""
    if not CORE_SCHEMA_FILE.exists():
        logger.warning(f"Schema file not found at {CORE_SCHEMA_FILE}; skipping schema check.")
        return
    schema_sql = CORE_SCHEMA_FILE.read_text(encoding="utf-8")
    async with db.pool.acquire() as connection:
        await connection.execute(schema_sql)
    logger.info("Vault schema verified.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    try:
        await apply_core_schema()
    except Exception as e:
        # Surface loudly but keep the API up so /docs and doctor still work.
        logger.error(f"Failed to apply vault schema: {e}")
    if ATLAS_ENABLED:
        from integrations.atlas import ensure_atlas_schema
        await ensure_atlas_schema(db.pool)
    yield
    await db.disconnect()


app = FastAPI(
    title="Aqueitas Brain",
    description="The Intelligence Layer of the Aqueitas EngOS",
    version="2.1.0",
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

if ATLAS_ENABLED:
    from integrations.atlas import router as atlas_router
    app.include_router(atlas_router)


PROJECT_UPSERT = """
INSERT INTO projects (name, description)
VALUES ($1, $2)
ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name
RETURNING id
"""

LOG_INSERT = """
INSERT INTO engineering_logs (project_id, commit_hash, log_content, content_embedding)
VALUES ($1, $2, $3, $4::vector)
ON CONFLICT (project_id, commit_hash) WHERE commit_hash IS NOT NULL DO NOTHING
RETURNING id
"""

LOG_LOOKUP = """
SELECT id FROM engineering_logs WHERE project_id = $1 AND commit_hash = $2
"""


@app.post("/log", response_model=LogResponse)
async def ingest_log(request: LogRequest):
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database connection pool not initialized.")

    try:
        # Step 0: Dedup check BEFORE any model calls — replays and sensor
        # timeout-retries must not burn tokens or create duplicate memories.
        async with db.pool.acquire() as connection:
            project_id = await connection.fetchval(
                PROJECT_UPSERT, request.project_name, "Auto-registered via Aqueitas Sensor"
            )
            if request.commit_hash:
                existing_id = await connection.fetchval(LOG_LOOKUP, project_id, request.commit_hash)
                if existing_id:
                    return LogResponse(
                        status="duplicate",
                        message="Commit already ingested; skipped.",
                        log_id=str(existing_id)
                    )

        # Step 1: The Context Engine deduces intentionality from the diff
        context_summary = await extract_context(request.git_diff, request.commit_msg)

        # Step 2: Generate the 1536-dimensional vector for the summary
        vector_embedding = await generate_embedding(context_summary)

        # Step 3: Insert into the Sovereign Vault
        vector_str = f"[{','.join(str(x) for x in vector_embedding)}]"

        header_lines = []
        if request.commit_hash:
            header_lines.append(f"COMMIT: {request.commit_hash}")
        if request.author:
            header_lines.append(f"AUTHOR: {request.author}")
        if request.committed_at:
            header_lines.append(f"DATE: {request.committed_at}")
        header = ("\n".join(header_lines) + "\n\n") if header_lines else ""

        combined_log = (
            f"{header}COMMIT MESSAGE:\n{request.commit_msg}\n\n"
            f"DIFF:\n{request.git_diff}\n\nSUMMARY:\n{context_summary}"
        )

        async with db.pool.acquire() as connection:
            inserted_id = await connection.fetchval(
                LOG_INSERT, project_id, request.commit_hash, combined_log, vector_str
            )
            if inserted_id is None:
                # Lost a race with a concurrent identical ingest — still a success.
                existing_id = await connection.fetchval(LOG_LOOKUP, project_id, request.commit_hash)
                return LogResponse(
                    status="duplicate",
                    message="Commit already ingested; skipped.",
                    log_id=str(existing_id)
                )

            return LogResponse(
                status="success",
                message="Log successfully ingested and vectorized.",
                log_id=str(inserted_id)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query_vault(request: QueryRequest):
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized.")

    try:
        # Step 1: Vectorization
        query_vector = await generate_embedding(request.query)

        # Step 2 & 3: Proximity query with strict database limit
        async with db.pool.acquire() as connection:
            retrieved_logs = await search_vault(query_vector, request.limit, connection, query_text=request.query)

        # Step 4: Grounded synthesis
        answer = await synthesize_answer(request.query, retrieved_logs)

        sources = [
            SourceReference(
                log_id=log["log_id"],
                project_name=log["project_name"],
                created_at=log.get("created_at"),
                excerpt=(log.get("log_content") or "")[:240]
            )
            for log in retrieved_logs
        ]

        return QueryResponse(answer=answer, sources=sources)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs")
async def get_recent_logs(limit: int = 10):
    """
    Retrieves the most recent engineering logs for the dashboard.
    """
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized.")

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
