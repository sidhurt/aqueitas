# Aqueitas — The Sovereign Engineering OS

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org) [![Docker Required](https://img.shields.io/badge/docker-required-informational)](https://docker.com)

> Every commit you write contains two things: **what changed**, and **why it changed**. Most engineering teams permanently lose the second one. Aqueitas captures both — automatically, on every commit, forever.

![Aqueitas demo: aq ask retrieving engineering intent from a commit](docs/demo.gif)

---

## ⚡ Get Running in 3 Steps

### Prerequisites
- [Python 3.10+](https://python.org/downloads) — check with `python --version`
- [Docker Desktop](https://docker.com/products/docker-desktop) — must be running
- [Git](https://git-scm.com)

---

### Step 1 — Configure (run once)

> You'll need:
> - An **OpenAI key** → [platform.openai.com/api-keys](https://platform.openai.com/api-keys) *(embeddings — ~$0.02/1M tokens)*
> - A **DeepSeek key** → [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) *(reasoning — ~$0.14/1M tokens)*
>
> **No keys? You can still try it.** Set `EMBEDDING_PROVIDER=fake` and
> `REASONING_PROVIDER=passthrough` in your `.env` — the full commit→vault→ask
> loop runs 100% locally (commit messages become the intent summaries, and
> deterministic offline vectors power the search). Swap in real keys later;
> nothing else changes.

**Windows** — Double-click **`CONFIGURE_AQUEITAS.bat`** (interactive wizard, no manual file editing)

**Mac / Linux:**
```bash
python3 aq.py configure
```

Or manually:
```bash
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY and DEEPSEEK_API_KEY

cp brain/.env.example brain/.env
# Edit brain/.env with the same keys
```

---

### Step 2 — Install (run once)

**Windows** — Double-click **`INSTALL_AQUEITAS.bat`**, or in a terminal:
```bat
python aq.py install
```

**Mac / Linux:**
```bash
python3 aq.py install
```

This creates the Python environment, installs dependencies, and activates the global Git commit sensor. Takes ~60 seconds on first run.

---

### Step 3 — Start (run daily)

**Windows** — Double-click **`START_AQUEITAS.bat`**, or in a terminal:
```bat
python aq.py start
```

**Mac / Linux:**
```bash
python3 aq.py start
```

After a few seconds, verify everything is healthy:

```bash
# Windows
python aq.py doctor

# Mac / Linux
python3 aq.py doctor
```

---

**That's it.** Every Git commit you make — in any project — is now automatically intercepted, reasoned about, and embedded into your Sovereign Vault.

---

## 🔍 Querying Your Technical Memory

```bash
# Ask a question about your engineering history
python aq.py ask "how did I implement the authentication flow in the DMS project?"

# View recent ingested commits
python aq.py logs

# Full system health check
python aq.py doctor
```

---

## 🖥️ Full CLI Reference

> On **Mac / Linux**, replace `python` with `python3` in all commands below.

| Command | When to use |
|---|---|
| `python aq.py configure` | First-time setup — write `.env` files from API keys |
| `python aq.py install` | First-time setup — create venv, install deps, activate sensor |
| `python aq.py start` | Every session — boot the Vault and Brain |
| `python aq.py status` | Quick health check |
| `python aq.py doctor` | Deep diagnostics — keys, files, connectivity |
| `python aq.py ask "..."` | Query your technical memory |
| `python aq.py logs` | View the 10 most recent ingested commits |
| `python aq.py replay` | Re-ingest commits queued while the Brain was offline |
| `python aq.py mcp` | Run the MCP server (stdio) for AI-assistant integration |

---

## 🔌 MCP Integration (Claude Code, Claude Desktop, Cursor)

Aqueitas is infrastructure, not another chat window: any MCP-capable assistant
can query your engineering memory directly.

**Claude Code:**
```bash
claude mcp add aqueitas -- python /absolute/path/to/aqueitas/aq.py mcp
```

**Cursor / Claude Desktop** (`mcp.json` / `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "aqueitas": {
      "command": "python",
      "args": ["/absolute/path/to/aqueitas/aq.py", "mcp"]
    }
  }
}
```

Exposed tools:

| Tool | What it does |
|---|---|
| `query_sovereign_vault` | Grounded answers from your engineering history, with structured sources (log id, project, timestamp, excerpt). If the Brain is offline it returns an honest error — never a made-up answer. |
| `ingest_workspace` | Chunk + embed a local directory into the vault for code-aware retrieval. |

---

## 🔒 Privacy & Data Flow

Trust requires knowing exactly what leaves your machine:

- **Vault data never leaves your machine.** Commits, embeddings, and answers live in your local Postgres container.
- With default providers, **two things are sent out per commit**: the diff + commit message go to **DeepSeek** (intent extraction), and the resulting summary goes to **OpenAI** (embedding). Diffs are capped at 50KB before leaving the machine.
- The sensor is **global** (`core.hooksPath`) — it observes every repo you commit to. Your repos' own `post-commit` hooks still run: the sensor chains to them first. To pause observation: `git config --global --unset core.hooksPath`.
- Fully offline mode: `EMBEDDING_PROVIDER=fake` + `REASONING_PROVIDER=passthrough` — zero external calls.
- If the Brain is down, commits queue locally in `sensor/queue.jsonl` and replay later — nothing is lost, nothing is sent anywhere in the meantime.

---

## 🏗️ Architecture

The system is divided into four operational layers:

```mermaid
graph TD
    subgraph "Phase 3: The Sensor"
        A[Developer Commits Code] -->|Git Hook Intercepts| B(post-commit.py)
    end

    subgraph "Phase 2: The Ingestion Engine (FastAPI)"
        B -->|Async Payload POST| C{Hybrid Context Engine}
        C -->|1. Reasoning: Deduce Intent| D[DeepSeek 'deepseek-chat']
        C -->|2. Math: Embed to 1536d| E[OpenAI 'text-embedding-3-small']
        D --> C
        E --> C
    end

    subgraph "Phase 1: The Sovereign Vault"
        C -->|Async Insert| F[(PostgreSQL + pgvector)]
    end

    subgraph "Phase 4: The Retrieval Engine"
        G[aq ask CLI] -->|Query| F
        F -->|HNSW Vector Search| G
        G -->|Zero-Hallucination RAG| H((Human Engineer))
    end
```

| Layer | Technology | Role |
|---|---|---|
| Sovereign Vault | PostgreSQL + pgvector | Stores commit embeddings (1536-dimensional HNSW index), deduplicated by commit hash |
| Ingestion Engine | FastAPI + asyncpg | Extracts the *why* behind every code change |
| Sensor | Global Git hook | Observes commits across every project (and chains to each repo's own hooks) |
| Retrieval Engine | aq CLI + vector search | Answers grounded strictly in your actual history — sources cited, honest when no record exists |

Providers are swappable via `.env` (`EMBEDDING_PROVIDER`, `REASONING_PROVIDER`,
`EMBEDDING_MODEL`, `REASONING_MODEL`, `REASONING_BASE_URL`) — the accumulated
engineering memory is the asset, not any particular model.

> **Optional:** an experimental remote-worker integration (AWS Fargate + Tailscale)
> exists behind `ATLAS_ENABLED=true`. It is fully off by default and the core
> system has no AWS dependency.

---

## 💡 Cost Model

The entire system runs on two cheap API calls per commit:

| Model | Provider | Use | Cost |
|---|---|---|---|
| `deepseek-chat` | DeepSeek | Reasoning / intent extraction | ~$0.14 / 1M tokens |
| `text-embedding-3-small` | OpenAI | 1536-dimensional embedding | ~$0.02 / 1M tokens |

A typical commit costs under **$0.001** to ingest. Thousands of commits per month cost fractions of a cent.

---

## 📖 Philosophy

Aqueitas evolved from a lightweight documentation script (1.0) into a mathematically rigorous Engineering Operating System (2.0) built on data sovereignty and zero SaaS lock-in.

- [The Aqueitas Manifesto](docs/AQUEITAS_MANIFESTO.md)
- [Aqueitas 2.0: Dissertation & Architecture](docs/Aqueitas_2.0_Dissertation.txt)

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. This project uses [Conventional Commits](https://www.conventionalcommits.org/) — your commit messages should meet the same bar as the tool itself.

## ⚖️ License

MIT — see [LICENSE](LICENSE).
