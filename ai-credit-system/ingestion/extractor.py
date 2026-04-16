"""Extractor agent: page-by-page vision extraction guided by JSON schema."""

from __future__ import annotations

import json
import os

from openai import AsyncOpenAI

from ingestion.file_utils import image_to_b64, prepare_pages_for_extractor
from ingestion.state import DocumentState

client = AsyncOpenAI()

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

            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=4000,
                temperature=0.2,
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
