# Aqueitas: The Sovereign Engineering Operating System (EngOS)

Aqueitas executes the death of "passive forgetting" in software engineering. By automatically intercepting the byproduct of daily engineering (the code diff) and mathematically mapping its underlying logic, Aqueitas constructs an **Active Technical Memory**. It ensures that no effort is ephemeral, turning every keystroke into an undeniable, queryable intellectual asset.

---

## 🚀 The Evolution: Aqueitas 1.0 vs. Aqueitas 2.0

Aqueitas has undergone a profound architectural shift. It evolved from a lightweight, automated documentation sidecar relying on third-party SaaS (Aqueitas 1.0) into a fully sovereign, mathematically rigorous Engineering Operating System (Aqueitas 2.0). 

Here is a comprehensive comparison of the project's first and second iterations:

### 1. The Persistence Layer (Memory)
* **Aqueitas 1.0:** Relied on **Notion via MCP** (Model Context Protocol). It bridged the CLI and Notion to convert ephemeral diff analysis into a permanent database. While effective, it suffered from SaaS lock-in and required navigating an external interface.
* **Aqueitas 2.0:** Migrated to a **Sovereign Vault**. Utilizes Dockerized **PostgreSQL 17** with the `pgvector` extension. Data sovereignty is prioritized, natively handling 1536-dimensional embeddings with Hierarchical Navigable Small World (HNSW) indexing for instantaneous semantic retrieval.

### 2. The Automation Trigger (Sensor)
* **Aqueitas 1.0:** Driven by IDE-specific configurations (`.vscode/tasks.json`). It utilized the `"runOn": "folderOpen"` directive to trigger a zero-click automation pipeline that synced the local environment with SAP Business Application Studio (BAS).
* **Aqueitas 2.0:** Operates at the system level via a **Global Git Hook** (`core.hooksPath` mapped to `sensor/post-commit.py`). It synchronously intercepts `git commit` commands, enforcing a 2-5 second terminal block to provide undeniable confirmation that the embedding was successfully reasoned and written to the Vault.

### 3. The Intelligence Layer (Brain)
* **Aqueitas 1.0:** Powered by bash scripts (`audit-changes.sh`) using Heredocs to pass diffs to the **Gemini CLI**. It booted the LLM into a scoped role to derive architectural rationale.
* **Aqueitas 2.0:** Powered by a high-velocity **FastAPI** Python service utilizing a Hybrid Context Engine:
  * **DeepSeek (`deepseek-chat`):** Acts as the Staff-level architect to strip boilerplate and deduce intentionality (the "Why").
  * **OpenAI (`text-embedding-3-small`):** Mathematically encodes the text into 1536-dimensional coordinates.

### 4. The Retrieval Engine (Output)
* **Aqueitas 1.0:** Read-only intelligence persisted in Notion. Engineers had to open Notion to search past rationale.
* **Aqueitas 2.0:** A dedicated **RAG Pipeline** accessible directly via terminal cross-platform wrappers (`aq-ask`). DeepSeek is subjected to a **Zero-Hallucination Protocol**—it is explicitly forbidden from utilizing its generalized training data. If the vector search returns irrelevant logs, it defaults to: *"The Vault contains no record of this resolution."*

---

## 🏗️ The Aqueitas 2.0 Architecture Overview

The system is strictly divided into four operational layers leveraging open-source, scalable technologies:

1. **Phase 1: The Sovereign Vault:** PostgreSQL + `pgvector`.
2. **Phase 2: The Ingestion Engine:** FastAPI + `asyncpg` + DeepSeek/OpenAI hybrid routing.
3. **Phase 3: The Sensor:** Global Git hooks intercepting commits synchronously.
4. **Phase 4: The Retrieval Engine:** Vector search orchestration via CLI (`aq-ask`).

## 💡 Financial & Operational Efficiency

The entire system is architected under the mandate of "Efficiency over Excess." By utilizing DeepSeek for reasoning ($0.14/1M tokens) and OpenAI for embeddings ($0.02/1M tokens), the API cost to ingest and retrieve thousands of code commits per month is fractions of a cent. 

## 🌍 Global Impact

The current industry standard relies on fragmented documentation (Notion, Slack, Jira) which inevitably fails under pressure, resulting in the mass evaporation of intellectual property. Aqueitas 2.0 redefines the relationship between the engineer and their output. It elevates the operator from a laborer writing syntax into a commander orchestrating captured intelligence. 
