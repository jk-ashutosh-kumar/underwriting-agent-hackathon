"""Local webhook listener.

Starts a small HTTP server that receives document.extraction.completed events
and prints them to the terminal.  Run this alongside the main API server, then
register its URL so events are delivered automatically.

Usage:
    # 1. Start the listener (default port 9000)
    python webhook_listener.py

    # 2. Register it with the API server (in another terminal)
    curl -s -X POST http://localhost:8010/api/webhooks/register \
         -H "Content-Type: application/json" \
         -d '{"url": "http://localhost:9000/webhook"}' | python -m json.tool

    # 3. Upload a document to trigger the event
    curl -s -X POST http://localhost:8010/api/parse-document \
         -F "company_id=acme" \
         -F "files[]=@/path/to/statement.pdf"

    # Options
    python webhook_listener.py --port 9001   # custom port
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request, Response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("webhook_listener")

listener = FastAPI(title="Webhook Listener")


@listener.post("/webhook")
async def receive_webhook(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": await request.body()}

    event = payload.get("event", "unknown")
    case_id = payload.get("case_id", "—")
    document_id = payload.get("document_id", "—")
    ts = payload.get("timestamp", datetime.utcnow().isoformat())

    logger.info(
        "\n"
        "┌─────────────────────────────────────────────────────┐\n"
        "│  WEBHOOK RECEIVED                                   │\n"
        "├─────────────────────────────────────────────────────┤\n"
        "│  event       : %-36s│\n"
        "│  case_id     : %-36s│\n"
        "│  document_id : %-36s│\n"
        "│  timestamp   : %-36s│\n"
        "└─────────────────────────────────────────────────────┘",
        event, case_id, document_id, ts,
    )
    print("\nFull payload:\n" + json.dumps(payload, indent=2))

    return Response(content='{"status":"ok"}', media_type="application/json")


@listener.get("/health")
def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local webhook listener")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on (default: 9000)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    logger.info("Webhook listener starting on http://%s:%s/webhook", args.host, args.port)
    logger.info("Register with: curl -X POST http://localhost:8010/api/webhooks/register "
                "-H 'Content-Type: application/json' "
                "-d '{\"url\": \"http://localhost:%s/webhook\"}'", args.port)

    uvicorn.run(listener, host=args.host, port=args.port, log_level="warning")
