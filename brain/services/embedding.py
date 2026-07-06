"""Provider layer for embeddings and reasoning.

Principle: every model and provider is replaceable — the accumulated
engineering understanding is the asset, not the underlying models.

Selection is env-driven:
  EMBEDDING_PROVIDER  = openai (default) | fake
  REASONING_PROVIDER  = deepseek (default) | passthrough
  EMBEDDING_MODEL     = text-embedding-3-small (default)
  REASONING_MODEL     = deepseek-chat (default)
  REASONING_BASE_URL  = https://api.deepseek.com (default)

`fake` and `passthrough` need no API keys: `fake` produces deterministic
hashed bag-of-words vectors (token overlap still yields useful similarity),
and `passthrough` uses the commit message itself as the intent summary.
"""
import hashlib
import math
import os

from dotenv import load_dotenv

load_dotenv()

# Fixed by the vault schema: vector(1536). Changing this requires a migration.
EMBEDDING_DIMENSIONS = 1536

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
REASONING_PROVIDER = os.getenv("REASONING_PROVIDER", "deepseek").strip().lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
REASONING_MODEL = os.getenv("REASONING_MODEL", "deepseek-chat")
REASONING_BASE_URL = os.getenv("REASONING_BASE_URL", "https://api.deepseek.com")

_OFFLINE_REASONING = ("passthrough", "none", "off")
_OFFLINE_EMBEDDING = ("fake", "hash")

_reasoning_client = None
_embedding_client = None


def reasoning_enabled() -> bool:
    return REASONING_PROVIDER not in _OFFLINE_REASONING


def _get_reasoning_client():
    global _reasoning_client
    if _reasoning_client is None:
        from openai import AsyncOpenAI
        _reasoning_client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=REASONING_BASE_URL,
        )
    return _reasoning_client


def _get_embedding_client():
    global _embedding_client
    if _embedding_client is None:
        from openai import AsyncOpenAI
        _embedding_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _embedding_client


def fake_embedding(text: str) -> list[float]:
    """Deterministic, dependency-free embedding: hashed bag-of-words.

    Identical text always maps to the identical vector, and texts sharing
    tokens land closer together — enough signal to exercise the full
    ingest/retrieve loop without any external API.
    """
    vec = [0.0] * EMBEDDING_DIMENSIONS
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        vec[0] = 1.0
        norm = 1.0
    return [x / norm for x in vec]


async def chat_completion(system_prompt: str, user_prompt: str,
                          temperature: float = 0.2, max_tokens: int = 500) -> str:
    """Single entry point for all reasoning calls. Callers must check
    reasoning_enabled() first; this raises if invoked in offline mode."""
    if not reasoning_enabled():
        raise RuntimeError(
            f"Reasoning is disabled (REASONING_PROVIDER={REASONING_PROVIDER}); "
            "callers must branch on reasoning_enabled()."
        )
    response = await _get_reasoning_client().chat.completions.create(
        model=REASONING_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


async def extract_context(git_diff: str, commit_msg: str | None = None) -> str:
    """Deduce the intentionality ('Why') behind a code change.

    With reasoning offline, the commit message is the best available
    statement of intent — observation over fabrication.
    """
    if not reasoning_enabled():
        summary = (commit_msg or "").strip()
        return summary if summary else git_diff[:400].strip()

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

    return await chat_completion(system_prompt, user_prompt, temperature=0.2, max_tokens=300)


async def generate_embedding(text: str) -> list[float]:
    """Generate a 1536-dimensional vector for the text using the configured provider."""
    if EMBEDDING_PROVIDER in _OFFLINE_EMBEDDING:
        return fake_embedding(text)

    response = await _get_embedding_client().embeddings.create(
        input=text,
        model=EMBEDDING_MODEL,
    )
    return response.data[0].embedding
