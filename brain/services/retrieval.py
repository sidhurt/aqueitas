import re
from .embedding import deepseek_client, generate_embedding

# Keywords that signal the user wants commits ordered by time, not similarity
_TEMPORAL_PATTERN = re.compile(
    r"\b(last|latest|recent|newest|most recent|chronological)\b",
    re.IGNORECASE,
)

def _is_temporal_query(query: str) -> bool:
    """Return True when the query is asking about recency rather than semantics."""
    return bool(_TEMPORAL_PATTERN.search(query))


async def search_vault(
    query_embedding: list[float],
    limit: int,
    connection,
    query_text: str = "",
) -> list[dict]:
    """
    Retrieves engineering logs from the Sovereign Vault.

    - Temporal queries ("last N commits", "recent changes") are answered by
      ordering on created_at DESC so the newest ingested commits are returned.
    - All other queries use cosine-distance vector search for semantic relevance.
    """
    if _is_temporal_query(query_text):
        sql = """
        SELECT e.id, p.name AS project_name, e.log_content,
               e.created_at
        FROM engineering_logs e
        JOIN projects p ON e.project_id = p.id
        ORDER BY e.created_at DESC
        LIMIT $1
        """
        rows = await connection.fetch(sql, limit)
    else:
        vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
        sql = """
        SELECT e.id, p.name AS project_name, e.log_content,
               e.created_at
        FROM engineering_logs e
        JOIN projects p ON e.project_id = p.id
        ORDER BY e.content_embedding <=> $1::vector
        LIMIT $2
        """
        rows = await connection.fetch(sql, vector_str, limit)

    results = []
    for row in rows:
        results.append({
            "log_id": str(row["id"]),
            "project_name": row["project_name"],
            "log_content": row["log_content"],
            "created_at": str(row["created_at"]),
        })
    return results

async def synthesize_answer(query: str, retrieved_logs: list[dict]) -> str:
    """
    Passes the retrieved logs to DeepSeek for Zero-Hallucination synthesis.
    """
    system_prompt = (
        "You are a clinical technical architect. You are answering a query strictly based on the provided engineering logs.\n"
        "If the provided logs do not contain the answer, you are strictly forbidden from generating one. "
        "Output EXACTLY: 'The Vault contains no record of this resolution.'\n"
        "Do not use external knowledge or general training data."
    )
    
    logs_context = ""
    for idx, log in enumerate(retrieved_logs, 1):
        logs_context += f"--- LOG {idx} (Project: {log['project_name']}) ---\n{log['log_content']}\n\n"
        
    user_prompt = f"Logs:\n{logs_context}\n\nQuery: {query}"
    
    response = await deepseek_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()
