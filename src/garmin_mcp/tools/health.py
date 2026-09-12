from datetime import date

from fastmcp import FastMCP


def register(mcp: FastMCP, client) -> None:
    @mcp.tool
    def get_sleep_summary(day: str | None = None) -> dict:
        """Hent søvnsammendrag for en dato (YYYY-MM-DD). Default: i dag."""
        day = day or date.today().isoformat()
        raw = client.get_sleep_data(day) or {}
        dto = raw.get("dailySleepDTO") or {}
        overall = (dto.get("sleepScores") or {}).get("overall") or {}

        def minutes(seconds_key: str) -> float:
            return round((dto.get(seconds_key) or 0) / 60, 1)

        return {
            "dato": day,
            "total_sovn_min": minutes("sleepTimeSeconds"),
            "dyp_sovn_min": minutes("deepSleepSeconds"),
            "lett_sovn_min": minutes("lightSleepSeconds"),
            "rem_sovn_min": minutes("remSleepSeconds"),
            "vaken_min": minutes("awakeSleepSeconds"),
            "sovn_score": overall.get("value"),
            "sovn_kvalitet": overall.get("qualifierKey"),
        }

    @mcp.tool
    def get_hrv_summary(day: str | None = None) -> dict:
        """Hent HRV-sammendrag (hjertefrekvensvariabilitet) for en dato (YYYY-MM-DD). Default: i dag."""
        day = day or date.today().isoformat()
        raw = client.get_hrv_data(day) or {}
        summary = raw.get("hrvSummary") or {}
        return {
            "dato": day,
            "siste_natt_avg_ms": summary.get("lastNightAvg"),
            "ukentlig_avg_ms": summary.get("weeklyAvg"),
            "status": summary.get("status"),
        }
