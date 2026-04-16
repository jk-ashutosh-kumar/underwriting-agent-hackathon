"""Small wrapper for provider-backed JSON responses."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse plain JSON or JSON embedded in markdown fences."""
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.replace("```json", "").replace("```", "").strip()
    try:
        payload = json.loads(clean)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        return None
    return None


def ask_llm_json(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """
    Request a JSON object from an LLM.

    Raises:
        RuntimeError: if API key is missing or JSON parse fails.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Cannot run live LLM mode.")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - environment dependency issue
        raise RuntimeError("openai package is not installed in this environment.") from exc

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content or ""
    parsed = _extract_json_block(content)
    if parsed is None:
        raise RuntimeError("LLM response was not valid JSON.")
    return parsed

