from datetime import date

from fastmcp import FastMCP

from garmin_mcp.tools.fmt import rnd

# Garmins inndeling av stressnivå (0–100). Negative verdier betyr aktivitet eller
# for mye bevegelse til å måle, og telles ikke.
_STRESS_BANDS = (("hvile", 0, 25), ("lav", 26, 50), ("middels", 51, 75), ("hoy", 76, 100))


def _stress_minutes(samples: list) -> dict:
    """Minutter i hvert stressnivå, fra [tidsstempel_ms, nivå]-par."""
    measured = [(ts, level) for ts, level in samples if level is not None]
    totals = {name: 0.0 for name, _, _ in _STRESS_BANDS}
    for (ts, level), (next_ts, _) in zip(measured, measured[1:]):
        for name, low, high in _STRESS_BANDS:
            if low <= level <= high:
                totals[name] += (next_ts - ts) / 60000
    return {f"{name}_min": round(value) for name, value in totals.items()}


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

    @mcp.tool
    def get_stress_summary(day: str | None = None) -> dict:
        """Hent stressnivå for en dato (YYYY-MM-DD): snitt, maks, minutter i hvile/lav/
        middels/høy stress, og Body Battery-høyeste og -laveste. Default: i dag."""
        day = day or date.today().isoformat()
        raw = client.get_stress_data(day) or {}
        body_battery = [v[2] for v in raw.get("bodyBatteryValuesArray") or [] if len(v) > 2 and v[2] is not None]
        return {
            "dato": day,
            "snitt_stress": raw.get("avgStressLevel"),
            "maks_stress": raw.get("maxStressLevel"),
            **_stress_minutes(raw.get("stressValuesArray") or []),
            "body_battery_hoyest": max(body_battery, default=None),
            "body_battery_lavest": min(body_battery, default=None),
            "body_battery_siste": body_battery[-1] if body_battery else None,
        }

    @mcp.tool
    def get_spo2_summary(day: str | None = None) -> dict:
        """Hent blodoksygen (SpO2, %) for en dato (YYYY-MM-DD). Default: i dag."""
        day = day or date.today().isoformat()
        raw = client.get_spo2_data(day) or {}
        return {
            "dato": day,
            "snitt": rnd(raw.get("averageSpO2")),
            "laveste": raw.get("lowestSpO2"),
            "snitt_under_sovn": rnd(raw.get("avgSleepSpO2")),
            "siste_7_dager_snitt": rnd(raw.get("lastSevenDaysAvgSpO2")),
            "siste_maling": raw.get("latestSpO2"),
        }

    @mcp.tool
    def get_training_readiness(day: str | None = None) -> dict:
        """Hent treningsberedskap og anbefalt restitusjonstid for en dato (YYYY-MM-DD).
        Viser den siste målingen den dagen (den oppdateres etter hver økt), med
        faktorene bak: søvn, restitusjonstid, belastning, HRV og stress. Default: i dag."""
        day = day or date.today().isoformat()
        entries = client.get_training_readiness(day) or []
        if not entries:
            return {"dato": day, "melding": "Ingen treningsberedskap registrert denne dagen."}
        latest = max(entries, key=lambda e: e.get("timestampLocal") or "")
        recovery_min = latest.get("recoveryTime")
        return {
            "dato": day,
            "tidspunkt": latest.get("timestampLocal"),
            "score": latest.get("score"),
            "niva": latest.get("level"),
            "tilbakemelding": latest.get("feedbackShort"),
            "restitusjonstid_timer": round(recovery_min / 60, 1) if recovery_min is not None else None,
            "faktorer_prosent": {
                "sovn": latest.get("sleepScoreFactorPercent"),
                "sovnhistorikk": latest.get("sleepHistoryFactorPercent"),
                "restitusjonstid": latest.get("recoveryTimeFactorPercent"),
                "belastning": latest.get("acwrFactorPercent"),
                "hrv": latest.get("hrvFactorPercent"),
                "stresshistorikk": latest.get("stressHistoryFactorPercent"),
            },
            "sovn_score": latest.get("sleepScore"),
            "akutt_belastning": latest.get("acuteLoad"),
            "hrv_ukessnitt": latest.get("hrvWeeklyAverage"),
        }
