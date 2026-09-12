from datetime import date

from fastmcp import FastMCP


def register(mcp: FastMCP, client) -> None:
    @mcp.tool
    def get_training_load(day: str | None = None) -> dict:
        """Hent treningsbelastning og -status for en dato (YYYY-MM-DD). Default: i dag."""
        day = day or date.today().isoformat()
        raw = client.get_training_status(day) or {}
        latest = (raw.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
        device_data = next(iter(latest.values()), {}) if latest else {}
        acute = device_data.get("acuteTrainingLoadDTO") or {}
        vo2max = ((raw.get("mostRecentVO2Max") or {}).get("generic") or {}).get("vo2MaxValue")
        return {
            "dato": day,
            "status": device_data.get("trainingStatusFeedbackPhrase"),
            "akutt_belastning": acute.get("dailyTrainingLoadAcute"),
            "kronisk_belastning": acute.get("dailyTrainingLoadChronic"),
            "belastningsforhold": acute.get("dailyAcuteChronicWorkloadRatio"),
            "belastning_status": acute.get("acwrStatus"),
            "vo2max": vo2max,
        }
