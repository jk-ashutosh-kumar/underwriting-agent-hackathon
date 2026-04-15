# AI Credit Underwriting System

A hackathon-friendly, production-style monorepo scaffold for an AI-powered credit underwriting pipeline.

## Project Overview

This project is organized in clear modular phases:

1. **Ingestion**: Parse a statement document into normalized JSON.
2. **Multi-Agent Analysis**: Run Auditor, Trend Analyst, and Benchmarker logic via a CrewAI-style crew module.
3. **Decision Flow**: Make a simple underwriting decision from risk score.
4. **Memory**: Save case results in a local JSON memory file.
5. **UI**: Streamlit dashboard for uploading data and running analysis.

The system is intentionally simple and uses mock logic where useful, so it can run quickly in a hackathon.

## How to Run

1. Run the app with one script:

```bash
./run_app.sh
```

This script will:

- Create `.venv` if missing
- Install dependencies from `requirements.txt`
- Launch Streamlit UI

2. Optional manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run ui/app.py
```

## Folder Structure

- `app/main.py`: End-to-end CLI pipeline runner.
- `ingestion/parser.py`: Mock parser (`parse_document`).
- `agents/`: Individual agent logic and crew orchestrator.
  - `auditor.py`: Flags high-value transactions and outputs risk score.
  - `trend.py`: Computes inflow/outflow profit trend.
  - `benchmark.py`: Returns mock benchmark result.
  - `crew.py`: Builds CrewAI objects (if available) and combines outputs.
- `graph/flow.py`: Simple decision state function (`APPROVED` or `HUMAN_REVIEW`).
- `memory/store.py`: JSON file-based memory save/load.
- `tools/accounting_tool.py`: Mock accounting query tool.
- `ui/app.py`: Streamlit dashboard.
- `data/sample_statement.json`: Dummy financial transaction data.
- `requirements.txt`: Minimal dependencies.

## Single-Command End-to-End

For the full user flow (upload/sample + analysis + decision + memory), use:

```bash
./run_app.sh
```

Click **Run Analysis** in the UI to execute the complete pipeline.
