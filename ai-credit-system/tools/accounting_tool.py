"""Simple accounting tool used by CrewAI agents."""

from __future__ import annotations

try:
    # Optional import: if CrewAI BaseTool is available, we use it.
    # This keeps the tool compatible with Agent(tools=[...]) in CrewAI.
    from crewai.tools import BaseTool
except Exception:  # pragma: no cover - fallback for lightweight environments
    class BaseTool:  # type: ignore[override]
        """Minimal fallback BaseTool for environments without CrewAI tools module."""

        name = "BaseTool"
        description = "Fallback tool class."


class AccountingModuleTool(BaseTool):
    """
    Mock accounting module tool.

    This tool intentionally returns static text for demo reliability.
    Later, this can be upgraded to:
    - read CSV/Excel into Pandas dataframes
    - convert natural-language query to SQL
    - execute queries against a finance warehouse
    """

    name: str = "AccountingModuleTool"
    description: str = "Query accounting indicators and repayment behavior."

    def _run(self, query: str) -> str:
        """Return a deterministic mock response for transparent demos."""
        _ = query
        return "Partner has 95% on-time payments"

    # Compatibility helper for non-CrewAI direct calls.
    def run(self, query: str) -> str:
        """Alias to keep usage simple across the codebase."""
        return self._run(query)
