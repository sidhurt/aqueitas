# Phase 3: The Sensor (Automated Ingestion)

This plan outlines the architecture for eliminating the "Interface Deficit" by building a Global Git Hook that silently pushes engineering logs to the Aqueitas Brain.

## User Review Required

> [!IMPORTANT]  
> To ensure the Git hook does not freeze your terminal for 5 seconds while DeepSeek and OpenAI process the diff, I am proposing an architectural shift to the Brain. We will use FastAPI's **`BackgroundTasks`**. The API will immediately return a `202 Accepted`, allowing your terminal to unblock instantly, while the AI processing happens silently in the background. Do you agree with this optimization?

## Proposed Changes

We will split the execution into two layers: modifying the API for zero-friction ingestion, and building the global interceptor.

### 1. The Brain Optimization (FastAPI)

#### [MODIFY] `brain/models.py`
- Change `project_id` to `project_name` in `LogRequest`. The Git hook shouldn't need to know database UUIDs; it only knows the folder name of the repo.

#### [MODIFY] `brain/main.py`
- Refactor the `/log` endpoint to use `BackgroundTasks`.
- Add logic to automatically look up (or create) the `project_id` based on the incoming `project_name`.
- Shift the `extract_context`, `generate_embedding`, and database insertion into a background function. The endpoint will instantly return a `202 Accepted` status.

---

### 2. The Sensor (Global Git Hook)

We will create a centralized `sensor/` directory to house the global Git hooks.

#### [NEW] `sensor/post-commit.py`
A lightweight, zero-dependency Python script that:
1. Detects the current repository name (e.g. `basename(pwd)`).
2. Captures the latest commit diff (`git diff HEAD~1 HEAD`).
3. Captures the commit message (`git log -1 --pretty=%B`).
4. Fires an HTTP POST request to `http://127.0.0.1:8000/log`.
5. Fails gracefully (silently) if the Aqueitas Brain is currently turned off, so it never interrupts your standard Git workflow.

#### [NEW] `sensor/post-commit` (Shell Executable)
A simple wrapper required by Git that executes the `post-commit.py` script.

#### [NEW] `sensor/setup.ps1`
A one-click PowerShell script to register the global hooks directory using `git config --global core.hooksPath`.

## Verification Plan
- We will make a real `git commit` in the `aqueitas` repository.
- We will verify that the commit command executes instantly in the terminal.
- We will check the FastAPI logs to ensure the background task processed the diff and inserted it into the Sovereign Vault.
