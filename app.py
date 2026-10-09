"""Streamlit entry point. Run: python -m streamlit run app.py."""
import pandas as pd
import streamlit as st

from config import COUNTRY, END_YEAR, INDICATORS, START_YEAR
from src.platform_service import (
    ROOT, ResearchError, WorldBankClient, build_research, csv_bytes, current_year,
    excel_bytes, missing_report, retry_failed_series,
)
from src.research_experience import (
    PRESETS, coverage_table, indicator_names, research_chart, research_notes,
)


def make_client():
    return WorldBankClient()


def load_catalogs(refresh=False):
    client = make_client()
    return client.catalog("countries", refresh), client.catalog("indicators", refresh)


def store_result(result, settings, selections):
    st.session_state.result = result
    st.session_state.result_settings = settings
    st.session_state.result_selections = selections
    st.session_state.pop("excel_export", None)
    st.session_state.csv_export = csv_bytes(result.data)
    st.session_state.citation, st.session_state.research_notes = research_notes(result, settings)
    st.session_state.pop("chart_indicator", None)
    st.session_state.pop("chart_highlight", None)
    st.session_state.result_view = "Data table"


def retrieve_with_progress(operation):
    with st.status("Preparing your research dataset…", expanded=True) as status:
        progress = st.progress(0.0)
        message = st.empty()
        def update(completed, total, country, indicator, source):
            progress.progress(completed / total)
            message.write(f"{completed} of {total} series checked · {country} · {indicator}")
        result = operation(update)
        status.update(label=("Dataset ready — some series need attention" if result.errors else "Dataset ready"),
                      state="complete", expanded=False)
    return result


def apply_preset(indicator_map):
    preset = st.session_state.preset
    if preset != "Choose individually":
        st.session_state.chosen_indicators = [code for code in PRESETS[preset] if code in indicator_map]
        st.session_state.indicator_search = ""


def apply_period():
    shortcut = st.session_state.period_shortcut
    end = min(END_YEAR, current_year())
    if shortcut == "Last 10 completed years":
        end = current_year() - 1
        st.session_state.start_year, st.session_state.end_year = end - 9, end
    elif shortcut == "Since 2000":
        st.session_state.start_year, st.session_state.end_year = 2000, end
    elif shortcut == "Original research period":
        st.session_state.start_year, st.session_state.end_year = START_YEAR, end


@st.fragment
def render_builder(country_map, indicator_map):
    if "result" in st.session_state:
        st.markdown("[Jump to your dataset ↓](#your-research-dataset)")
    st.subheader("1. Choose your research question")
    st.selectbox("Start with a research preset", ["Growth and inflation", "Employment", "Trade and investment", "Choose individually"],
                 key="preset", on_change=apply_preset, args=(indicator_map,))
    preset = st.session_state.preset
    if preset in PRESETS:
        unavailable = [code for code in PRESETS[preset] if code not in indicator_map]
        if unavailable:
            st.caption("Some preset indicators are unavailable in this catalogue. Choose alternatives below.")
    query = st.text_input("Search indicators", key="indicator_search",
                         placeholder="Try inflation, GDP, unemployment, or a World Bank code")
    previous = [code for code in st.session_state.chosen_indicators if code in indicator_map]
    matches = [code for code, row in indicator_map.items()
               if query.casefold().strip() in f"{code} {row['name']} {row.get('sourceNote', '')}".casefold()]
    options = list(dict.fromkeys([*previous, *matches]))
    if not matches:
        st.info("No indicators match this search. Try a shorter term or an indicator code; your selected indicators are kept.")
    else:
        st.caption(f"{len(matches):,} matching indicators. You can customize any preset.")
    codes = st.multiselect("Indicators (up to 10)", options, key="chosen_indicators",
                           format_func=lambda code: f"{indicator_map[code]['name']} · {code}", max_selections=10)
    with st.expander("Understand your selected indicators"):
        for code in codes:
            st.markdown(f"**{indicator_map[code]['name']}**")
            st.write(indicator_map[code].get("sourceNote") or "See the World Bank definition after retrieval.")
    st.subheader("2. Choose countries and years")
    countries = st.multiselect("Countries (up to 5)", list(country_map), key="chosen_countries",
        format_func=lambda code: f"{country_map[code]['name']} ({code})", max_selections=5)
    st.selectbox("Research period", ["Custom years", "Last 10 completed years", "Since 2000", "Original research period"],
                 key="period_shortcut", on_change=apply_period)
    left, right = st.columns(2)
    start = left.number_input("Start year", min_value=1960, max_value=current_year(), step=1, key="start_year")
    end = right.number_input("End year", min_value=1960, max_value=current_year(), step=1, key="end_year")
    settings = (countries, codes, int(start), int(end))
    country_label = "country" if len(countries) == 1 else "countries"
    indicator_label = "indicator" if len(codes) == 1 else "indicators"
    st.caption(f"Selection: {len(countries)} {country_label} · {len(codes)} {indicator_label} · {start}–{end}")
    if start > end:
        st.warning("Start year must be on or before end year. Adjust the years before building.")
    if "result" in st.session_state and settings != st.session_state.result_settings:
        st.info("Selections changed. Your previous dataset is kept below. Build again to apply these choices.")
    with st.expander("Data freshness options"):
        refresh = st.checkbox("Refresh observations from World Bank", key="refresh_observations",
            help="Reuse validated downloads by default. Refresh requests current observations; valid caches remain a fallback if the API fails.")
    if st.button("Build research dataset", type="primary", width="stretch"):
        try:
            selected = ([country_map[x] for x in countries], [indicator_map[x] for x in codes])
            result = retrieve_with_progress(lambda update: build_research(
                make_client(), *selected, int(start), int(end), refresh, on_progress=update))
            store_result(result, settings, selected)
            st.rerun()
        except ResearchError as exc:
            st.error(str(exc))


