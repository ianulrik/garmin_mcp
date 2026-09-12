from fastmcp import FastMCP


def register(mcp: FastMCP, client) -> None:
    @mcp.tool
    def get_last_activities(limit: int = 5) -> list[dict]:
        """Hent de siste treningsøktene fra Garmin Connect som et kort sammendrag."""
        activities = client.get_activities(0, limit)
        return [
            {
                "navn": a.get("activityName"),
                "type": (a.get("activityType") or {}).get("typeKey"),
                "dato": a.get("startTimeLocal"),
                "varighet_min": round(a.get("duration", 0) / 60, 1),
                "distanse_km": round(a["distance"] / 1000, 2) if a.get("distance") else None,
            }
            for a in activities
        ]
