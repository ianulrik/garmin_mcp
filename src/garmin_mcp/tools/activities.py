from fastmcp import FastMCP

from garmin_mcp.tools.fmt import km, kmh, minutes, pace, rnd

# Tempo (min/km) gir bare mening for aktiviteter til fots — for sykling o.l. holder km/t.
_PACE_TYPES = ("running", "walking", "hiking", "trail", "treadmill", "track")


def _uses_pace(activity_type: str | None) -> bool:
    return any(t in (activity_type or "") for t in _PACE_TYPES)


def _is_swim(activity_type: str | None) -> bool:
    return "swim" in (activity_type or "")


def _run_pace(speed_mps, activity_type: str | None) -> str | None:
    return pace(speed_mps) if _uses_pace(activity_type) else None


def _nonzero(value):
    """Garmin fyller inn 0 for mål klokka ikke registrerte (f.eks. tak/SWOLF ved drill)."""
    return rnd(value) if value else None


def _summary(s: dict, activity_type: str | None) -> dict:
    """Nøkkeltall for hele økten, fra summaryDTO i get_activity()."""
    return {
        "varighet_min": minutes(s.get("duration")),
        "bevegelsestid_min": minutes(s.get("movingDuration")),
        "distanse_km": km(s.get("distance")),
        "snitt_tempo_min_per_km": _run_pace(s.get("averageSpeed"), activity_type),
        "snitt_fart_kmt": kmh(s.get("averageSpeed")),
        "snitt_puls": rnd(s.get("averageHR")),
        "maks_puls": rnd(s.get("maxHR")),
        "min_puls": rnd(s.get("minHR")),
        "snitt_kadens": rnd(s.get("averageRunCadence")),
        "snitt_watt": rnd(s.get("averagePower")),
        "normalisert_watt": rnd(s.get("normalizedPower")),
        "hoydemeter_opp": rnd(s.get("elevationGain")),
        "hoydemeter_ned": rnd(s.get("elevationLoss")),
        "kalorier": rnd(s.get("calories")),
        "aerob_treningseffekt": rnd(s.get("trainingEffect"), 1),
        "anaerob_treningseffekt": rnd(s.get("anaerobicTrainingEffect"), 1),
        "treningseffekt": s.get("trainingEffectLabel"),
        "treningsbelastning": rnd(s.get("activityTrainingLoad")),
        "body_battery_endring": s.get("differenceBodyBattery"),
        # Garmin lagrer RPE som 10–100; skalaen i appen er 1–10.
        "opplevd_anstrengelse_rpe": s["directWorkoutRpe"] // 10 if s.get("directWorkoutRpe") else None,
    }


def _swim_summary(s: dict) -> dict:
    # Snittfarten i summaryDTO er 0 for bassengsvømming — regn ut fra distanse og svømmetid.
    distance, moving = s.get("distance"), s.get("movingDuration")
    speed = distance / moving if distance and moving else None
    return {
        "basseng_lengde_m": rnd(s.get("poolLength")),
        "antall_lengder": s.get("numberOfActiveLengths"),
        "svommetid_min": minutes(moving),
        "snitt_tempo_per_100m": pace(speed, 100),
        "snitt_tak_per_lengde": _nonzero(s.get("averageStrokes")),
        "snitt_swolf": _nonzero(s.get("averageSWOLF")),
    }


def _lap(lap: dict, activity_type: str | None) -> dict:
    """Én runde/split fra get_activity_splits()."""
    return {
        "runde": lap.get("lapIndex"),
        "type": lap.get("intensityType"),
        "varighet_sek": rnd(lap.get("duration")),
        "distanse_km": km(lap.get("distance")),
        "tempo_min_per_km": _run_pace(lap.get("averageSpeed"), activity_type),
        "fart_kmt": kmh(lap.get("averageSpeed")),
        "snitt_puls": rnd(lap.get("averageHR")),
        "maks_puls": rnd(lap.get("maxHR")),
        "snitt_kadens": rnd(lap.get("averageRunCadence")),
        "snitt_watt": rnd(lap.get("averagePower")),
        "hoydemeter_opp": rnd(lap.get("elevationGain")),
    }