@st.fragment
def render_result():
    result = st.session_state.result
    countries, codes, start, end = st.session_state.result_settings
    names = indicator_names(result)
    # Keep readable names for failed requests too, without claiming observations.
    for row in st.session_state.result_selections[1]:
        names.setdefault(row["id"], row["name"])
    country_names = result.data.set_index("Country code")["Country"].to_dict()
    st.divider()
    st.subheader("Your research dataset")
    st.caption(f"{' · '.join(country_names[x] for x in countries)} | {start}–{end} | {len(codes)} indicator{'s' if len(codes) != 1 else ''}")
    failed = result.provenance["Status"].str.startswith("retrieval failed").sum()
    if failed:
        st.warning(f"{failed} series could not be retrieved. Successful observations are available; failed series are marked in the coverage report.")
        with st.expander("View retrieval problems"):
            for error in result.errors:
                st.write(error)
        if st.button("Retry failed series", help="Retry only failed requests in this dataset, keeping successful results."):
            try:
                selected = st.session_state.result_selections
                recovered = retrieve_with_progress(lambda update: retry_failed_series(
                    make_client(), result, *selected, start, end, on_progress=update))
                store_result(recovered, st.session_state.result_settings, selected)
                st.rerun()
            except ResearchError as exc:
                st.error(str(exc))
    if result.provenance["Status"].str.contains("stale cache").any():
        st.warning("Some observations use an expired, validated cache because the API was unavailable. Original retrieval dates are shown in Sources.")
    metrics = st.columns(3)
    metrics[0].metric("Countries", len(countries))
    available, expected = int(result.quality["Available"].sum()), int(result.quality["Expected years"].sum())
    metrics[1].metric("Available observations", f"{available:,} / {expected:,}")
    metrics[2].metric("Data coverage", f"{100 * available / expected:.1f}%")
    st.caption("Coverage is the share of selected annual observations available, including failed requests as unavailable. Blank values remain blank; they are never filled or interpolated.")
    view = st.segmented_control("Explore results", ["Data table", "Charts", "Coverage", "Indicator guide", "Sources"],
                                key="result_view") or "Data table"
    filename = f"economic_data_{'_'.join(countries)}_{start}_{end}"
    if view == "Data table":
        show_codes = st.toggle("Show original indicator codes", value=False)
        column_config = {code: st.column_config.NumberColumn(code if show_codes else names.get(code, code),
                                                            help=f"World Bank code: {code}") for code in codes}
        st.dataframe(result.data, hide_index=True, width="stretch", column_config=column_config)
        left, right = st.columns(2)
        left.download_button("Download CSV", st.session_state.csv_export, f"{filename}.csv", "text/csv", width="stretch", on_click="ignore")
        if "excel_export" not in st.session_state:
            try:
                st.session_state.excel_export = excel_bytes(result)
            except (ImportError, ValueError, OSError):
                st.warning("Excel export is unavailable. You can still download CSV.")
        if "excel_export" in st.session_state:
            right.download_button("Download Excel + research notes", st.session_state.excel_export, f"{filename}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch", on_click="ignore")
        st.caption("Exports preserve original indicator codes and full precision. Excel includes definitions, coverage and source details.")
    elif view == "Charts":
        code = st.selectbox("Indicator to chart", codes, format_func=lambda x: names.get(x, x), key="chart_indicator")
        highlight = st.selectbox("Highlight a country", ["All countries", *countries],
                                 format_func=lambda x: country_names.get(x, x), key="chart_highlight")
        if result.data[code].notna().any():
            st.altair_chart(research_chart(result.data, code, names.get(code, code),
                                          None if highlight == "All countries" else highlight), width="stretch")
            st.caption("Hover for exact values; drag or scroll inside the chart to explore. Open the chart toolbar to download PNG. Missing years remain gaps. Each indicator uses its own scale.")
        else:
            st.info("No observations are available for this indicator. Check Coverage for missing data or retrieval failures, or try another period.")
    elif view == "Coverage":
        coverage = coverage_table(result)
        st.dataframe(coverage, hide_index=True, width="stretch", column_config={
            "Coverage (%)": st.column_config.ProgressColumn("Coverage (%)", min_value=0, max_value=100, format="%.1f%%"),
            "First available year": st.column_config.NumberColumn(format="%d"),
            "Last available year": st.column_config.NumberColumn(format="%d"),
        })
        st.info("First and last available years do not imply complete coverage between them. Missing observations can reflect reporting delays or limited coverage; retrieval failures are separately labelled.")
    elif view == "Indicator guide":
        for row in st.session_state.result_selections[1]:
            saved = result.metadata[result.metadata["Indicator code"] == row["id"]] if not result.metadata.empty else pd.DataFrame()
            meta = saved.iloc[0].to_dict() if not saved.empty else None
            with st.expander(f"{names[row['id']]} · {row['id']}"):
                st.write(meta["Definition"] if meta else row.get("sourceNote", "No definition supplied."))
                st.write("Unit:", (meta["Unit"] if meta else row.get("unit")) or "See the indicator name and definition.")
                st.write("Original provider:", (meta["Original source"] if meta else row.get("sourceOrganization")) or "Not supplied")
                if not meta:
                    st.caption("Definition from the catalogue. Observations could not be retrieved.")
                st.link_button("Open World Bank indicator page", f"https://data.worldbank.org/indicator/{row['id']}")
    else:
        st.dataframe(result.provenance, hide_index=True, width="stretch",
            column_config={"API URL": st.column_config.LinkColumn("API URL")})
        st.caption("World Development Indicators, source 2. Default cache life: 24 hours. World Bank can revise historical values; preserve your download and retrieval dates.")
    with st.expander("Save your research settings and citation"):
        st.write("Suggested citation — adapt to your institution's style and acknowledge the original providers:")
        st.code(st.session_state.citation, language=None, wrap_lines=True)
        st.download_button("Download citation", st.session_state.citation.encode("utf-8"), f"{filename}_citation.txt", "text/plain", on_click="ignore")
        st.download_button("Download research settings", st.session_state.research_notes, f"{filename}_settings.json", "application/json", on_click="ignore")
        st.caption("Settings record the exact countries, codes, years, retrieval statuses and source URLs. Use them to repeat your selection; revised API values may differ.")


