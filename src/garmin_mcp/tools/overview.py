"""Oversikt over en treningsperiode: ukessummer, daglige trender og dagens status.

Samme data brukes både av MCP-verktøyet get_training_overview og av
dashboardet (garmin_mcp.dashboard), så Claude og grafene ser de samme tallene.
"""

import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastmcp import FastMCP

from garmin_mcp.tools.fmt import km, rnd

# Rekkefølgen her er også fargerekkefølgen i dashboardet.
SPORTS = ("lop", "sykkel", "styrke", "svomming", "annet")
_SPORT_KEYS = (
    ("svomming", ("swim",)),
    ("lop", ("run", "track", "treadmill", "trail")),
    ("sykkel", ("cycl", "bik", "ride")),
    ("styrke", ("strength", "fitness_equipment", "hiit")),
)

_TRAINING_STATUS = {
    "PRODUCTIVE": "Produktiv",
    "MAINTAINING": "Vedlikehold",
    "RECOVERY": "Restitusjon",
    "UNPRODUCTIVE": "Uproduktiv",
    "DETRAINING": "Avtrening",
    "OVERREACHING": "Overbelastning",
    "PEAKING": "Toppform",
    "STRAINED": "Anstrengt",
    "NO_STATUS": "Ingen status",
}

_LOAD_BALANCE = {
    "AEROBIC_LOW_FOCUS": "Mangler lav aerob belastning",
    "AEROBIC_HIGH_FOCUS": "Mangler høy aerob belastning",
    "ANAEROBIC_FOCUS": "Mangler anaerob belastning",
    "AEROBIC_LOW_SHORTAGE": "Mangler lav aerob belastning",
    "AEROBIC_HIGH_SHORTAGE": "Mangler høy aerob belastning",
    "ANAEROBIC_SHORTAGE": "Mangler anaerob belastning",
    "BALANCED": "Balansert",
    "NO_DATA": "Ikke nok data",
}


def sport_group(activity_type: str | None) -> str:
    t = activity_type or ""
    for group, needles in _SPORT_KEYS:
        if any(n in t for n in needles):
            return group
    return "annet"


def _phrase(raw: str | None, table: dict) -> str | None:
    """Garmin-fraser som 'MAINTAINING_4' → 'Vedlikehold'. Ukjente vises som de er."""
    if not raw:
        return None
    key = re.sub(r"_\d+$", "", raw)
    return table.get(key, key.replace("_", " ").capitalize())


def _week_start(day: str) -> str:
    d = date.fromisoformat(day[:10])
    return (d - timedelta(days=d.weekday())).isoformat()


def _activity(a: dict) -> dict:
    activity_type = (a.get("activityType") or {}).get("typeKey")
    return {
        "activity_id": a.get("activityId"),
        "dato": a.get("startTimeLocal"),
        "navn": a.get("activityName"),
        "type": activity_type,
        "sport": sport_group(activity_type),
        "varighet_min": round((a.get("duration") or 0) / 60, 1),
        "distanse_km": km(a.get("distance")),
        "snitt_puls": rnd(a.get("averageHR")),
        "treningsbelastning": rnd(a.get("activityTrainingLoad")),
        "aerob_te": rnd(a.get("aerobicTrainingEffect"), 1),
        "anaerob_te": rnd(a.get("anaerobicTrainingEffect"), 1),
    }


def _weeks(activities: list[dict], start: date, end: date) -> list[dict]:
    weeks: dict[str, dict] = {}
    monday = start - timedelta(days=start.weekday())
    while monday <= end:
        weeks[monday.isoformat()] = {
            "uke_start": monday.isoformat(),
            "uke_nr": monday.isocalendar().week,
            "okter": 0,
            "minutter": 0.0,
            "distanse_km": 0.0,
            "treningsbelastning": 0,
            "minutter_per_sport": {s: 0.0 for s in SPORTS},
        }
        monday += timedelta(days=7)
    for a in activities:
        week = weeks.get(_week_start(a["dato"]))
        if week is None:
            continue
        week["okter"] += 1
        week["minutter"] += a["varighet_min"]
        week["distanse_km"] += a["distanse_km"] or 0
        week["treningsbelastning"] += a["treningsbelastning"] or 0
        week["minutter_per_sport"][a["sport"]] += a["varighet_min"]
    for week in weeks.values():
        week["minutter"] = round(week["minutter"])
        week["distanse_km"] = round(week["distanse_km"], 1)
        week["minutter_per_sport"] = {s: round(m) for s, m in week["minutter_per_sport"].items()}
    return list(weeks.values())


