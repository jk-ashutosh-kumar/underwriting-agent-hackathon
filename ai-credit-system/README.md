# AI Credit Underwriting System

Hackathon-ready multi-agent credit underwriting demo built with simple, explainable logic.

## Latest Developments (Phase 2)

The system now includes a **Multi-Agent Credit Committee** with clear personas, regional context, memory-backed comparison, and explainable outputs.

### 1) Multi-Agent Credit Committee

Three distinct agent personas are orchestrated in `agents/crew.py`:

- **Auditor Agent** (`Fraud Detection Specialist`)
  - Persona: skeptical forensic accountant who trusts no one.
  - Flags:
    - Large transactions above region threshold.
    - Repeated identical transaction amounts (possible round-tripping).
  - Output: `risk_score`, `flags`, and "why" explanation.

- **Trend Agent** (`Growth Analyst`)
  - Persona: data-driven strategist focused on growth.
  - Computes:
    - `profit = inflow - outflow`
    - Simple growth indicator (`growing`, `stable`, `shrinking`)
  - Output: `profit`, `trend`, and explainable insight.

- **Benchmark Agent** (`Portfolio Manager`)
  - Persona: experienced portfolio manager.
  - Compares current case with historical memory entries.
  - Fallback if memory unavailable: `"No historical comparison"`.

### 2) Regional Rules + Context Injection

Regional decision context is stored in `data/regional_rules.json` and injected into task descriptions and agent logic:

- Country-specific large transaction threshold
- DSCR threshold (future use)
- Regional keywords (for contextual interpretation)

Supported examples:

- `India`: large transaction threshold `100000`, keywords `UPI`, `GST`
- `Philippines`: large transaction threshold `80000`, keywords `Peso`, `Check`

### 3) Custom Accounting Tool

`tools/accounting_tool.py` now exposes `AccountingModuleTool` with:

- `_run(query: str)` -> mock deterministic output:
  - `"Partner has 95% on-time payments"`
- Comments showing future extension path:
  - Pandas ingestion
  - SQL conversion
  - Data warehouse querying

### 4) Simple Memory System

`memory/store.py` now includes:

- `load_memory()`
- `save_memory(entry)`

Memory is JSON-file based for reliability and speed in demos.  
Backward-compatible aliases are also preserved:

- `load_cases()` -> `load_memory()`
- `save_case(data)` -> `save_memory(data)`

### 5) Explainable Final Output

`run_crew(data, region)` returns:

```python
{
  "audit": ...,
  "trend": ...,
  "benchmark": ...,
  "final_summary": "...",
  "crew_status": "..."
}
```

`final_summary` combines:

- fraud risk
- growth/profit signal
- benchmark insight
- accounting tool signal

## Environment Setup (Secrets)

This project supports `.env`-based secrets loaded via `python-dotenv`.

1. Create/activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure secrets:

- Copy `.env.example` to `.env` and fill values:
  - `OPENAI_API_KEY`
  - `DB_URL`

`.env` is ignored by git through `.gitignore`.

## How to Run

### Option A: One-command app run

```bash
./run_app.sh
```

This script:

- creates `.venv` if missing
- installs dependencies
- launches Streamlit UI

### Option B: Manual run

```bash
source .venv/bin/activate
streamlit run ui/app.py
```

### Option C: Run committee directly (CLI test)

```bash
python agents/crew.py
```

This executes the built-in test block and prints the full committee output for `region="India"`.

## Project Structure

- `app/main.py`: End-to-end CLI pipeline runner.
- `ingestion/parser.py`: Mock parser.
- `agents/`
  - `auditor.py`: Fraud/anomaly checks + explainable risk rationale.
  - `trend.py`: Profit + growth trend logic + explanation.
  - `benchmark.py`: Historical comparison using memory.
  - `crew.py`: CrewAI committee setup + region-aware orchestration.
- `tools/accounting_tool.py`: Custom accounting query tool (`AccountingModuleTool`).
- `memory/store.py`: JSON memory load/save (`load_memory`, `save_memory`).
- `graph/flow.py`: Final underwriting decision helper.
- `ui/app.py`: Streamlit UI.
- `data/sample_statement.json`: Sample financial input.
- `data/regional_rules.json`: Region-specific policy context.
- `data/cases_memory.json`: Stored historical cases.

## Demo Notes

- Prioritize **explainability**: each agent includes a clear "why".
- Prioritize **reliability**: deterministic logic, minimal dependencies.
- Prioritize **clarity**: visible agent personalities and chained outputs.
