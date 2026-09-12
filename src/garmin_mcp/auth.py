"""Engangsoppsett: kjøres manuelt i en ekte terminal for å logge inn hos
Garmin og cache token lokalt. Kjøres ALDRI av Claude Desktop/MCP-serveren.

Bruk: uv run python -m garmin_mcp.auth
"""

import os
import sys
from getpass import getpass

from garminconnect import Garmin

TOKEN_STORE = "~/.garminconnect"


def _secure_token_dir(path: str) -> None:
    """Sett eier-only rettigheter på token-mappen og filene i den.

    En OAuth-token er et ~6 måneders bærer-credential til hele Garmin-kontoen —
    den skal ikke være lesbar for andre brukere på maskinen.
    """
    expanded = os.path.expanduser(path)
    if not os.path.isdir(expanded):
        return
    os.chmod(expanded, 0o700)
    for entry in os.scandir(expanded):
        if entry.is_file():
            os.chmod(entry.path, 0o600)


def main() -> None:
    email = input("Garmin e-post: ")
    password = getpass("Garmin passord (vises ikke): ")

    client = Garmin(email, password, prompt_mfa=lambda: input("MFA-kode: "))
    client.login(TOKEN_STORE)
    _secure_token_dir(TOKEN_STORE)

    print(f"Innlogget. Token cachet i {TOKEN_STORE}", file=sys.stderr)


if __name__ == "__main__":
    main()
