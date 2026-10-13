"""Tests for the WAHIS PDF text parser.

Fixtures are synthetic text blocks modeled on the real WAHIS report grammar
(observed in local_data/pistes_raw/Event_{3473,5822,5868,3644}.pdf) with
fabricated event IDs, coordinates, and place names — the real files must
never be committed to the repo.
"""

from components.geospatial_tracking.data_processing.wahis_parser import (
    parse_event_header,
    parse_wahis_text,
    split_outbreak_chunks,
)
from components.geospatial_tracking.schemas import AvailabilityQuality, GpsQuality


def _event_header(
    country="Testland",
    event_id="9001",
    start_date="2021/01/10",
    reason_line="First occurrence in the country - 2021/03/01 Stable",
    end_date="2021/04/15",
    self_declaration="NO",
    report_line="Follow-up report 1 FUR_900001 - 2021/05/01",
    zone_or_country="ZONE",
):
    return f"""{country} - Lumpy skin disease virus (Inf. with) - Follow-up report 1
WAHIS
GENERAL INFORMATION
COUNTRY/TERRITORY OR ZONE ANIMAL TYPE DISEASE CATEGORY EVENT ID
{zone_or_country} TERRESTRIAL Listed disease {event_id}
DISEASE CAUSAL AGENT GENOTYPE / SEROTYPE /
SUBTYPE
START DATE
Lumpy skin disease virus (Inf. with) Lumpy skin disease virus - {start_date}
REASON FOR NOTIFICATION DATE OF LAST OCCURRENCE CONFIRMATION DATE EVENT STATUS
{reason_line}
END DATE SELF-DECLARATION
{end_date} {self_declaration}
REPORT INFORMATION
REPORT NUMBER REPORT ID REPORT REFERENCE REPORT DATE
{report_line}
REPORT STATUS NO EVOLUTION REPORT
Validated -
EPIDEMIOLOGY
SOURCE OF EVENT OR ORIGIN OF INFECTION
Unknown or inconclusive
"""


def _outbreak_block(
    outbreak_id="OB_1001",
    reference="TEST/REF/1",
    locality="Testville",
    start_date="2021/01/10",
    end_date="2021/04/15",
    admin1="Province A",
    lat="7.123456",
    lon="81.654321",
    approximate=False,
    new_row="- - - - - -",
    total_row="10 3 1 0 0 0",
    species="cattle \n(domestic)",
    diagnostic_method="Clinical,\nDiagnostic test",
):
    approx_suffix = " \n(Approximate location)" if approximate else ""
    title = f"OB_{outbreak_id.replace('OB_', '')} - {reference} - {locality.upper()}" if reference else f"OB_{outbreak_id.replace('OB_', '')} - {locality.upper()}"
    return f"""{title}
OUTBREAK REFERENCE START DATE END DATE DETAILED CHARACTERISATION
{reference or '-'} {start_date} {end_date} -
FIRST ADMINISTRATIVE DIVISION SECOND ADMINISTRATIVE
DIVISION
THIRD ADMINISTRATIVE
DIVISION
EPIDEMIOLOGICAL UNIT
{admin1} District X - Farm
LOCATION Latitude, Longitude OUTBREAKS IN CLUSTER Measuring unit
{locality} {lat} , {lon}{approx_suffix} - Animal
AFFECTED POPULATION DESCRIPTION
-
Species Wildlife
type
Susceptible Cases Deaths Killed and
Disposed of
Slaughtered/ Killed for
commercial use
Vaccinated
NEW {new_row}{species}
TOTAL {total_row} -
METHOD OF DIAGNOSTIC
{diagnostic_method}
CONTROL MEASURES DIFFERENT FROM EVENT LEVEL
MEASURES NOT IMPLEMENTED
-
ADDITIONAL MEASURES
-
"""


