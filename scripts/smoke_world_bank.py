"""Opt-in live smoke check. Reuses caches; never alters legacy datasets."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.platform_service import ResearchError, WorldBankClient, build_research


def main():
    client = WorldBankClient()
    try:
        countries = client.catalog("countries")
        indicators = client.catalog("indicators")
        country = next(row for row in countries.items if row["id"] == "NGA")
        indicator = next(row for row in indicators.items if row["id"] == "NY.GDP.MKTP.KD.ZG")
        result = build_research(client, [country], [indicator], 2020, 2022)
        if result.errors:
            raise ResearchError("; ".join(result.errors))
        print(f"Countries: {len(countries.items)} ({countries.status})")
        print(f"Indicators: {len(indicators.items)} ({indicators.status})")
        print(result.data.to_string(index=False))
        print(result.provenance[["Status", "API last updated"]].to_string(index=False))
    except (ResearchError, StopIteration) as exc:
        print(f"Live check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
