"""Presentation helpers: presets, chart gaps, research notes and readable labels."""
import json

import altair as alt

from src.platform_service import API, SOURCE

PRESETS = {
    "Growth and inflation": ["NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG"],
    "Employment": ["SL.UEM.TOTL.ZS", "SL.TLF.CACT.ZS"],
    "Trade and investment": ["NE.TRD.GNFS.ZS", "BX.KLT.DINV.WD.GD.ZS"],
}


def indicator_names(result):
    return dict(zip(result.metadata.get("Indicator code", []), result.metadata.get("Name", [])))


def coverage_table(result):
    table = result.quality.copy()
    names = indicator_names(result)
    countries = result.data.set_index("Country code")["Country"].to_dict()
    table.insert(0, "Country", table["Country code"].map(countries))
    table.insert(1, "Indicator", table["Indicator code"].map(lambda code: names.get(code, code)))
    return table


def research_notes(result, settings):
    countries, codes, start, end = settings
    dates = sorted(set(result.provenance.loc[result.provenance["Retrieved (UTC)"] != "", "Retrieved (UTC)"].str[:10]))
    citation = ("World Bank. World Development Indicators (source 2). "
                f"Countries: {', '.join(countries)}. Indicators: {', '.join(codes)}. "
                f"Observation period: {start}–{end}. "
                f"Retrieved: {', '.join(dates) if dates else 'no successful retrieval'}. "
                "https://data.worldbank.org/. Consult the original indicator providers when citing.")
    if result.errors:
        citation += " Some series could not be retrieved; see the source report."
    if result.provenance["Status"].str.contains("stale cache").any():
        citation += " Some observations use expired cached responses; retrieval dates are preserved."
    payload = {"schema_version": 1, "api": API, "source_id": SOURCE,
               "countries": countries, "indicator_codes": codes, "start_year": start, "end_year": end,
               "suggested_citation": citation, "sources": result.provenance.to_dict("records"),
               "missing_value_policy": "No filling or interpolation; missing observations remain blank."}
    return citation, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def research_chart(data, code, label, highlight=None):
    frame = data[["Country", "Country code", "Year", code]].sort_values(["Country code", "Year"]).copy()
    # Each run of observed years has a separate line; no joining across blanks.
    frame["Segment"] = frame.groupby("Country code")[code].transform(lambda values: values.isna().cumsum())
    field = code.replace(".", "\\.")
    opacity = (alt.condition(alt.datum["Country code"] == highlight, alt.value(1), alt.value(0.2))
               if highlight else alt.value(1))
    return alt.Chart(frame).mark_line(point=True).encode(
        x=alt.X("Year:Q", axis=alt.Axis(format="d", title="Year"), scale=alt.Scale(zero=False)),
        y=alt.Y(field=field, type="quantitative", title=label, scale=alt.Scale(zero=False)),
        color=alt.Color("Country:N", title="Country"), detail="Segment:N", opacity=opacity,
        tooltip=["Country:N", alt.Tooltip("Year:Q", format="d"),
                 alt.Tooltip(field=field, type="quantitative", title=label, format=",.3f")],
    ).properties(height=340).interactive()
