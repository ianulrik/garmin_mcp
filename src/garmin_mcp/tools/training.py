from datetime import date

from fastmcp import FastMCP

from garmin_mcp.tools.fmt import pace, rnd


def _zone_floors(zone_set: dict, count: int) -> dict:
    """Nedre grense for hver sone. Soner med gulv 0 over sone 1 er ikke i bruk."""
    floors = {}
    for n in range(1, count + 1):
        floor = zone_set.get(f"zone{n}Floor")
        if floor or n == 1:
            floors[f"sone_{n}"] = rnd(floor)
    return floors


def _hr_zones(zone_sets: list[dict]) -> dict:
    """Pulssoner per sport. Sporter med samme soner som DEFAULT slås sammen."""
    zone_key = ("zone1Floor", "zone2Floor", "zone3Floor", "zone4Floor", "zone5Floor", "maxHeartRateUsed")
    default = next((z for z in zone_sets if z.get("sport") == "DEFAULT"), None)
    result = {}
    for z in zone_sets:
        is_copy_of_default = (
            default is not None
            and z is not default
            and all(z.get(k) == default.get(k) for k in zone_key)
        )
        if is_copy_of_default:
            continue
        result[z.get("sport", "").lower()] = {
            "metode": z.get("trainingMethod"),
            **_zone_floors(z, 5),
        }
    return result


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

    @mcp.tool
    def get_training_thresholds() -> dict:
        """Hent terskler og treningssoner: makspuls, hvilepuls, laktatterskel (puls og
        tempo) for løping, FTP og wattsoner for sykkel og løping, og pulssoner per sport.
        Sonene er oppgitt som nedre grense for hver sone."""
        user = (client.get_user_profile() or {}).get("userData") or {}
        hr_zone_sets = client.get_heart_rate_zones() or []
        power_zone_sets = client.get_power_zones() or []

        default_hr = next((z for z in hr_zone_sets if z.get("sport") == "DEFAULT"), {})
        # Garmin lagrer terskelfarten i enheten 10 m/s.
        lt_speed = user.get("lactateThresholdSpeed")
        lt_speed_mps = lt_speed * 10 if lt_speed else None

        return {
            "makspuls": default_hr.get("maxHeartRateUsed"),
            "hvilepuls": default_hr.get("restingHeartRateUsed"),
            "vo2max_lop": user.get("vo2MaxRunning"),
            "vo2max_sykkel": user.get("vo2MaxCycling"),
            "lop_terskel": {
                "terskelpuls": user.get("lactateThresholdHeartRate"),
                "terskeltempo_min_per_km": pace(lt_speed_mps),
                "auto_detektert": user.get("thresholdHeartRateAutoDetected"),
            },
            "pulssoner": _hr_zones(hr_zone_sets),
            "watt": {
                z.get("sport", "").lower(): {
                    "ftp": rnd(z.get("functionalThresholdPower")),
                    "soner": _zone_floors(z, 7),
                }
                for z in power_zone_sets
                if z.get("sport") in ("CYCLING", "RUNNING")
            },
            "ftp_auto_detektert": user.get("ftpAutoDetected"),
        }
