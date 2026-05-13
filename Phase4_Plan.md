# Phase 4: The Retrieval Engine (RAG Pipeline)

This plan details the architecture for the "Output" layer of Aqueitas 2.0. By implementing a high-speed RAG pipeline, the EngOS will transition from a passive vault into an actionable technical oracle.

## User Review Required

> [!IMPORTANT]  
> The CLI output interface will be built inside a new `cli/` directory. I propose creating a Python script `cli/aq-ask.py` wrapped by both a Bash script (`aq-ask`) and a PowerShell script (`aq-ask.ps1`). This ensures the CLI tool works seamlessly regardless of whether you are in a Git Bash terminal, a standard Windows PowerShell, or an integrated VS Code terminal. Do you approve of this cross-platform CLI wrapper approach?

## Proposed Changes

### 1. Data Contracts (Schemas)

#### [MODIFY] `brain/models.py`
Introduce strict Pydantic schemas for the retrieval layer:
- `QueryRequest`: Accepts a natural language `query` (str) and an optional `limit` (int, default 5).
- `SourceReference`: Represents metadata for a retrieved log (`log_id`, `project_name`).
- `QueryResponse`: Returns the synthesized `answer` (str) and a list of `sources` (List[SourceReference]).

---

### 2. The Vector Search Orchestration

#### [NEW] `brain/services/retrieval.py`
A dedicated asynchronous service layer mapping the RAG workflow.
- **`search_vault(query_embedding: list[float], limit: int, pool)`**: Executes a PostgreSQL query joining `engineering_logs` and `projects`. It will use the `pgvector` cosine distance operator (`<=>`) to sort logs mathematically by similarity to the query embedding.

---

### 3. The Zero-Hallucination Synthesis

#### [MODIFY] `brain/services/retrieval.py`
- **`synthesize_answer(query: str, retrieved_logs: list)`**: Passes the raw text of the retrieved logs to the DeepSeek engine. 
- **Prompt Engineering**: The system prompt will enforce an absolute boundary: DeepSeek must act as a clinical technical architect and construct the answer *exclusively* from the provided logs. If the logs are irrelevant, it will forcibly fallback to the standardized response: *"The Vault contains no record of this resolution."*

---

### 4. API Endpoint Integration

#### [MODIFY] `brain/main.py`
- **`POST /query`**: A new REST endpoint that ingests the `QueryRequest`.
- **Workflow**:
  1. Calls `generate_embedding(query)` from `embedding.py`.
  2. Passes the vector to `search_vault()`.
  3. Passes the retrieved logs to `synthesize_answer()`.
  4. Returns the `QueryResponse` to the client.

---

### 5. The CLI Output Interface

We will establish a dedicated `cli/` directory for terminal integration.

#### [NEW] `cli/aq-ask.py`
A lightweight script that takes the user's string argument, constructs the JSON payload, pings `http://127.0.0.1:8000/query`, and cleanly prints *only* the answer and source metadata to the terminal.

#### [NEW] `cli/aq-ask` & `cli/aq-ask.ps1`
Platform-agnostic executable wrappers that allow you to seamlessly type `aq-ask "How did I bypass CORS?"` directly in your shell.

## Verification Plan
1. We will verify that the FastAPI `/query` endpoint returns a perfectly structured JSON payload.
2. We will execute `aq-ask "test"` from the terminal to ensure the script parses the API response and renders a clean, human-readable output without disrupting the flow of the terminal.
