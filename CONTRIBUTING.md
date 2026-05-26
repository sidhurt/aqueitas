# Contributing to Aqueitas

Thank you for your interest in contributing. Aqueitas is built on the principle that engineering intent should be permanent — contributions that honour that philosophy are welcome.

---

## How to Contribute

### Reporting Bugs
Open an issue with:
- Your OS and Python version
- The exact command that failed
- The full error output (paste it — don't screenshot)

### Suggesting Features
Open an issue tagged `enhancement`. Explain the *problem* you're solving, not just the feature you want. Aqueitas is opinionated software; features that introduce SaaS dependencies or cloud lock-in will not be merged.

### Submitting Pull Requests

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Write clean commits.** This is non-negotiable for a project whose entire purpose is commit quality:
   - Use [Conventional Commits](https://www.conventionalcommits.org/) format: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
   - Each commit message body should explain *why*, not just *what*
   - No "fix stuff", "wip", or "misc changes"

3. **Test your changes.** Ensure the full flow works end-to-end:
   ```bash
   python aq.py doctor
   python aq.py status
   ```

4. **Open the PR** against `main` with a clear description of what changed and why.

---

## Development Setup

```bash
# 1. Clone your fork
git clone https://github.com/YOUR_USERNAME/aqueitas.git
cd aqueitas

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

---

## Code Style

- **Python**: Follow PEP 8. Use descriptive variable names. No one-letter variables outside of loop counters.
- **Comments**: Explain *why*, not *what*. The code explains what; comments explain intent.
- **No dead code**: Remove commented-out blocks before submitting.

---

## Commit Message Standard

Since Aqueitas *reads and reasons about commit messages*, your contributions must set the standard:

```
feat(brain): add retry logic for OpenAI embedding failures

The embedding endpoint occasionally returns 429 rate-limit errors under
burst load. Added exponential backoff with jitter (3 retries, max 8s delay)
to prevent ingestion pipeline failures during heavy commit sessions.
```

The header answers: what changed?
The body answers: why did it change, and what was the reasoning?

---

## Questions?

Open a discussion or an issue. We'd rather answer a question than see a contributor give up.
