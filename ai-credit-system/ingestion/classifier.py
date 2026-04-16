"""Classifier agent: vision-based document type detection."""

from __future__ import annotations

import json
import os

from openai import AsyncOpenAI

from ingestion.db import fetch_schema, update_document
from ingestion.file_utils import image_to_b64, prepare_pages_for_classifier
from ingestion.state import DocumentState

client = AsyncOpenAI()

KNOWN_TYPES = [
    "bank_statement",
    "salary_slip",
    "invoice",
    "tax_return",
    "identity_document",
    "credcheck_report",
    "unknown",
]

CLASSIFY_PROMPT = """
You are a document classification expert.
Look at the provided document page image(s) carefully.
Identify the document type from this list:
{types}

Return ONLY a valid JSON object in this exact format:
{{"document_type": "<type_from_list>", "confidence": "<high|medium|low>"}}
No explanation. No markdown. JSON only.
"""


async def classify_node(state: DocumentState) -> DocumentState:
    try:
        pages = prepare_pages_for_classifier(
            state["file_bytes"], state["content_type"]
        )

        image_blocks = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_to_b64(p)}",
                    "detail": "low",
                },
            }
            for p in pages
        ]

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": CLASSIFY_PROMPT.format(
                            types=", ".join(KNOWN_TYPES)
                        ),
                    },
                    *image_blocks,
                ],
            }
        ]

        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=100,
            temperature=0.2,
        )

        result = json.loads(resp.choices[0].message.content)
        doc_type = result.get("document_type", "unknown")

        if doc_type == "unknown":
            return {
                **state,
                "document_type": "unknown",
                "schema": None,
                "status": "failed",
                "error": "Document type could not be determined",
            }

        schema = fetch_schema(doc_type)
        if not schema:
            update_document(state["document_id"], doc_type=doc_type, status="failed")
            return {
                **state,
                "document_type": doc_type,
                "schema": None,
                "status": "failed",
                "error": f"No schema registered for type: {doc_type}",
            }

        update_document(state["document_id"], doc_type=doc_type, status="extracting")
        return {
            **state,
            "document_type": doc_type,
            "schema": schema,
            "status": "extracting",
        }

    except Exception as e:
        update_document(state["document_id"], status="failed")
        return {
            **state,
            "status": "failed",
            "error": f"Classifier error: {str(e)}",
        }
