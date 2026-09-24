# garmin-mcp

MCP-server som gir Claude tilgang til Garmin Connect: økter, søvn, HRV, stress,
treningsberedskap, belastning og terskler.

## Oppsett

    uv run python -m garmin_mcp.auth   # engangs innlogging, lagrer tokens i ~/.garminconnect

## Treningsdashboard

`get_training_overview(days)` gir Claude ukessummer, daglige trender (HRV, hvilepuls,
søvn, belastning) og dagens status for en periode. De samme tallene kan vises som et
dashboard i nettleseren:

    uv run python -m garmin_mcp.dashboard                  # siste 42 dager → ~/garmin-dashboard.html
    uv run python -m garmin_mcp.dashboard --days 90 --out ~/Desktop/trening.html --no-open

Fra Claude: be om «lag treningsdashboardet», som kaller `create_training_dashboard`.
