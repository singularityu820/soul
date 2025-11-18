import asyncio
import json
from pathlib import Path
from typing import Dict

_STORE_PATH = Path(__file__).resolve().parents[2] / "storage" / "info_store.json"
_STORE_LOCK = asyncio.Lock()


def _load_store() -> Dict[str, str]:
    if not _STORE_PATH.exists():
        return {}
    try:
        raw = _STORE_PATH.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def _save_store(store: Dict[str, str]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(
        json.dumps(store, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


async def read_info(name: str) -> str:
    async with _STORE_LOCK:
        store = _load_store()
        return store.get(name, "")


async def write_info(name: str, value: str) -> None:
    async with _STORE_LOCK:
        store = _load_store()
        store[name] = value
        _save_store(store)
