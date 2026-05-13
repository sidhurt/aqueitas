from .embedding import deepseek_client, generate_embedding

async def search_vault(query_embedding: list[float], limit: int, connection) -> list[dict]:
    """
    Executes a vector search against the engineering_logs table using the cosine distance operator (<=>).
    Strictly enforces the limit at the database level.
    """
    query = """
    SELECT e.id, p.name as project_name, e.log_content
    FROM engineering_logs e
    JOIN projects p ON e.project_id = p.id
    ORDER BY e.content_embedding <=> $1::vector
    LIMIT $2
    """
    
    vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
    
    rows = await connection.fetch(query, vector_str, limit)
    
    results = []
    for row in rows:
        results.append({
            "log_id": str(row['id']),
            "project_name": row['project_name'],
            "log_content": row['log_content']
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
