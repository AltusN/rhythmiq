"""
Dump the FastAPI app's OpenAPI schema to a file (or stdout) without running a server.
Imports app.main directly -- same trick as migrations/env.py importing app metadata.
The DB engine is created at import time but never connects, so a placeholder URL is
enough when the real env var isn't set.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("POSTGRESQL_DATABASE_URL", "postgresql+psycopg://placeholder/placeholder")

from app.main import app  # noqa: E402


def main() -> None:
    schema = json.dumps(app.openapi(), indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(schema + "\n")
    else:
        print(schema)


if __name__ == "__main__":
    main()
