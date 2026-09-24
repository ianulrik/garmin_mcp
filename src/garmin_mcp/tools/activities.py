from fastmcp import FastMCP


def _round(value, digits: int = 0):
    if value is None:
        return None
    return round(value, digits) if digits else round(value)


def _minutes(seconds) -> float | None:
    return round(seconds / 60, 1) if seconds else None


def _km(meters) -> float | None:
    return round(meters / 1000, 2) if meters else None


# Tempo (min/km) gir bare mening for aktiviteter til fots — for sykling o.l. holder km/t.
_PACE_TYPES = ("running", "walking", "hiking", "trail", "treadmill", "track")


def _uses_pace(activity_type: str | None) -> bool:
    return any(t in (activity_type or "") for t in _PACE_TYPES)


def _pace(speed_mps, activity_type: str | None) -> str | None:
    """Garmin oppgir fart i m/s — gjør om til løpetempo som 'm:ss' per km."""
    if not speed_mps or not _uses_pace(activity_type):
        return None
    total_seconds = round(1000 / speed_mps)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def _kmh(speed_mps) -> float | None:
    return round(speed_mps * 3.6, 1) if speed_mps else None


def _summary(s: dict, activity_type: str | None) -> dict:
    """Nøkkeltall for hele økten, fra summaryDTO i get_activity()."""
    return {
        "varighet_min": _minutes(s.get("duration")),
        "bevegelsestid_min": _minutes(s.get("movingDuration")),
        "distanse_km": _km(s.get("distance")),
        "snitt_tempo_min_per_km": _pace(s.get("averageSpeed"), activity_type),
        "snitt_fart_kmt": _kmh(s.get("averageSpeed")),
        "snitt_puls": _round(s.get("averageHR")),
        "maks_puls": _round(s.get("maxHR")),
        "min_puls": _round(s.get("minHR")),
        "snitt_kadens": _round(s.get("averageRunCadence")),
        "snitt_watt": _round(s.get("averagePower")),
        "normalisert_watt": _round(s.get("normalizedPower")),
        "hoydemeter_opp": _round(s.get("elevationGain")),
        "hoydemeter_ned": _round(s.get("elevationLoss")),
        "kalorier": _round(s.get("calories")),
        "aerob_treningseffekt": _round(s.get("trainingEffect"), 1),
        "anaerob_treningseffekt": _round(s.get("anaerobicTrainingEffect"), 1),
        "treningseffekt": s.get("trainingEffectLabel"),
        "treningsbelastning": _round(s.get("activityTrainingLoad")),
        "body_battery_endring": s.get("differenceBodyBattery"),
        # Garmin lagrer RPE som 10–100; skalaen i appen er 1–10.
        "opplevd_anstrengelse_rpe": s["directWorkoutRpe"] // 10 if s.get("directWorkoutRpe") else None,
    }


def _lap(lap: dict, activity_type: str | None) -> dict:
    """Én runde/split fra get_activity_splits()."""
    return {
        "runde": lap.get("lapIndex"),
        "type": lap.get("intensityType"),
        "varighet_sek": _round(lap.get("duration")),
        "distanse_km": _km(lap.get("distance")),
        "tempo_min_per_km": _pace(lap.get("averageSpeed"), activity_type),
        "fart_kmt": _kmh(lap.get("averageSpeed")),
        "snitt_puls": _round(lap.get("averageHR")),
        "maks_puls": _round(lap.get("maxHR")),
        "snitt_kadens": _round(lap.get("averageRunCadence")),
        "snitt_watt": _round(lap.get("averagePower")),
        "hoydemeter_opp": _round(lap.get("elevationGain")),
    }


def _hr_zones(zones: list[dict]) -> list[dict]:
    return [
        {
            "sone": z.get("zoneNumber"),
            "fra_puls": z.get("zoneLowBoundary"),
            "minutter": round((z.get("secsInZone") or 0) / 60, 1),
        }
        for z in zones
    ]


def register(mcp: FastMCP, client) -> None:
    @mcp.tool
    def get_last_activities(limit: int = 5) -> list[dict]:
        """Hent de siste treningsøktene fra Garmin Connect som et kort sammendrag
        med puls og tempo. Bruk activity_id med get_activity_details for runder/splits
        og pulssoner."""
        activities = client.get_activities(0, limit)
        return [
            {
                "activity_id": a.get("activityId"),
                "navn": a.get("activityName"),
                "type": (activity_type := (a.get("activityType") or {}).get("typeKey")),
                "dato": a.get("startTimeLocal"),
                "varighet_min": _minutes(a.get("duration")),
                "distanse_km": _km(a.get("distance")),
                "snitt_tempo_min_per_km": _pace(a.get("averageSpeed"), activity_type),
                "snitt_puls": _round(a.get("averageHR")),
                "maks_puls": _round(a.get("maxHR")),
                "kalorier": _round(a.get("calories")),
                "treningseffekt": a.get("trainingEffectLabel"),
                "treningsbelastning": _round(a.get("activityTrainingLoad")),
                "antall_runder": a.get("lapCount"),
            }
            for a in activities
        ]

    @mcp.tool
    def get_activity_details(activity_id: int) -> dict:
        """Hent detaljer for én treningsøkt: nøkkeltall (puls, tempo, kadens, watt,
        treningseffekt), tid i hver pulssone, og alle runder/splits med puls og tempo
        per runde. Runde-type viser WARMUP/ACTIVE/REST/COOLDOWN for strukturerte
        økter (ACTIVE = drag, REST = pause). Finn activity_id med get_last_activities."""
        activity = client.get_activity(activity_id) or {}
        splits = client.get_activity_splits(activity_id) or {}
        zones = client.get_activity_hr_in_timezones(activity_id) or []
        activity_type = (activity.get("activityTypeDTO") or {}).get("typeKey")
        summary = activity.get("summaryDTO") or {}
        return {
            "activity_id": activity_id,
            "navn": activity.get("activityName"),
            "type": activity_type,
            "dato": summary.get("startTimeLocal"),
            "sammendrag": _summary(summary, activity_type),
            "pulssoner": _hr_zones(zones),
            "runder": [_lap(lap, activity_type) for lap in splits.get("lapDTOs") or []],
        }
