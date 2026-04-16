"""Simple accounting tool used by CrewAI agents."""

from __future__ import annotations

# CrewAI versions differ on where BaseTool lives; try all known paths so
# Agent(tools=[AccountingModuleTool()]) does not hit internal KeyError 'tools'.
try:
    from crewai.tools import BaseTool as _CrewBaseTool  # type: ignore
except Exception:  # pragma: no cover
    try:
        from crewai.tools.base_tool import BaseTool as _CrewBaseTool  # type: ignore
    except Exception:  # pragma: no cover
        try:
            from langchain_core.tools import BaseTool as _CrewBaseTool  # type: ignore
        except Exception:  # pragma: no cover
            _CrewBaseTool = None  # type: ignore

if _CrewBaseTool is not None:
    BaseTool = _CrewBaseTool
else:

    class BaseTool:  # type: ignore[override]
        """Fallback when no real BaseTool import succeeded (Crew wiring will skip tools)."""

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

    def _run(self, query: str = "", **_: object) -> str:
        """Return a deterministic mock response for transparent demos.

        CrewAI tool runners may pass framework kwargs (e.g. ``verbose``), so we
        accept and ignore extra keyword arguments for compatibility.
        """
        _ = query
        return "Partner has 95% on-time payments"

    # Compatibility helper for non-CrewAI direct calls.
    def run(self, query: str = "", **kwargs: object) -> str:
        """Alias to keep usage simple across the codebase."""
        return self._run(query, **kwargs)
