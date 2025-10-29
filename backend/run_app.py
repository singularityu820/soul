"""Simple starter script for local development.

Run this from the `backend` directory with:
    python run_app.py

This script ensures the `backend` folder is on sys.path so relative imports
inside `app` resolve correctly and then starts uvicorn to serve the FastAPI
application defined in `app.main:app`.

If uvicorn is not installed the script prints an actionable hint.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend directory is on sys.path so `import app` works with relative imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    try:
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
    except Exception as exc:
        print("Failed to start uvicorn. Ensure it's installed in your environment.")
        print("Install with: pip install \"uvicorn[standard]\"")
        print()
        print("Alternatively, from the backend folder run:")
        print("  python -m uvicorn app.main:app --reload --port 8000")
        print()
        print("Error details:", exc)