def render_legacy():
    with st.expander("View the existing Nigeria dataset (offline)"):
        st.caption("Original NGA archive, 1990–2025. Unverified API provenance; kept separate from validated downloads.")
        if st.button("Open original archive"):
            try:
                data = pd.read_csv(ROOT / "data/processed/NGA/1990_2025/NGA_economic_data.csv")
                if "Year" not in data.columns or data["Year"].duplicated().any():
                    raise ValueError("Invalid archive years")
                st.session_state.legacy_data = data
            except (OSError, ValueError, pd.errors.ParserError):
                st.info("The original archive is unavailable in this installation.")
        if "legacy_data" in st.session_state:
            st.dataframe(st.session_state.legacy_data, hide_index=True, width="stretch")
            st.download_button("Download original archive CSV", csv_bytes(st.session_state.legacy_data), "NGA_original_archive.csv", "text/csv", on_click="ignore")


def main():
    st.set_page_config(page_title="Economic Research Platform", page_icon="🌍", layout="wide")
    st.caption("ECONOMIC RESEARCH LAB · WORLD BANK OPEN DATA")
    st.title("Economic data. Ready for research.")
    st.write("Choose a research topic, compare countries, and download data you can explain and cite.")
    with st.sidebar:
        st.header("Your research workspace")
        st.markdown("1. Choose indicators or a preset.\n2. Pick countries and years.\n3. Build and check coverage.\n4. Download data and citation.")
        st.info("Start with growth and inflation. Check definitions and missing values before drawing conclusions.")
        with st.expander("Catalogue and connection"):
            refresh_catalogs = st.button("Refresh catalogues", help="Request current country and indicator catalogues.")
    load = st.button("Load World Bank catalogues", type="primary") if "catalogs" not in st.session_state else False
    if load or refresh_catalogs:
        try:
            with st.spinner("Loading countries and indicator definitions…"):
                st.session_state.catalogs = load_catalogs(refresh_catalogs)
        except ResearchError as exc:
            st.error(str(exc))
            st.info("Retry loading the catalogues when your connection returns. The original archive is available below.")
    if "catalogs" in st.session_state:
        countries, indicators = st.session_state.catalogs
        st.caption(f"Countries: {countries.status} · Indicators: {indicators.status}")
        if "stale cache" in countries.status or "stale cache" in indicators.status:
            st.warning("Catalogue choices use an expired, validated cache because the API is unavailable.")
        country_map = {row["id"]: row for row in sorted(countries.items, key=lambda row: row["name"])}
        indicator_map = {row["id"]: row for row in sorted(indicators.items, key=lambda row: row["name"])}
        defaults = {"chosen_countries": [COUNTRY] if COUNTRY in country_map else [],
                    "chosen_indicators": [x for x in INDICATORS.values() if x in indicator_map][:2],
                    "start_year": START_YEAR, "end_year": min(END_YEAR, current_year()),
                    "preset": "Growth and inflation", "period_shortcut": "Custom years", "indicator_search": ""}
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
        # Catalogue refreshes may retire codes; keep valid selections only.
        st.session_state.chosen_indicators = [x for x in st.session_state.chosen_indicators if x in indicator_map]
        st.session_state.chosen_countries = [x for x in st.session_state.chosen_countries if x in country_map]
        render_builder(country_map, indicator_map)
    else:
        st.info("Load countries and indicators to start. Your first load needs internet; subsequent requests reuse validated downloads.")
    if "result" in st.session_state:
        # Upgrade an existing MVP browser session without discarding its data.
        if "result_selections" not in st.session_state:
            result = st.session_state.result
            original_countries, original_codes, start, end = st.session_state.result_settings
            country_names = result.data.set_index("Country code")["Country"].to_dict()
            saved_metadata = {row["Indicator code"]: row for row in result.metadata.to_dict("records")}
            catalog_rows = ({row["id"]: row for row in st.session_state.catalogs[1].items}
                            if "catalogs" in st.session_state else {})
            selected_indicators = []
            for code in original_codes:
                meta = saved_metadata.get(code, {})
                selected_indicators.append(catalog_rows.get(code, {
                    "id": code, "name": meta.get("Name", code), "source": {"id": "2"},
                    "sourceNote": meta.get("Definition", ""), "unit": meta.get("Unit", ""),
                    "sourceOrganization": meta.get("Original source", ""),
                }))
            result.quality = missing_report(result.data).merge(
                result.provenance[["Country code", "Indicator code", "Status"]].rename(columns={"Status": "Retrieval status"}),
                on=["Country code", "Indicator code"], validate="one_to_one")
            store_result(result, st.session_state.result_settings,
                         ([{"id": code, "name": country_names[code]} for code in original_countries], selected_indicators))
        render_result()
    render_legacy()
    st.divider()
    st.caption("Annual World Development Indicators · No observations filled or invented · Review definitions, coverage and sources before analysis.")


if __name__ == "__main__":
    main()
