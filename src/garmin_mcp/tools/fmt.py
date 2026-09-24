"""Felles formatering av Garmin-verdier (m/s, sekunder, meter) til lesbare enheter."""


def rnd(value, digits: int = 0):
    if value is None:
        return None
    return round(value, digits) if digits else round(value)


def minutes(seconds) -> float | None:
    return round(seconds / 60, 1) if seconds else None


def km(meters) -> float | None:
    return round(meters / 1000, 2) if meters else None


def kmh(speed_mps) -> float | None:
    return round(speed_mps * 3.6, 1) if speed_mps else None


def pace(speed_mps, per_meters: int = 1000) -> str | None:
    """Fart i m/s → tempo som 'm:ss' per `per_meters` (1000 = per km, 100 = per 100 m)."""
    if not speed_mps:
        return None
    total_seconds = round(per_meters / speed_mps)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"
