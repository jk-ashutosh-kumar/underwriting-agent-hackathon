"""Webhook registry and dispatcher.

Webhook URLs are persisted to data/webhooks.json so registrations survive
server restarts.  The dispatcher fires async HTTP POST requests; failures are
logged but never raise so they cannot break the extraction pipeline.

Payload sent on every ``document.extraction.completed`` event:

    {
        "event": "document.extraction.completed",
        "case_id": "<uuid>",
        "document_id": "<uuid>",
        "timestamp": "<iso8601>"
    }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import httpx

logger = logging.getLogger(__name__)

_STORE_FILE = Path(__file__).resolve().parent / "data" / "webhooks.json"


# --------------------------------------------------------------------------- #
# Registry (file-backed)
# --------------------------------------------------------------------------- #

def _load() -> List[str]:
    try:
        return json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(urls: List[str]) -> None:
    _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STORE_FILE.write_text(json.dumps(urls, indent=2), encoding="utf-8")


def register(url: str) -> bool:
    """Add *url* to the registry.  Returns True if added, False if already present."""
    urls = _load()
    if url in urls:
        return False
    urls.append(url)
    _save(urls)
    logger.info("webhook_registered url=%s", url)
    return True


def unregister(url: str) -> bool:
    """Remove *url* from the registry.  Returns True if removed, False if not found."""
    urls = _load()
    if url not in urls:
        return False
    urls.remove(url)
    _save(urls)
    logger.info("webhook_unregistered url=%s", url)
    return True


def list_webhooks() -> List[str]:
    return _load()


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #

async def fire_extraction_completed(case_id: str, document_id: str) -> None:
    """POST ``document.extraction.completed`` to every registered URL.

    Runs asynchronously; individual delivery failures are logged and skipped so
    the extraction pipeline is never blocked or broken.
    """
    urls = _load()
    if not urls:
        return

    payload = {
        "event": "document.extraction.completed",
        "case_id": case_id,
        "document_id": document_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in urls:
            try:
                response = await client.post(url, json=payload)
                logger.info(
                    "webhook_delivered url=%s status=%s",
                    url,
                    response.status_code,
                )
            except Exception as exc:
                logger.warning("webhook_delivery_failed url=%s error=%s", url, exc)
