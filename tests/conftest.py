import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Brain modules (services.embedding etc.) are imported flat, exactly as the
# Brain itself imports them when uvicorn runs from the brain directory.
sys.path.insert(0, str(ROOT / "brain"))
sys.path.insert(0, str(ROOT))

# Unit tests must run without paid APIs. setdefault keeps a developer's
# explicit override (or an integration run) intact.
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("REASONING_PROVIDER", "passthrough")
