"""Garmin-klient: pålogging fra token-cache, timeout og feiloversettelse.

Skilt ut fra server.py fordi dette er "hvordan vi snakker trygt med Garmin",
uavhengig av hvilke verktøy som finnes.
"""

import os
import sys
import threading

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

TOKEN_STORE = os.path.expanduser("~/.garminconnect")

_CALL_TIMEOUT = 30.0  # sekunder

_ERROR_HINTS = {
    GarminConnectAuthenticationError: "Sesjonen har utløpt. Kjør 'uv run python -m garmin_mcp.auth' på nytt.",
    GarminConnectTooManyRequestsError: "Garmin rate-limiter deg. Vent noen minutter før du prøver igjen.",
    GarminConnectConnectionError: "Fikk ikke kontakt med Garmin Connect. Sjekk nettverket eller prøv igjen senere.",
}


class GarminProxy:
    """Wrapper rundt Garmin-klienten: legger timeout og tydeligere feilmeldinger
    på hvert API-kall.

    Uten en timeout kan ett trått Garmin-kall blokkere hele serveren helt til
    MCP-klientens egen timeout (typisk flere minutter) gir opp — da ser HELE
    serveren død ut for Claude Desktop, ikke bare at ett verktøykall feilet.
    """

    def __init__(self, client: Garmin, timeout: float = _CALL_TIMEOUT) -> None:
        self._client = client
        self._timeout = timeout

    def __getattr__(self, name: str):
        attr = getattr(self._client, name)
        if not callable(attr):
            return attr

        def wrapped(*args, **kwargs):
            outcome: dict = {}

            def run() -> None:
                try:
                    outcome["value"] = attr(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001 - videresendes til kalleren
                    outcome["error"] = exc

            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            worker.join(self._timeout)

            if worker.is_alive():
                raise TimeoutError(
                    f"Garmin-kallet '{name}' svarte ikke innen {self._timeout:g}s. Prøv igjen om litt."
                )
            if "error" in outcome:
                error = outcome["error"]
                for exc_type, hint in _ERROR_HINTS.items():
                    if isinstance(error, exc_type):
                        raise type(error)(f"{error} — {hint}") from None
                raise error
            return outcome["value"]

        return wrapped


def get_client() -> GarminProxy:
    # Ingen email/password/prompt_mfa her, med vilje: denne prosessen kjøres
    # av Claude Desktop uten en ekte terminal. Skulle garminconnect prøve å
    # falle tilbake på interaktiv innlogging, ville den prøve å lese stdin —
    # men stdin er MCP-protokollkanalen, ikke et tastatur. Det er
    # stdin-motstykket til stdout-fella i server.py. Uten credentials her *kan*
    # ikke biblioteket falle tilbake til interaktiv login: finner den ikke
    # gyldige cachede tokens i TOKEN_STORE, feiler login() rent i stedet.
    client = Garmin()
    try:
        client.login(TOKEN_STORE)
        # login() kan lykkes selv om den cachede tokenen faktisk er død (et
        # "innlogget som ingen"-scenario) — bekreft med et ekte, billig
        # API-kall at sesjonen faktisk virker, ikke bare at login() ikke kastet.
        if not client.get_full_name():
            raise GarminConnectAuthenticationError("Sesjonen er ikke autentisert")
    except Exception as e:
        print(f"Fant ingen gyldig Garmin-sesjon i {TOKEN_STORE}: {e}", file=sys.stderr)
        print("Kjør engangsoppsettet: uv run python -m garmin_mcp.auth", file=sys.stderr)
        raise SystemExit(1) from e
    return GarminProxy(client)
