import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Client 1: DeepSeek for heavy context reasoning (ultra-low cost for large Git diffs)
deepseek_client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# Client 2: OpenAI exclusively for standard 1536-dimensional embeddings (ultra-low cost)
openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

async def extract_context(git_diff: str, commit_msg: str | None = None) -> str:
    """
    Uses DeepSeek to deduce the intentionality ('Why') behind a code change.
    Ignores boilerplate and focuses on the technical engineering decisions.
    """
    system_prompt = (
        "You are an elite Staff Engineer analyzing a Git diff. "
        "Your sole objective is to deduce the INTENTIONALITY (the 'Why') behind this change. "
        "Ignore boilerplate, formatting, and trivial syntax changes. "
        "Focus entirely on architectural shifts, technical decisions, bug fixes, or performance optimizations. "
        "Respond with a concise, highly technical summary of the engineering logic."
    )
    
    user_prompt = f"Analyze the following Git diff:\n\n{git_diff}"
    if commit_msg:
        user_prompt += f"\n\nContext from commit message: {commit_msg}"

    response = await deepseek_client.chat.completions.create(
        model="deepseek-chat", # DeepSeek V3 optimized for reasoning and coding
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        max_tokens=300
    )
    
    return response.choices[0].message.content.strip()

async def generate_embedding(text: str) -> list[float]:
    """
    Calls OpenAI text-embedding-3-small to generate a 1536-dimensional vector for the text.
    """
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding
