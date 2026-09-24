"""Treningsdashboard: gjør collect_overview() om til én selvstendig HTML-fil.

Dataene bakes inn i HTML-malen som JSON, så fila kan åpnes rett i nettleseren
uten server. Kjør fra terminalen:

    uv run python -m garmin_mcp.dashboard            # siste 42 dager, åpner nettleser
    uv run python -m garmin_mcp.dashboard --days 90 --out ~/Desktop/trening.html

eller be Claude kalle MCP-verktøyet create_training_dashboard.
"""

import argparse
import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

DEFAULT_OUT = Path("~/garmin-dashboard.html").expanduser()
_PLACEHOLDER = "/*__GARMIN_DATA__*/null"


def render(overview: dict) -> str:
    template = files("garmin_mcp").joinpath("dashboard.html").read_text(encoding="utf-8")
    # "</" escapes så et aktivitetsnavn aldri kan avslutte <script>-taggen.
    data = json.dumps(overview, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(_PLACEHOLDER, data)


def write(overview: dict, out: Path = DEFAULT_OUT) -> Path:
    out = Path(out).expanduser()
    out.write_text(render(overview), encoding="utf-8")
    return out


def open_file(path: Path) -> None:
    # Output fra `open` må ikke havne på stdout: i MCP-serveren er stdout
    # protokollkanalen (se server.py).
    opener = {"darwin": ["open"], "win32": ["cmd", "/c", "start", ""]}.get(sys.platform, ["xdg-open"])
    subprocess.run([*opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lag treningsdashboard fra Garmin Connect.")
    parser.add_argument("--days", type=int, default=42, help="antall dager tilbake (7–120)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="hvor HTML-fila skal lagres")
    parser.add_argument("--no-open", action="store_true", help="ikke åpne i nettleseren")
    args = parser.parse_args()

    from garmin_mcp.client import get_client
    from garmin_mcp.tools.overview import collect_overview

    path = write(collect_overview(get_client(), args.days), args.out)
    print(f"Dashboard lagret: {path}")
    if not args.no_open:
        open_file(path)


if __name__ == "__main__":
    main()