def _daily(client, activities: list[dict], start: date, end: date) -> list[dict]:
    s, e = start.isoformat(), end.isoformat()
    hrv = {h.get("calendarDate"): h for h in (client.get_hrv_data_range(s, e) or {}).get("hrvSummaries") or []}
    sleep = {d.get("calendarDate"): d.get("values") or {} for d in client.get_sleep_daily(s, e) or []}
    rhr = {d.get("calendarDate"): d.get("value") for d in client.get_rhr_daily(s, e) or []}
    load = defaultdict(int)
    for a in activities:
        load[a["dato"][:10]] += a["treningsbelastning"] or 0

    days = []
    day = start
    while day <= end:
        key = day.isoformat()
        h, sl = hrv.get(key) or {}, sleep.get(key) or {}
        baseline = h.get("baseline") or {}
        sleep_seconds = sl.get("totalSleepTimeInSeconds")
        days.append({
            "dato": key,
            "hrv_ms": h.get("lastNightAvg"),
            "hrv_baseline_lav": baseline.get("balancedLow"),
            "hrv_baseline_hoy": baseline.get("balancedUpper"),
            "hrv_status": h.get("status"),
            "hvilepuls": rnd(rhr.get(key)),
            "sovn_timer": round(sleep_seconds / 3600, 2) if sleep_seconds else None,
            "sovn_score": sl.get("sleepScore"),
            "treningsbelastning": load.get(key, 0),
        })
        day += timedelta(days=1)
    return days


def _status(client, today: str) -> dict:
    raw = client.get_training_status(today) or {}
    latest = (raw.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
    device = next(iter(latest.values()), {}) if latest else {}
    acute = device.get("acuteTrainingLoadDTO") or {}
    balance_map = (raw.get("mostRecentTrainingLoadBalance") or {}).get("metricsTrainingLoadBalanceDTOMap") or {}
    balance = next(iter(balance_map.values()), {}) if balance_map else {}
    vo2 = (raw.get("mostRecentVO2Max") or {}).get("generic") or {}

    readiness_entries = client.get_training_readiness(today) or []
    readiness = max(readiness_entries, key=lambda e: e.get("timestampLocal") or "") if readiness_entries else {}
    recovery_min = readiness.get("recoveryTime")

    def band(name: str) -> dict:
        return {
            "belastning": rnd(balance.get(f"monthlyLoad{name}")),
            "mal_min": balance.get(f"monthlyLoad{name}TargetMin"),
            "mal_maks": balance.get(f"monthlyLoad{name}TargetMax"),
        }

    return {
        "treningsstatus": _phrase(device.get("trainingStatusFeedbackPhrase"), _TRAINING_STATUS),
        "status_siden": device.get("sinceDate"),
        "vo2max": vo2.get("vo2MaxPreciseValue") or vo2.get("vo2MaxValue"),
        "akutt_belastning": acute.get("dailyTrainingLoadAcute"),
        "kronisk_belastning": acute.get("dailyTrainingLoadChronic"),
        "kronisk_optimal_min": rnd(acute.get("minTrainingLoadChronic")),
        "kronisk_optimal_maks": rnd(acute.get("maxTrainingLoadChronic")),
        "belastningsforhold": acute.get("dailyAcuteChronicWorkloadRatio"),
        "belastning_status": acute.get("acwrStatus"),
        "beredskap_score": readiness.get("score"),
        "beredskap_niva": readiness.get("level"),
        "restitusjonstid_timer": round(recovery_min / 60, 1) if recovery_min is not None else None,
        "belastningsbalanse": {
            "vurdering": _phrase(balance.get("trainingBalanceFeedbackPhrase"), _LOAD_BALANCE),
            "aerob_lav": band("AerobicLow"),
            "aerob_hoy": band("AerobicHigh"),
            "anaerob": band("Anaerobic"),
        },
    }


def collect_overview(client, days: int = 42) -> dict:
    days = max(7, min(days, 120))
    end = date.today()
    start = end - timedelta(days=days - 1)
    raw = client.get_activities_by_date(start.isoformat(), end.isoformat()) or []
    activities = sorted((_activity(a) for a in raw), key=lambda a: a["dato"] or "", reverse=True)
    return {
        "generert": datetime.now().isoformat(timespec="minutes"),
        "fra": start.isoformat(),
        "til": end.isoformat(),
        "status": _status(client, end.isoformat()),
        "uker": _weeks(activities, start, end),
        "dager": _daily(client, activities, start, end),
        "okter": activities,
    }


def register(mcp: FastMCP, client) -> None:
    @mcp.tool
    def get_training_overview(days: int = 28) -> dict:
        """Hent en oversikt over de siste `days` dagene (7–120, default 28): dagens
        treningsstatus, akutt/kronisk belastning, VO2max, beredskap og månedlig
        belastningsbalanse; ukessummer (økter, minutter per sport, km, belastning);
        daglige trender (HRV med baseline, hvilepuls, søvn, belastning); og alle
        øktene i perioden. Bruk denne for spørsmål om utvikling over tid."""
        return collect_overview(client, days)

    @mcp.tool
    def create_training_dashboard(days: int = 42, open_in_browser: bool = True) -> dict:
        """Lag et treningsdashboard som HTML-fil (ukesvolum per sport, HRV, hvilepuls,
        søvn, belastningsbalanse og øktliste) for de siste `days` dagene og åpne det i
        nettleseren. Returnerer filstien."""
        from garmin_mcp import dashboard

        path = dashboard.write(collect_overview(client, days))
        if open_in_browser:
            dashboard.open_file(path)
        return {"fil": str(path), "url": path.as_uri()}