class TestEventHeader:
    def test_basic_fields(self):
        text = _event_header()
        header = parse_event_header(text)
        assert header["country"] == "Testland"
        assert header["event_id"] == "9001"
        assert header["event_start_date"] == "2021/01/10"
        assert header["event_end_date"] == "2021/04/15"
        assert header["report_date"] == "2021/05/01"
        assert header["report_id"] == "FUR_900001"

    def test_first_occurrence_single_date_reason_line(self):
        # "First occurrence" lines carry only ONE date (confirmation date);
        # "date of last occurrence" is "-" (absent).
        text = _event_header(reason_line="First occurrence in the country - 2021/03/01 Stable")
        header = parse_event_header(text)
        assert header["confirmation_date"] == "2021/03/01"
        assert header["event_status"] == "Stable"

    def test_recurrence_two_date_reason_line(self):
        # Recurrence lines carry TWO dates: date of last occurrence, then
        # confirmation date. The LAST date on the line is always the
        # confirmation date, regardless of how many dates precede it.
        text = _event_header(
            reason_line="Recurrence of an eradicated disease 2020/11/01 2021/03/01 Resolved"
        )
        header = parse_event_header(text)
        assert header["confirmation_date"] == "2021/03/01"
        assert header["event_status"] == "Resolved"

    def test_start_date_label_inside_outbreak_block_is_not_confused_with_event_start_date(self):
        # "START DATE" also appears (as part of a longer combined header) in
        # every outbreak block's "OUTBREAK REFERENCE START DATE END DATE..."
        # line. parse_event_header must only look before EPIDEMIOLOGY.
        text = _event_header(start_date="2021/01/10") + _outbreak_block(start_date="1999/01/01")
        header = parse_event_header(text)
        assert header["event_start_date"] == "2021/01/10"


class TestOutbreakSplitting:
    def test_splits_multiple_outbreaks(self):
        text = _event_header() + _outbreak_block(outbreak_id="OB_1001") + _outbreak_block(
            outbreak_id="OB_1002"
        )
        chunks = split_outbreak_chunks(text)
        assert len(chunks) == 2
        assert chunks[0].startswith("OB_1001")
        assert chunks[1].startswith("OB_1002")

    def test_no_outbreaks_returns_empty_list(self):
        assert split_outbreak_chunks(_event_header()) == []


