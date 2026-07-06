import os
import sys
import asyncio
import json
from pathlib import Path

# Trust the OS certificate store (corporate TLS interception breaks certifi);
# must run before any SSL context is created.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import httpx
from mcp.server.fastmcp import FastMCP

# Inject brain into sys.path so the vault's own modules are importable
BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'brain'))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BRAIN_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BRAIN_DIR, '.env'))
load_dotenv(os.path.join(ROOT_DIR, '.env'))
from database import db
from services.embedding import generate_embedding

BRAIN_URL = "http://127.0.0.1:8000"


def _elog(msg: str) -> None:
    # stderr only: stdout carries the MCP JSON-RPC stream.
    print(msg, file=sys.stderr)


# Initialize the FastMCP server
mcp = FastMCP("Aqueitas")

@mcp.tool()
async def ingest_workspace(directory_path: str) -> str:
    """
    Traverse the local directory, chunk the code files, deduce the architectural purpose,
    and ingest the vectors into the pgvector database.
    """
    target_dir = Path(directory_path)
    if not target_dir.exists() or not target_dir.is_dir():
        return json.dumps({"status": "error", "message": f"Directory '{directory_path}' does not exist or is not a directory."})

    await db.connect()

    IGNORE_DIRS = {'.git', 'node_modules', 'venv', '.venv', '__pycache__', 'build', 'dist', '.next', 'out', 'coverage'}
    IGNORE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.mp4', '.exe', '.dll', '.so', '.dylib', '.bin', '.pdf', '.zip', '.tar', '.gz', '.pyc'}
    CHUNK_SIZE = 4000
    OVERLAP = 200

    # 1. Register or get Project ID
    async with db.pool.acquire() as connection:
        project_id = await connection.fetchval("""
            INSERT INTO projects (name, description)
            VALUES ($1, $2)
            ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name
            RETURNING id
        """, target_dir.name, f"Workspace ingestion of {target_dir}")

    sem = asyncio.Semaphore(15)

    async def process_chunk(file_path: Path, chunk_text: str):
        async with sem:
            try:
                embedding = await generate_embedding(chunk_text)
                vector_str = f"[{','.join(str(x) for x in embedding)}]"
                return {
                    "project_id": project_id,
                    "project_path": str(target_dir),
                    "file_path": str(file_path.relative_to(target_dir)),
                    "raw_content": chunk_text,
                    "content_embedding": vector_str
                }
            except Exception as e:
                _elog(f"Embedding error for {file_path}: {e}")
                return None

    tasks = []

    # 2. Traverse and Chunk
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]

        for file in files:
            path = Path(root) / file
            if path.suffix.lower() in IGNORE_EXTS or path.name.startswith('.'):
                continue

            try:
                content = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue # Skip binary or unreadable files gracefully

            if not content.strip():
                continue

            # Chunking
            for i in range(0, len(content), CHUNK_SIZE - OVERLAP):
                if i > 0 and i + CHUNK_SIZE >= len(content) and len(content) - i < OVERLAP * 2:
                    break # Avoid tiny tail chunks
                chunk = content[i:i + CHUNK_SIZE]
                tasks.append(process_chunk(path, chunk))

    if not tasks:
        return json.dumps({
            "status": "success",
            "message": "No processable files found.",
            "project_id": target_dir.name,
            "action": "ingested_to_vault"
        })

    _elog(f"Processing {len(tasks)} chunks across {target_dir}...")

    # 3. Vectorize concurrently
    results = await asyncio.gather(*tasks)
    valid_records = [r for r in results if r is not None]

    # 4. Batch Insert
    if valid_records:
        async with db.pool.acquire() as connection:
            await connection.executemany("""
                INSERT INTO workspace_files (project_id, project_path, file_path, raw_content, content_embedding)
                VALUES ($1, $2, $3, $4, $5::vector)
            """, [(r["project_id"], r["project_path"], r["file_path"], r["raw_content"], r["content_embedding"]) for r in valid_records])

    return json.dumps({
        "status": "success",
        "message": f"Successfully ingested {len(valid_records)} chunks from workspace.",
        "project_id": target_dir.name,
        "action": "ingested_to_vault"
    })

@mcp.tool()
def query_sovereign_vault(query: str, directory_path: str) -> str:
    """
    Execute a semantic proximity search against the vector DB to answer questions
    about the codebase (e.g., "Where is authentication state managed?").
    Returns a grounded answer plus structured sources (log id, project, timestamp,
    excerpt). If the Brain is offline, returns an honest error — never a
    fabricated answer.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{BRAIN_URL}/query",
                json={"query": f"[{Path(directory_path).name}] {query}", "limit": 3}
            )
            response.raise_for_status()
            data = response.json()
            return json.dumps({
                "status": "success",
                "answer": data.get("answer", "No direct answer found."),
                "sources": data.get("sources", [])
            })
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "status": "error",
            "message": (
                f"The Aqueitas Brain returned HTTP {e.response.status_code}. "
                "No answer is available. Do not invent one; report this error to the user."
            ),
            "detail": e.response.text[:500]
        })
    except httpx.RequestError as e:
        return json.dumps({
            "status": "error",
            "message": (
                f"The Aqueitas Brain is unreachable at {BRAIN_URL}. "
                "No engineering memory is available for this query. "
                "Do not invent an answer; tell the user to start Aqueitas with 'python aq.py start'."
            ),
            "detail": str(e)
        })

@mcp.prompt()
def analyze_friction_points() -> str:
    """
    A strategic briefing prompt. Instructs the LLM to identify tight coupling,
    technical debt, or optimization vectors based on retrieved context.
    """
    return """
You are acting as a Principal Systems Architect. Review the provided codebase context and retrieved engineering logs from the Aqueitas Sovereign Vault.

Your objective is to deliver a strategic briefing that identifies:
1. Tight Coupling: Areas where components are too deeply integrated, hindering modularity.
2. Technical Debt: Hidden complexities, outdated patterns, or "hacky" solutions that need refactoring.
3. Optimization Vectors: Specific functions, queries, or architectural flows that can be accelerated or optimized for scale.

Frame your output as a professional, brutal, and highly actionable briefing for a Lead Engineer.
Focus strictly on structural and architectural friction points.
"""

def start_mcp():
    """Entry point to run the MCP server over stdio."""
    mcp.run(transport="stdio")

if __name__ == "__main__":
    start_mcp()
