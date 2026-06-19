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
        sql_logs = """
        SELECT e.id, p.name AS project_name, e.log_content,
               e.created_at
        FROM engineering_logs e
        JOIN projects p ON e.project_id = p.id
        ORDER BY e.created_at DESC
        LIMIT $1
        """
        rows_logs = await connection.fetch(sql_logs, limit)
        
        sql_files = """
        SELECT w.id, p.name AS project_name, w.file_path, w.raw_content,
               w.timestamp AS created_at
        FROM workspace_files w
        JOIN projects p ON w.project_id = p.id
        ORDER BY w.timestamp DESC
        LIMIT $1
        """
        rows_files = await connection.fetch(sql_files, limit)
        
        combined_results = []
        for row in rows_logs:
            combined_results.append({
                "log_id": str(row["id"]),
                "project_name": row["project_name"],
                "log_content": f"[COMMIT LOG]\n{row['log_content']}",
                "created_at": str(row["created_at"]),
                "sort_key": row["created_at"]
            })
        for row in rows_files:
            combined_results.append({
                "log_id": str(row["id"]),
                "project_name": row["project_name"],
                "log_content": f"[SOURCE FILE: {row['file_path']}]\n{row['raw_content']}",
                "created_at": str(row["created_at"]),
                "sort_key": row["created_at"]
            })
            
        combined_results.sort(key=lambda x: x["sort_key"], reverse=True)
        
    else:
        vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        sql_logs = """
        SELECT e.id, p.name AS project_name, e.log_content,
               e.created_at,
               (e.content_embedding <=> $1::vector) AS distance
        FROM engineering_logs e
        JOIN projects p ON e.project_id = p.id
        ORDER BY distance
        LIMIT $2
        """
        rows_logs = await connection.fetch(sql_logs, vector_str, limit)
        
        sql_files = """
        SELECT w.id, p.name AS project_name, w.file_path, w.raw_content,
               w.timestamp AS created_at,
               (w.content_embedding <=> $1::vector) AS distance
        FROM workspace_files w
        JOIN projects p ON w.project_id = p.id
        ORDER BY distance
        LIMIT $2
        """
        rows_files = await connection.fetch(sql_files, vector_str, limit)
        
        combined_results = []
        for row in rows_logs:
            combined_results.append({
                "log_id": str(row["id"]),
                "project_name": row["project_name"],
                "log_content": f"[COMMIT LOG]\n{row['log_content']}",
                "created_at": str(row["created_at"]),
                "distance": row["distance"]
            })
        for row in rows_files:
            combined_results.append({
                "log_id": str(row["id"]),
                "project_name": row["project_name"],
                "log_content": f"[SOURCE FILE: {row['file_path']}]\n{row['raw_content']}",
                "created_at": str(row["created_at"]),
                "distance": row["distance"]
            })
            
        combined_results.sort(key=lambda x: x["distance"])

    # Take absolute top N
    top_results = combined_results[:limit]
    
    results = []
    for res in top_results:
        results.append({
            "log_id": res["log_id"],
            "project_name": res["project_name"],
            "log_content": res["log_content"],
            "created_at": res["created_at"],
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
