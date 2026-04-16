# Backend API Endpoints Documentation

This document provides a detailed explanation of the backend API endpoints, including their inputs, processing logic, and outputs.

## 1. `/api/health`
- **Method**: GET
- **Description**: Returns the health status of the API.
- **Input**: None
- **Processing**: Simple health check.
- **Output**:
  ```json
  {
    "status": "ok"
  }
  ```

## 2. `/api/sample`
- **Method**: GET
- **Description**: Returns a sample financial statement.
- **Input**: None
- **Processing**:
  - Reads the `sample_statement.json` file.
  - Returns its content.
- **Output**: JSON content of the sample file.

## 3. `/api/regions`
- **Method**: GET
- **Description**: Returns the supported regions.
- **Input**: None
- **Processing**:
  - Reads the `regional_rules.json` file.
  - Extracts and returns the keys (regions).
- **Output**:
  ```json
  ["India", "Philippines"]
  ```

## 4. `/api/debug/persistence`
- **Method**: GET
- **Description**: Returns a quick persistence health snapshot for debugging.
- **Input**: None
- **Processing**:
  - Loads memory and checkpoint data.
  - Extracts the last case details and checkpoint risk score.
- **Output**:
  ```json
  {
    "cases_count": 10,
    "last_case_id": "case-10",
    "last_case_timestamp": "2026-04-16T12:00:00Z",
    "last_checkpoint_decision_status": "APPROVED",
    "last_checkpoint_risk_score": 75
  }
  ```

## 5. `/api/parse-document`
- **Method**: POST
- **Description**: Parses an uploaded document into financial data.
- **Input**:
  ```json
  {
    "file_name": "document.pdf",
    "file_type": "pdf"
  }
  ```
- **Processing**:
  - Validates the file type.
  - Parses the document using the `parse_document` function.
- **Output**:
  ```json
  {
    "applicant_id": null,
    "statement_month": null,
    "transactions": [],
    "total_inflow": 0,
    "total_outflow": 0
  }
  ```

## 6. `/api/underwrite`
- **Method**: POST
- **Description**: Runs the full underwriting flow and returns structured results.
- **Input**:
  ```json
  {
    "data": {
      "applicant_id": "SME-1029",
      "statement_month": "2026-03",
      "transactions": [
        {
          "date": "2026-03-01",
          "description": "Retail Sales Deposit",
          "amount": 95000.0,
          "type": "credit"
        }
      ],
      "total_inflow": 95000.0,
      "total_outflow": 0.0
    },
    "region": "India",
    "human_response": "approved"
  }
  ```
- **Processing**:
  - Runs the underwriting flow using the provided data.
  - Generates a decision and risk score.
- **Output**:
  ```json
  {
    "risk_score": 75,
    "decision_status": "APPROVED",
    "agent_logs": ["Log details..."],
    "audit": {"risk_score": 75, "flags": [], "explanation": "..."},
    "trend": {"profit": 95000.0, "trend": "growing", "insight": "..."},
    "benchmark": {"benchmark_result": "...", "comparison_insight": "..."},
    "final_summary": "...",
    "crew_status": "...",
    "needs_hitl": false
  }
  ```

## 7. `/api/underwrite/stream`
- **Method**: POST
- **Description**: Streams the underwriting flow progress as NDJSON.
- **Input**: Same as `/api/underwrite`.
- **Processing**:
  - Runs the underwriting flow.
  - Streams progress and final results.
- **Output**: NDJSON stream with progress and result objects.

## 8. `/api/underwrite/langgraph/start`
- **Method**: POST
- **Description**: Starts a LangGraph underwriting thread and pauses on HITL if needed.
- **Input**: Same as `/api/underwrite`.
- **Processing**:
  - Initiates the LangGraph underwriting flow.
  - Pauses for human input if required.
- **Output**:
  ```json
  {
    "status": "NEEDS_INPUT",
    "thread_id": "thread-123",
    "active_index": 2,
    "label": "HITL",
    "logs": ["Log details..."],
    "decision": "PENDING",
    "hitl_context": {"reason": "large_transaction"}
  }
  ```

## 9. `/api/underwrite/langgraph/resume`
- **Method**: POST
- **Description**: Resumes a paused LangGraph underwriting thread with human clarification.
- **Input**: Same as `/api/underwrite`.
- **Processing**:
  - Resumes the underwriting flow from the paused state.
- **Output**: Same as `/api/underwrite`.

---

This document provides a comprehensive overview of the backend API endpoints, their inputs, processing logic, and outputs.