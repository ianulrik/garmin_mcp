"""Engangsoppsett: kjøres manuelt i en ekte terminal for å logge inn hos
Garmin og cache token lokalt. Kjøres ALDRI av Claude Desktop/MCP-serveren.

Bruk: uv run python -m garmin_mcp.auth
"""

import sys
from getpass import getpass

from garminconnect import Garmin

TOKEN_STORE = "~/.garminconnect"


def main() -> None:
    email = input("Garmin e-post: ")
    password = getpass("Garmin passord (vises ikke): ")

    client = Garmin(email, password, prompt_mfa=lambda: input("MFA-kode: "))
    client.login(TOKEN_STORE)

    print(f"Innlogget. Token cachet i {TOKEN_STORE}", file=sys.stderr)


if __name__ == "__main__":
    main()