class TestOutbreakFieldExtraction:
    def test_extracts_reference_and_locality(self):
        text = _event_header() + _outbreak_block(
            outbreak_id="OB_1001", reference="TEST/REF/1", locality="Testville"
        )
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert len(records) == 1
        r = records[0]
        assert r.outbreak_id == "OB_1001"
        assert r.outbreak_reference == "TEST/REF/1"
        assert r.locality == "Testville"

    def test_outbreak_reference_optional_two_part_title(self):
        # When WAHIS has no outbreak reference, the title line is just
        # "OB_id - LOCALITY" (two parts), not three.
        text = _event_header() + _outbreak_block(outbreak_id="OB_2002", reference=None, locality="Noreftown")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert len(records) == 1
        assert records[0].outbreak_id == "OB_2002"
        assert records[0].outbreak_reference is None
        assert records[0].locality == "Noreftown"

    def test_locality_with_digits_is_parsed(self):
        # Real data includes localities like "Village 7" — the location
        # regex must allow digits in the locality name, not just letters.
        text = _event_header() + _outbreak_block(locality="Village 7")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert records[0].locality == "Village 7"
        assert records[0].latitude is not None

    def test_approximate_location_flag(self):
        text = _event_header() + _outbreak_block(approximate=True)
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.approximate_location is True
        assert r.gps_quality == GpsQuality.APPROXIMATE.value

    def test_exact_location_flag(self):
        text = _event_header() + _outbreak_block(approximate=False)
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.approximate_location is False
        assert r.gps_quality == GpsQuality.EXACT.value

    def test_two_distinct_outbreaks_sharing_approximate_coordinates_are_not_merged(self):
        # Distinct outbreak IDs with identical (approximate) coordinates
        # must remain separate records — merging is a later, explicit
        # deduplication decision, never an implicit parsing side effect.
        text = (
            _event_header()
            + _outbreak_block(outbreak_id="OB_3001", locality="Hamlet A", lat="9.0", lon="80.0", approximate=True)
            + _outbreak_block(outbreak_id="OB_3002", locality="Hamlet B", lat="9.0", lon="80.0", approximate=True)
        )
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert len(records) == 2
        assert records[0].outbreak_id != records[1].outbreak_id
        assert (records[0].latitude, records[0].longitude) == (records[1].latitude, records[1].longitude)

    def test_quantitative_totals_with_dash_new_row(self):
        # Follow-up reports commonly show an all-dash NEW row (no new cases
        # since the last report) followed by real cumulative TOTAL values.
        text = _event_header() + _outbreak_block(new_row="- - - - - -", total_row="89 36 0 0 0 -")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.susceptible == 89
        assert r.cases == 36
        assert r.deaths == 0
        assert r.vaccinated is None  # trailing "-" must not become 0

    def test_quantitative_totals_with_populated_new_row(self):
        # Immediate notifications show real (non-dash) NEW values, which
        # previously broke the "-species" anchor regex.
        text = _event_header() + _outbreak_block(new_row="3 1 0 0 0 2", total_row="3 1 0 0 0 2")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.susceptible == 3
        assert r.cases == 1
        assert r.vaccinated == 2
        assert r.species == "cattle (domestic)"

    def test_diagnostic_method_extracted(self):
        text = _event_header() + _outbreak_block(diagnostic_method="Clinical,\nDiagnostic test")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert records[0].diagnostic_method == "Clinical, Diagnostic test"

    def test_page_footer_line_does_not_corrupt_admin_or_location_fields(self):
        # pypdf inserts standalone "N/M" page-number lines between pages;
        # they must be stripped before field extraction, not leak into data.
        block = _outbreak_block(admin1="Province A", locality="Testville")
        # simulate a page break landing between EPIDEMIOLOGICAL UNIT and its data line
        block = block.replace(
            "EPIDEMIOLOGICAL UNIT\nProvince A",
            "EPIDEMIOLOGICAL UNIT\n7/12\nProvince A",
        )
        text = _event_header() + block
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert "7/12" not in (records[0].extra["admin_line_raw"] or "")

    def test_event_context_propagated_to_every_outbreak(self):
        text = _event_header(country="Testland", event_id="9001") + _outbreak_block(
            outbreak_id="OB_1001"
        ) + _outbreak_block(outbreak_id="OB_1002")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert all(r.country == "Testland" for r in records)
        assert all(r.event_id == "9001" for r in records)

    def test_operational_availability_is_unknown_not_inferred_from_report_date(self):
        # This source has no true "system knew by" evidence. The event's
        # report_date must never be promoted into
        # operational_availability_date for an outbreak block.
        text = _event_header(report_line="Follow-up report 1 FUR_900001 - 2021/05/01") + _outbreak_block()
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.operational_availability_date is None
        assert r.operational_availability_quality == AvailabilityQuality.UNKNOWN.value

    def test_delayed_followup_report_does_not_replace_outbreak_chronology(self):
        # Event_3473-type scenario: a 2020/2021 outbreak whose follow-up
        # report is filed ~3 years later. The report_date must not leak
        # into outbreak_start_date/outbreak_end_date, and the proxy
        # availability date must reflect the outbreak's own chronology, not
        # the report's filing date.
        text = _event_header(
            start_date="2020/09/01",
            report_line="Follow-up report 1 FUR_347301 - 2023/07/28",
        ) + _outbreak_block(start_date="2020/09/15", end_date="2020/10/20")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.outbreak_start_date == "2020/09/15"
        assert r.outbreak_end_date == "2020/10/20"
        assert r.report_date == "2023/07/28"
        assert r.proxy_availability_date == "2020/09/15"
        assert r.proxy_availability_quality == AvailabilityQuality.EVENT_DATE_PROXY.value
        # the 2020 outbreak must not have become a "2023 outbreak"
        assert r.proxy_availability_date != r.report_date

    def test_long_running_followup_outbreaks_keep_distinct_proxy_dates(self):
        # Event_3644-type scenario: one long-running follow-up report
        # (single event-level report_date) bundles outbreak blocks spanning
        # years. Each block must keep its own proxy availability date
        # rather than collapsing to the shared report_date.
        text = (
            _event_header(report_line="Follow-up report 49 FUR_364449 - 2024/01/09")
            + _outbreak_block(outbreak_id="OB_5001", start_date="2021/03/10", end_date="2021/03/20")
            + _outbreak_block(outbreak_id="OB_5002", start_date="2023/11/01", end_date="2023/11/10")
        )
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        assert len(records) == 2
        proxy_dates = {r.outbreak_id: r.proxy_availability_date for r in records}
        assert proxy_dates == {"OB_5001": "2021/03/10", "OB_5002": "2023/11/01"}
        # neither block silently inherits the shared, far-later report_date
        assert all(r.report_date == "2024/01/09" for r in records)
        assert all(r.proxy_availability_date != r.report_date for r in records)

    def test_proxy_availability_unknown_when_outbreak_start_date_missing(self):
        # If the outbreak dates line can't be parsed, proxy availability
        # must stay UNKNOWN rather than falling back to report_date.
        block = _outbreak_block().replace(
            "OUTBREAK REFERENCE START DATE END DATE DETAILED CHARACTERISATION\n"
            "TEST/REF/1 2021/01/10 2021/04/15 -\n",
            "",
        )
        text = _event_header() + block
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.outbreak_start_date is None
        assert r.proxy_availability_date is None
        assert r.proxy_availability_quality == AvailabilityQuality.UNKNOWN.value

    def test_reshuffled_coords_before_locality_recovers_coordinates(self):
        # Checkpoint 2 parser-gap fix: Event_3644.pdf's OB_100298 has a
        # mid-row PDF page break reshuffling LOCATION to
        # "lat, lon locality - Animal\n(Approximate location)" instead of
        # the normal "locality lat, lon (Approximate location) - Animal".
        text = _event_header() + _outbreak_block().replace(
            "Testville 7.123456 , 81.654321 - Animal",
            "7.123456 , 81.654321 Testville - Animal\n(Approximate location)",
        )
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.latitude == 7.123456
        assert r.longitude == 81.654321
        assert r.locality == "Testville"
        assert r.approximate_location is True
        assert r.gps_quality == GpsQuality.APPROXIMATE.value

    def test_locality_with_parentheses_and_linewrap_is_parsed(self):
        # Event_3644.pdf's OB_92005/OB_91966: normal column order, but the
        # locality name itself contains parentheses and wraps across a
        # line ("Si Racha (Protected Area Regional \nOffice 2 Sriracha)"),
        # which the original character class (no parens/newline) rejected.
        text = _event_header() + _outbreak_block().replace(
            "Testville 7.123456 , 81.654321 - Animal",
            "Ban Test (Wildlife Sanctuary \nRegional Office) 7.123456 , 81.654321 - Animal",
        )
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.latitude == 7.123456
        assert r.longitude == 81.654321
        assert r.locality == "Ban Test (Wildlife Sanctuary Regional Office)"
        assert r.approximate_location is False

    def test_reshuffled_or_parenthesized_location_never_captures_earlier_headers(self):
        # Regression guard: widening the locality character class to allow
        # '(' ')' '\n' must not let a non-greedy match creep backwards
        # across FIRST/SECOND/THIRD ADMINISTRATIVE DIVISION or
        # EPIDEMIOLOGICAL UNIT when the LOCATION line itself is malformed
        # beyond recovery — locality must never contain header text.
        text = _event_header() + _outbreak_block().replace(
            "Testville 7.123456 , 81.654321 - Animal", "totally unparseable line with no numbers"
        )
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.latitude is None
        assert r.longitude is None
        assert r.locality is None

    def test_admin_hierarchy_not_fabricated(self):
        # Known limitation: the admin1/2/3 line cannot be safely split on
        # whitespace (division names are themselves multi-word). The parser
        # must leave admin1/2/3 as None rather than guess, while preserving
        # the raw line for later, more careful segmentation.
        text = _event_header() + _outbreak_block(admin1="Chiang Mai")
        _, records = parse_wahis_text(text, source_file="fixture.pdf")
        r = records[0]
        assert r.admin1 is None
        assert r.admin2 is None
        assert r.admin3 is None
        assert "Chiang Mai" in (r.extra["admin_line_raw"] or "")
