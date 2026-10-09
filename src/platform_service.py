"""World Bank WDI access, validated caches, research tables and exports.

No network or filesystem work occurs at import time. Legacy CSVs are never
silently promoted to verified caches: they lack API identity and provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Callable

import pandas as pd
import requests

API = "https://api.worldbank.org/v2"
SOURCE = "2"  # World Development Indicators; disambiguates repeated codes.
ROOT = Path(__file__).resolve().parents[1]
CACHE_VERSION = 1


class ResearchError(Exception):
    """A recoverable error suitable for display to a researcher."""


def current_year() -> int:
    return datetime.now(timezone.utc).year


def validate_request(country: str, indicator: str, start: int, end: int) -> None:
    if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{3}", country):
        raise ResearchError("Choose a country using its three-letter World Bank code.")
    if not isinstance(indicator, str) or not re.fullmatch(r"[A-Za-z0-9_.]{1,100}", indicator):
        raise ResearchError("Choose a valid World Bank indicator code.")
    if any(type(year) is not int for year in (start, end)):
        raise ResearchError("Years must be whole numbers.")
    if not 1960 <= start <= end <= current_year():
        raise ResearchError(f"Choose years from 1960 to {current_year()}, with start before end.")


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


class JsonCache:
    """Identity- and checksum-validated JSON, with atomic writes and a TTL.

    A checksum detects accidental corruption, not malicious modifications.
    Cache writes are best effort; a read-only hosting filesystem is supported.
    """

    def __init__(self, folder: Path, ttl: int = 86400, clock: Callable | None = None):
        self.folder = Path(folder)
        self.ttl = ttl
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())

    def path(self, identity: dict) -> Path:
        return self.folder / f"{_digest(identity)}.json"

    def read(self, identity: dict, validator: Callable, allow_stale: bool = False):
        try:
            envelope = json.loads(self.path(identity).read_text(encoding="utf-8"))
            age = self.clock() - envelope["saved_at"]
            if (envelope["version"] != CACHE_VERSION or envelope["identity"] != identity
                    or not math.isfinite(age) or age < 0
                    or (not allow_stale and age > self.ttl)
                    or envelope["checksum"] != _digest(envelope["payload"])):
                return None
            validator(envelope["payload"])
            return envelope
        except (OSError, ValueError, TypeError, KeyError, ResearchError):
            return None

    def write(self, identity: dict, payload: object) -> bool:
        envelope = {"version": CACHE_VERSION, "identity": identity,
                    "saved_at": self.clock(), "payload": payload, "checksum": _digest(payload)}
        temporary = None
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.folder,
                                             suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(envelope, handle, allow_nan=False)
            os.replace(temporary, self.path(identity))
            return True
        except (OSError, ValueError):
            return False
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


@dataclass
class Catalog:
    items: list[dict]
    status: str
    retrieved_at: str


@dataclass
class Series:
    country: str
    indicator: str
    values: pd.DataFrame
    metadata: dict
    status: str
    retrieved_at: str
    api_updated: str
    url: str


def _timestamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


class WorldBankClient:
    def __init__(self, cache_dir: Path | None = None, session=None, ttl: int = 86400):
        self.cache = JsonCache(cache_dir or ROOT / "data" / "platform_cache", ttl)
        self.session = session or requests.Session()

    def _pages(self, path: str, params: dict | None = None) -> tuple[list, dict]:
        rows, header = [], {}
        page, expected_pages, expected_total = 1, None, None
        while True:
            try:
                response = self.session.get(f"{API}/{path}", params={
                    **(params or {}), "format": "json", "per_page": 1000, "page": page
                }, timeout=(5, 25))
                response.raise_for_status()
                body = response.json()
            except requests.RequestException as exc:
                raise ResearchError("World Bank could not be reached. Check your connection and try again.") from exc
            except ValueError as exc:
                raise ResearchError("World Bank returned an unreadable response. Try again later.") from exc
            try:
                if not isinstance(body, list) or len(body) != 2 or not isinstance(body[0], dict):
                    raise ValueError
                header = body[0]
                pages, total = int(header["pages"]), int(header["total"])
                # The API can report zero pages for a valid empty result.
                if total == 0 and pages == 0:
                    pages = 1
                if not 1 <= pages <= 200 or total < 0 or int(header["page"]) != page:
                    raise ValueError
                if expected_pages is None:
                    expected_pages, expected_total = pages, total
                if pages != expected_pages or total != expected_total:
                    raise ValueError
                batch = body[1]
                if batch is None and total == 0:
                    batch = []
                if not isinstance(batch, list) or not all(isinstance(row, dict) for row in batch):
                    raise ValueError
                rows.extend(batch)
                if page == pages:
                    if len(rows) != total:
                        raise ValueError
                    return rows, header
                page += 1
            except (ValueError, KeyError, TypeError) as exc:
                raise ResearchError("World Bank returned incomplete or invalid data. Try again later.") from exc

    @staticmethod
    def _validate_catalog(payload: dict, kind: str) -> None:
        if not isinstance(payload, dict):
            raise ResearchError("Invalid catalogue payload.")
        rows = payload["items"]
        if not isinstance(rows, list) or not rows:
            raise ResearchError("The World Bank catalogue is empty.")
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ResearchError("Invalid catalogue entry.")
            code = row["id"]
            pattern = r"[A-Z]{3}" if kind == "countries" else r"[A-Za-z0-9_.]{1,100}"
            if (not isinstance(code, str) or not re.fullmatch(pattern, code)
                    or code in seen or not isinstance(row["name"], str) or not row["name"]):
                raise ResearchError("Invalid catalogue identity.")
            if kind == "indicators" and str(row["source"]["id"]) != SOURCE:
                raise ResearchError("Invalid indicator source.")
            seen.add(code)

    def catalog(self, kind: str, refresh: bool = False) -> Catalog:
        if kind not in {"countries", "indicators"}:
            raise ResearchError("Unknown catalogue.")
        identity = {"api": API, "kind": kind, "source": SOURCE}
        validator = lambda payload: self._validate_catalog(payload, kind)
        cached = self.cache.read(identity, validator)
        if cached and not refresh:
            return Catalog(cached["payload"]["items"], "validated cache", _timestamp(cached["saved_at"]))
        try:
            if kind == "countries":
                rows, _ = self._pages("country")
                # Exclude World Bank regional/income aggregates from country selection.
                rows = [row for row in rows if row.get("region", {}).get("id") not in {None, "NA"}]
            else:
                rows, _ = self._pages("indicator", {"source": SOURCE})
            payload = {"items": rows}
            validator(payload)
        except (KeyError, TypeError, ResearchError) as exc:
            stale = self.cache.read(identity, validator, allow_stale=True)
            if stale:
                return Catalog(stale["payload"]["items"], "stale cache — API unavailable",
                               _timestamp(stale["saved_at"]))
            raise ResearchError(f"Cannot load {kind}. Connect to the internet and retry.") from exc
        saved = self.cache.write(identity, payload)
        return Catalog(rows, "World Bank API" if saved else "World Bank API — cache unavailable",
                       _timestamp(self.cache.clock()))

    @staticmethod
    def _validate_series(payload: dict, country: str, indicator: str, start: int, end: int):
        if not isinstance(payload, dict) or not isinstance(payload.get("metadata"), dict):
            raise ResearchError("Invalid observation metadata.")
        metadata = payload["metadata"]
        if (metadata["id"] != indicator or str(metadata["source"]["id"]) != SOURCE
                or not isinstance(metadata["name"], str) or not metadata["name"]):
            raise ResearchError("Indicator metadata does not match the request.")
        if not isinstance(payload["api_updated"], str) or not isinstance(payload["rows"], list):
            raise ResearchError("Invalid observation payload.")
        seen = set()
        for row in payload["rows"]:
            if not isinstance(row, dict):
                raise ResearchError("Invalid observation.")
            year, value = row["year"], row["value"]
            if (row["country"] != country or row["indicator"] != indicator
                    or type(year) is not int or not start <= year <= end or year in seen):
                raise ResearchError("Observation identity, year range or uniqueness is invalid.")
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ResearchError("World Bank returned a non-numeric observation.")
            seen.add(year)

    def series(self, country: str, indicator: str, start: int, end: int,
               metadata: dict, refresh: bool = False) -> Series:
        validate_request(country, indicator, start, end)
        identity = {"api": API, "source": SOURCE, "country": country,
                    "indicator": indicator, "start": start, "end": end}
        validator = lambda payload: self._validate_series(payload, country, indicator, start, end)
        cached = self.cache.read(identity, validator)
        status = "validated cache"
        if refresh or cached is None:
            try:
                rows, header = self._pages(f"country/{country}/indicator/{indicator}",
                                           {"source": SOURCE, "date": f"{start}:{end}"})
                normalized = []
                for row in rows:
                    raw_year = row["date"]
                    if not isinstance(raw_year, str) or not re.fullmatch(r"\d{4}", raw_year):
                        raise ResearchError("World Bank returned an invalid year.")
                    normalized.append({"country": row["countryiso3code"],
                                       "indicator": row["indicator"]["id"],
                                       "year": int(raw_year), "value": row["value"]})
                payload = {"rows": normalized, "metadata": metadata,
                           "api_updated": str(header.get("lastupdated", "Not supplied"))}
                validator(payload)
                saved = self.cache.write(identity, payload)
                cached = {"payload": payload, "saved_at": self.cache.clock()}
                status = "World Bank API" if saved else "World Bank API — cache unavailable"
            except (KeyError, ValueError, TypeError, ResearchError) as exc:
                cached = self.cache.read(identity, validator, allow_stale=True)
                if cached is None:
                    if isinstance(exc, ResearchError):
                        raise
                    raise ResearchError("World Bank observations were malformed. Try again later.") from exc
                status = "stale cache — API unavailable"
        payload = cached["payload"]
        # Reindex only adds missing markers, never economic observations.
        lookup = {row["year"]: row["value"] for row in payload["rows"]}
        frame = pd.DataFrame({"Year": range(start, end + 1),
                              indicator: [lookup.get(y) for y in range(start, end + 1)]})
        frame[indicator] = pd.to_numeric(frame[indicator], errors="raise")
        url = f"{API}/country/{country}/indicator/{indicator}?format=json&source={SOURCE}&date={start}:{end}"
        return Series(country, indicator, frame, payload["metadata"], status,
                      _timestamp(cached["saved_at"]), payload["api_updated"], url)


@dataclass
class ResearchResult:
    data: pd.DataFrame
    quality: pd.DataFrame
    metadata: pd.DataFrame
    provenance: pd.DataFrame
    errors: list[str]


def missing_report(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for country, frame in data.groupby("Country code", sort=False):
        for code in frame.columns.difference(["Country", "Country code", "Year"], sort=False):
            missing = int(frame[code].isna().sum())
            rows.append({"Country code": country, "Indicator code": code,
                         "Expected years": len(frame), "Available": len(frame) - missing,
                         "Missing": missing, "Missing (%)": round(100 * missing / len(frame), 2),
                         "Coverage (%)": round(100 * (len(frame) - missing) / len(frame), 2),
                         "First available year": (int(frame.loc[frame[code].notna(), "Year"].min())
                                                  if missing < len(frame) else None),
                         "Last available year": (int(frame.loc[frame[code].notna(), "Year"].max())
                                                 if missing < len(frame) else None)})
    return pd.DataFrame(rows)


def build_research(client: WorldBankClient, countries: list[dict], indicators: list[dict],
                   start: int, end: int, refresh: bool = False,
                   on_progress: Callable | None = None) -> ResearchResult:
    if not countries or not indicators:
        raise ResearchError("Select at least one country and one indicator.")
    if len(countries) > 5 or len(indicators) > 10:
        raise ResearchError("For this MVP, select up to 5 countries and 10 indicators.")
    if len({x["id"] for x in countries}) != len(countries) or len({x["id"] for x in indicators}) != len(indicators):
        raise ResearchError("Country and indicator selections must be unique.")
    for country in countries:
        for indicator in indicators:
            validate_request(country["id"], indicator["id"], start, end)
    frames, provenance, errors, metadata_rows = [], [], [], {}
    for country in countries:
        frame = pd.DataFrame({"Country": country["name"], "Country code": country["id"],
                              "Year": range(start, end + 1)})
        for indicator in indicators:
            code = indicator["id"]
            try:
                series = client.series(country["id"], code, start, end, indicator, refresh)
                frame = frame.merge(series.values, on="Year", how="left", validate="one_to_one")
                meta = series.metadata
                metadata_rows[code] = {"Indicator code": code, "Name": meta["name"],
                    "Unit": meta.get("unit", ""), "Definition": meta.get("sourceNote", ""),
                    "Original source": meta.get("sourceOrganization", ""),
                    "Dataset": meta["source"].get("value", "World Development Indicators"),
                    "Source ID": SOURCE, "Metadata status": series.status}
                provenance.append({"Country code": country["id"], "Indicator code": code,
                    "Status": series.status, "Retrieved (UTC)": series.retrieved_at,
                    "API last updated": series.api_updated, "API URL": series.url})
            except ResearchError as exc:
                frame[code] = float("nan")
                errors.append(f"{country['name']} / {indicator['name']}: {exc}")
                provenance.append({"Country code": country["id"], "Indicator code": code,
                    "Status": "retrieval failed — observations unavailable",
                    "Retrieved (UTC)": "", "API last updated": "", "API URL": ""})
            if on_progress is not None:
                on_progress(len(provenance), len(countries) * len(indicators),
                            country["name"], indicator["name"], provenance[-1]["Status"])
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    quality = missing_report(data)
    statuses = {(r["Country code"], r["Indicator code"]): r["Status"] for r in provenance}
    quality["Retrieval status"] = [statuses[(r["Country code"], r["Indicator code"])]
                                   for r in quality.to_dict("records")]
    return ResearchResult(data, quality, pd.DataFrame(metadata_rows.values()),
                          pd.DataFrame(provenance), errors)


def retry_failed_series(client: WorldBankClient, result: ResearchResult, countries: list[dict],
                        indicators: list[dict], start: int, end: int,
                        on_progress: Callable | None = None) -> ResearchResult:
    """Retry failed pairs only, keeping successful observations and their provenance.

    The previous result is copied; it remains available if a retry fails.
    """
    country_map = {row["id"]: row for row in countries}
    indicator_map = {row["id"]: row for row in indicators}
    expected = {(c, i) for c in country_map for i in indicator_map}
    pairs = list(zip(result.provenance["Country code"], result.provenance["Indicator code"]))
    if set(pairs) != expected or len(pairs) != len(expected):
        raise ResearchError("Retry settings must match the original dataset.")
    expected_years = list(range(start, end + 1))
    for country in country_map:
        if result.data.loc[result.data["Country code"] == country, "Year"].tolist() != expected_years:
            raise ResearchError("Retry period must match the original dataset.")
        for code in indicator_map:
            validate_request(country, code, start, end)
    data = result.data.copy(deep=True)
    provenance = result.provenance.copy(deep=True)
    metadata = {row["Indicator code"]: row for row in result.metadata.to_dict("records")}
    errors = []
    failed = provenance["Status"].str.startswith("retrieval failed")
    indexes = provenance.index[failed].tolist()
    for completed, index in enumerate(indexes, 1):
        country, code = provenance.loc[index, ["Country code", "Indicator code"]]
        try:
            series = client.series(country, code, start, end, indicator_map[code], refresh=True)
            mask = data["Country code"] == country
            data.loc[mask, code] = series.values[code].to_numpy()
            provenance.loc[index, ["Status", "Retrieved (UTC)", "API last updated", "API URL"]] = [
                series.status, series.retrieved_at, series.api_updated, series.url]
            meta = series.metadata
            metadata[code] = {"Indicator code": code, "Name": meta["name"], "Unit": meta.get("unit", ""),
                "Definition": meta.get("sourceNote", ""), "Original source": meta.get("sourceOrganization", ""),
                "Dataset": meta["source"].get("value", "World Development Indicators"),
                "Source ID": SOURCE, "Metadata status": series.status}
        except ResearchError as exc:
            errors.append(f"{country_map[country]['name']} / {indicator_map[code]['name']}: {exc}")
        if on_progress is not None:
            on_progress(completed, len(indexes), country_map[country]["name"],
                        indicator_map[code]["name"], provenance.loc[index, "Status"])
    quality = missing_report(data).merge(
        provenance[["Country code", "Indicator code", "Status"]].rename(columns={"Status": "Retrieval status"}),
        on=["Country code", "Indicator code"], validate="one_to_one")
    return ResearchResult(data, quality, pd.DataFrame(metadata.values()), provenance, errors)


def csv_bytes(data: pd.DataFrame) -> bytes:
    return data.to_csv(index=False, na_rep="").encode("utf-8-sig")


def excel_bytes(result: ResearchResult) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in [("Data", result.data), ("Missing values", result.quality),
                            ("Indicator metadata", result.metadata), ("Sources", result.provenance)]:
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(55, max(14, len(str(column[0].value)) + 3))
                for cell in column:
                    # Treat upstream metadata as text rather than Excel formulas.
                    if cell.data_type == "f":
                        cell.data_type = "s"
    return buffer.getvalue()
