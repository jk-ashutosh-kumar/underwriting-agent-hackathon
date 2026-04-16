"""Extractor agent: page-by-page vision extraction guided by JSON schema."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable, Coroutine

from openai import AsyncOpenAI, RateLimitError

from ingestion.file_utils import image_to_b64, prepare_pages_for_extractor
from ingestion.state import DocumentState

logger = logging.getLogger(__name__)

# Disable the built-in fast retries (0.5 s – 8 s) — they stay inside the
# same RPM/TPM window and achieve nothing.  We apply our own backoff below.
client = AsyncOpenAI(max_retries=0)

# Global semaphore: caps concurrent in-flight OpenAI calls across all
# pipelines so a burst of large documents cannot saturate the rate limit.
_OPENAI_CONCURRENCY = int(os.getenv("OPENAI_CONCURRENCY", "3"))
_openai_sem = asyncio.Semaphore(_OPENAI_CONCURRENCY)

# Backoff schedule for RateLimitError (seconds).
# Each delay is long enough to outlast the RPM/TPM window (~60 s).
_RATE_LIMIT_BACKOFF = [10, 30, 60, 120]


async def _call_openai(
    coro_fn: Callable[[], Coroutine[Any, Any, Any]],
) -> Any:
    """Call an OpenAI coroutine through the semaphore with rate-limit backoff.

    On a 429, waits for intervals in _RATE_LIMIT_BACKOFF (10 s, 30 s, 60 s,
    120 s) before retrying — long enough to actually clear the rate-limit
    window instead of hammering the same window repeatedly.
    """
    for attempt, backoff in enumerate(_RATE_LIMIT_BACKOFF + [None]):
        async with _openai_sem:
            try:
                return await coro_fn()
            except RateLimitError:
                if backoff is None:
                    raise  # exhausted all retries
                logger.warning(
                    "[Extractor] Rate limited (attempt %d/%d), "
                    "waiting %ds before retry …",
                    attempt + 1,
                    len(_RATE_LIMIT_BACKOFF),
                    backoff,
                )
        # Sleep *outside* the semaphore so the slot is free for other callers.
        await asyncio.sleep(backoff)

EXTRACT_PROMPT = """
You are a precise document data extraction engine.
Extract ALL data from this document page strictly following this JSON Schema:

{schema}

Rules:
- Return ONLY a valid JSON object conforming to the schema above.
- If a field is not present on this page, omit it entirely.
- For array fields (like transactions), include only items visible on THIS page.
- Do not invent or hallucinate data. Extract only what is visible.
- In case of bank statements, carefully extract all transactions,dates,amounts,transaction_type(debit/credit), and descriptions.
- Numbers must be numeric (not strings). Dates as strings in original format.
- No markdown. No explanation. JSON only.
"""


async def extract_node(state: DocumentState) -> DocumentState:
    if state["status"] == "failed":
        return state

    try:
        pages = prepare_pages_for_extractor(
            state["file_bytes"], state["content_type"]
        )
        schema_str = json.dumps(state["schema"], indent=2)
        page_outputs = []

        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        for i, page in enumerate(pages):
            b64 = image_to_b64(page)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": EXTRACT_PROMPT.format(schema=schema_str),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ]

            resp = await _call_openai(
                lambda m=messages: client.chat.completions.create(
                    model=model,
                    messages=m,
                    response_format={"type": "json_object"},
                    max_tokens=4000,
                    temperature=0.2,
                )
            )

            page_json = json.loads(resp.choices[0].message.content)
            for txn in page_json.get("transactions", []):
                txn["page"] = i + 1
            page_outputs.append(page_json)
            print(f"  [Extractor] Page {i + 1}/{len(pages)} done")

        return {
            **state,
            "page_outputs": page_outputs,
            "status": "merging",
        }

    except Exception as e:
        return {
            **state,
            "status": "failed",
            "error": f"Extractor error: {str(e)}",
        }
