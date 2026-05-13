from fastapi import FastAPI, HTTPException
from database import db
from models import LogRequest, LogResponse
from services.embedding import extract_context, generate_embedding

app = FastAPI(
    title="Aqueitas Brain",
    description="The Intelligence Layer of the Aqueitas EngOS",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_event():
    await db.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await db.disconnect()

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
