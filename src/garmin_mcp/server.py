import sys

from fastmcp import FastMCP

from garmin_mcp import client as garmin_client
from garmin_mcp.tools import activities, demo, health, training

# All logging/debug-utskrift MÅ gå til stderr, aldri stdout.
# stdio-transporten bruker stdout som binær meldingskanal mellom Claude
# Desktop og denne prosessen. Ett vagrant print() på stdout korrumperer
# protokollen og gir kryptiske feil i Claude Desktop. Bruk print(..., file=sys.stderr)
# eller `logging` konfigurert mot stderr.
print("garmin-mcp server starter", file=sys.stderr)

mcp = FastMCP("garmin-mcp")
client = garmin_client.get_client()

demo.register(mcp, client)
activities.register(mcp, client)
health.register(mcp, client)
training.register(mcp, client)


if __name__ == "__main__":
    mcp.run()
