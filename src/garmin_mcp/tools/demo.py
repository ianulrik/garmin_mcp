from fastmcp import FastMCP


def register(mcp: FastMCP, _client) -> None:
    @mcp.tool
    def add(a: int, b: int) -> int:
        """Legg sammen to heltall og returner summen."""
        return a + b
