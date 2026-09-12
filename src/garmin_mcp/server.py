import os
import sys
from datetime import date

from fastmcp import FastMCP
from garminconnect import Garmin

# All logging/debug-utskrift MÅ gå til stderr, aldri stdout.
# stdio-transporten bruker stdout som binær meldingskanal mellom Claude
# Desktop og denne prosessen. Ett vagrant print() på stdout korrumperer
# protokollen og gir kryptiske feil i Claude Desktop. Bruk print(..., file=sys.stderr)
# eller `logging` konfigurert mot stderr.
print("garmin-mcp server starter", file=sys.stderr)

mcp = FastMCP("garmin-mcp")

TOKEN_STORE = os.path.expanduser("~/.garminconnect")


def _get_client() -> Garmin:
    # Ingen email/password/prompt_mfa her, med vilje: denne prosessen kjøres
    # av Claude Desktop uten en ekte terminal. Skulle garminconnect prøve å
    # falle tilbake på interaktiv innlogging, ville den prøve å lese stdin —
    # men stdin er MCP-protokollkanalen, ikke et tastatur. Det er
    # stdin-motstykket til stdout-fella over. Uten credentials her *kan*
    # ikke biblioteket falle tilbake til interaktiv login: finner den ikke
    # gyldige cachede tokens i TOKEN_STORE, feiler login() rent i stedet.
    client = Garmin()
    try:
        client.login(TOKEN_STORE)
    except Exception as e:
        print(f"Fant ingen gyldig Garmin-sesjon i {TOKEN_STORE}: {e}", file=sys.stderr)
        print("Kjør engangsoppsettet: uv run python -m garmin_mcp.auth", file=sys.stderr)
        raise SystemExit(1) from e
    return client


client = _get_client()


@mcp.tool
def add(a: int, b: int) -> int:
    """Legg sammen to heltall og returner summen."""
    return a + b


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


if __name__ == "__main__":
    mcp.run()
