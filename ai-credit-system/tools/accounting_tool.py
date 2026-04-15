"""Simple external accounting tool wrapper."""


class AccountingTool:
    """Mock tool to demonstrate external query calls."""

    def run(self, query: str) -> str:
        """Return mock response for a given accounting query."""
        return f"[AccountingTool] Processed query: '{query}'. Mock result returned."