def _swim_lap(lap: dict) -> dict:
    """Én svømmerunde. Runder uten distanse er pauser ved bassengkanten."""
    lengths = [length for length in lap.get("lengthDTOs") or [] if length.get("distance")]
    return {
        "runde": lap.get("lapIndex"),
        "type": "REST" if not lap.get("distance") else lap.get("swimStroke"),
        "varighet_sek": rnd(lap.get("duration")),
        "distanse_m": rnd(lap.get("distance")),
        "tempo_per_100m": pace(lap.get("averageSpeed"), 100),
        "snitt_puls": rnd(lap.get("averageHR")),
        "maks_puls": rnd(lap.get("maxHR")),
        "snitt_tak_per_lengde": _nonzero(lap.get("averageStrokes")),
        "snitt_swolf": _nonzero(lap.get("averageSWOLF")),
        "lengder": [
            {
                "lengde": length.get("lengthIndex"),
                "svommeart": length.get("swimStroke"),
                "sek": round(length.get("duration") or 0, 1),
                "tempo_per_100m": pace(length.get("averageSpeed"), 100),
                "snitt_puls": rnd(length.get("averageHR")),
                "tak": _nonzero(length.get("totalNumberOfStrokes")),
            }
            for length in lengths
        ],
    }


def _zones(zones: list[dict], boundary_key: str) -> list[dict]:
    return [
        {
            "sone": z.get("zoneNumber"),
            boundary_key: z.get("zoneLowBoundary"),
            "minutter": round((z.get("secsInZone") or 0) / 60, 1),
        }
        for z in zones or []
    ]


def register(mcp: FastMCP, client) -> None:
    @mcp.tool
    def get_last_activities(limit: int = 5) -> list[dict]:
        """Hent de siste treningsøktene fra Garmin Connect som et kort sammendrag
        med puls og tempo. Bruk activity_id med get_activity_details for runder/splits,
        svømmelengder og puls-/wattsoner."""
        activities = client.get_activities(0, limit)
        return [
            {
                "activity_id": a.get("activityId"),
                "navn": a.get("activityName"),
                "type": (activity_type := (a.get("activityType") or {}).get("typeKey")),
                "dato": a.get("startTimeLocal"),
                "varighet_min": minutes(a.get("duration")),
                "distanse_km": km(a.get("distance")),
                "snitt_tempo_min_per_km": _run_pace(a.get("averageSpeed"), activity_type),
                "snitt_puls": rnd(a.get("averageHR")),
                "maks_puls": rnd(a.get("maxHR")),
                "snitt_watt": rnd(a.get("avgPower")),
                "kalorier": rnd(a.get("calories")),
                "treningseffekt": a.get("trainingEffectLabel"),
                "treningsbelastning": rnd(a.get("activityTrainingLoad")),
                "antall_runder": a.get("lapCount"),
            }
            for a in activities
        ]

    @mcp.tool
    def get_activity_details(activity_id: int) -> dict:
        """Hent detaljer for én treningsøkt: nøkkeltall (puls, tempo, kadens, watt,
        treningseffekt), tid i hver puls- og wattsone, og alle runder/splits med puls
        og tempo per runde. Runde-type viser WARMUP/ACTIVE/REST/COOLDOWN for strukturerte
        økter (ACTIVE = drag, REST = pause). For svømming: bassenglengde, tempo per 100 m
        og hver enkelt lengde med svømmeart. Finn activity_id med get_last_activities."""
        activity = client.get_activity(activity_id) or {}
        splits = client.get_activity_splits(activity_id) or {}
        hr_zones = client.get_activity_hr_in_timezones(activity_id) or []
        activity_type = (activity.get("activityTypeDTO") or {}).get("typeKey")
        summary = activity.get("summaryDTO") or {}
        laps = splits.get("lapDTOs") or []

        details = {
            "activity_id": activity_id,
            "navn": activity.get("activityName"),
            "type": activity_type,
            "dato": summary.get("startTimeLocal"),
            "sammendrag": _summary(summary, activity_type),
            "pulssoner": _zones(hr_zones, "fra_puls"),
        }
        # Wattsoner finnes bare når økten har wattdata — spar et API-kall ellers.
        if summary.get("averagePower"):
            power_zones = client.get_activity_power_in_timezones(activity_id)
            if power_zones:
                details["wattsoner"] = _zones(power_zones, "fra_watt")
        if _is_swim(activity_type):
            details["svomming"] = _swim_summary(summary)
            details["runder"] = [_swim_lap(lap) for lap in laps]
        else:
            details["runder"] = [_lap(lap, activity_type) for lap in laps]
        return details
