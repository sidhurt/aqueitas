def forge_contextual_prompt(raw_prompt: str, retrieved_logs: list[dict]) -> str:
    """
    Stitches pgvector context with the user's raw prompt into a heavily fortified payload.
    """
    if not retrieved_logs:
        return raw_prompt

    # Format the retrieved engineering logs using the actual keys returned by search_vault
    context_block = "\n---\n".join(
        f"Project: {log.get('project_name')}\nLog Details:\n{log.get('log_content')}"
        for log in retrieved_logs
    )

    augmented_prompt = f"""
SYSTEM DIRECTIVE: 
You are Atlas, the execution muscle for Aqueitas EngOS. 
You have been dispatched to answer a query based on the sovereign engineering logs provided below. Ground your entire response in this exact context. If the answer is not in the context, state that explicitly. Do not hallucinate external codebase knowledge.

[ENGINEERING CONTEXT - SOVEREIGN VAULT]
{context_block}
[END CONTEXT]

USER QUERY:
{raw_prompt}

Execute.
"""
    return augmented_prompt.strip()
