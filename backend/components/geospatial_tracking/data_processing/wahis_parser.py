"""Parser for WAHIS "Event" PDF reports (Immediate Notification / Follow-up Report).

pypdf's text extraction flattens the source PDF's multi-column tables into a
single reading order that does not always match the visual column order (for
example the "NEW" row's numeric cells are emitted before the species-name
label that visually precedes them). The regexes below were written against
four real WAHIS exports (events 3473, 5822, 5868, 3644) and anchor on the
most stable literal tokens (e.g. "- Animal", "TOTAL", "Listed disease") to
stay robust to that column reordering.

KNOWN LIMITATION (documented, not silently worked around): the
FIRST/SECOND/THIRD ADMINISTRATIVE DIVISION line cannot be reliably split
into admin1/admin2/admin3 by this parser, because division names are
themselves multi-word (e.g. "Chiang Mai", "Tha Wang Pha") with no delimiter
between adjacent fields in the flattened text. Splitting on whitespace alone
would silently fabricate an incorrect boundary. Until a layout-aware
extractor (e.g. pdfplumber table extraction) or a gazetteer-assisted
segmenter is implemented (Phase B), admin1/admin2/admin3 are left as None
and the raw line is preserved in extra["admin_line_raw"] so no information
is lost.

DATE SEMANTICS (see schemas.py module docstring for the full A/B/C model):
this source's `report_date` is a single event-level filing date shared by
every outbreak block in the report. For a follow-up report that can be
filed months or years after the outbreaks it describes (Event_3473:
report_date ~3 years after confirmation_date) and can bundle outbreak
blocks spanning years of activity under one filing date (Event_3644: 670
blocks, one report_date, outbreak_start_dates from 2021-03 to 2024-01).
`report_date` is therefore never used as `operational_availability_date`
(left None/UNKNOWN — this source has no true "system knew by" evidence) nor
folded into `outbreak_start_date`/`event_start_date`. The
RETROSPECTIVE_PROXY substitute (`proxy_availability_date`) uses each
outbreak block's own `outbreak_start_date` instead, so blocks from the same
report remain chronologically distinguishable.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..schemas import AvailabilityQuality, GpsQuality, RawOutbreakRecord, SourceSystem

_DATE = re.compile(r"\d{4}/\d{2}/\d{2}")
_PAGE_FOOTER = re.compile(r"^\d{1,3}/\d{1,3}\s*")


def _line_after(lines: list[str], header_line: str) -> str | None:
    """Return the line immediately following an exact-match header line.

    WAHIS report tables are always emitted by pypdf as: (possibly
    multi-line-wrapped) column headers, then exactly one data line. Anchoring
    on an exact header-line match is far more robust than substring/windowed
    search, since header tokens (e.g. "START DATE") are reused verbatim
    inside other sections (e.g. each outbreak block).
    """
    for i, line in enumerate(lines):
        if line.strip() == header_line:
            return lines[i + 1].strip() if i + 1 < len(lines) else None
    return None


def parse_event_header(text: str) -> dict:
    """Extract event-level fields from the text preceding the first outbreak block."""
    header_text = text.split("GENERAL INFORMATION", 1)[-1]
    header_text = header_text.split("EPIDEMIOLOGY", 1)[0]
    lines = [_PAGE_FOOTER.sub("", ln) for ln in header_text.splitlines()]

    title_line = text.splitlines()[0] if text.splitlines() else ""
    country = title_line.split(" - ", 1)[0].strip() if " - " in title_line else None
    # WAHIS event titles are consistently "{country} - {disease} - {report
    # type}" (verified against all 4 real fixtures: Event_3473/5822/5868/3644).
    title_parts = title_line.split(" - ")
    disease = title_parts[1].strip() if len(title_parts) >= 3 and title_parts[1].strip() else None

    event_id_match = re.search(r"Listed disease\s+(\d+)", header_text)
    event_id = event_id_match.group(1) if event_id_match else None

    start_date_line = _line_after(lines, "START DATE")
    event_start_date = None
    if start_date_line:
        m = _DATE.search(start_date_line)
        event_start_date = m.group(0) if m else None

    reason_data_line = _line_after(
        lines, "REASON FOR NOTIFICATION DATE OF LAST OCCURRENCE CONFIRMATION DATE EVENT STATUS"
    )
    confirmation_date = None
    event_status = None
    if reason_data_line:
        dates_on_line = _DATE.findall(reason_data_line)
        if dates_on_line:
            confirmation_date = dates_on_line[-1]
            status_text = reason_data_line[reason_data_line.rfind(dates_on_line[-1]) + len(dates_on_line[-1]) :]
            event_status = status_text.strip() or None

    end_date_line = _line_after(lines, "END DATE SELF-DECLARATION")
    event_end_date = None
    if end_date_line:
        m = _DATE.search(end_date_line)
        event_end_date = m.group(0) if m else None

    report_data_line = _line_after(lines, "REPORT NUMBER REPORT ID REPORT REFERENCE REPORT DATE")
    report_date = None
    report_id = None
    if report_data_line:
        report_id_match = re.search(r"\b([A-Z]{2,4}_\d+)\b", report_data_line)
        report_id = report_id_match.group(1) if report_id_match else None
        dates = _DATE.findall(report_data_line)
        report_date = dates[-1] if dates else None

    return {
        "country": country,
        "disease": disease,
        "event_id": event_id,
        "event_start_date": event_start_date,
        "event_end_date": event_end_date,
        "confirmation_date": confirmation_date,
        "event_status": event_status,
        "report_date": report_date,
        "report_id": report_id,
    }


def split_outbreak_chunks(text: str) -> list[str]:
    starts = [m.start() for m in re.finditer(r"OB_\d+\s*-\s*", text)]
    if not starts:
        return []
    chunks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[start:end]
        # drop trailing page-footer "MAP" section if present on the last chunk
        map_idx = chunk.rfind("\nMAP\n")
        if map_idx != -1:
            chunk = chunk[:map_idx]
        chunks.append(chunk)
    return chunks


def _parse_int_or_none(token: str) -> int | None:
    token = token.strip()
    if token in ("", "-"):
        return None
    try:
        return int(token)
    except ValueError:
        return None


_LOCATION_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 .,'()\-\n]*?)\s+(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)"
    r"\s*(\(Approximate location\))?\s*-\s*Animal",
    re.DOTALL,
)

# Fallback for the rare (Checkpoint 2 audit: 3/670 in Event_3644.pdf) case
# where a mid-row PDF page break reshuffles the LOCATION table's visual
# column order to coordinates-then-locality-then-"- Animal", with the
# "(Approximate location)" flag emitted AFTER "- Animal" instead of before
# it (e.g. "15.02671 , 100.72298 Khok Samrong - Animal\n(Approximate
# location)"). Only used when `_LOCATION_RE` finds no match in the chunk —
# never guessed, only recovered when this exact alternate literal grammar
# is unambiguously present.
_LOCATION_RE_COORDS_FIRST = re.compile(
    r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s+"
    r"([A-Za-z][A-Za-z0-9 .,'()\-\n]*?)\s*-\s*Animal"
    r"\s*(\(Approximate location\))?",
    re.DOTALL,
)


_LOCATION_SECTION_HEADER = "LOCATION Latitude, Longitude OUTBREAKS IN CLUSTER Measuring unit"
_LOCATION_SECTION_END = "AFFECTED POPULATION DESCRIPTION"


def _location_section(chunk: str) -> str:
    """Bound the location regexes to the text between the LOCATION table's
    own header and the next section header, rather than the whole chunk.

    Without this bound, allowing '(' ')' '\\n' in the locality character
    class (needed for multi-line-wrapped, parenthesized real locality
    names — see `_LOCATION_RE`) lets a non-greedy match creep backwards
    across earlier section headers (FIRST/SECOND/THIRD ADMINISTRATIVE
    DIVISION, EPIDEMIOLOGICAL UNIT) whenever the true locality line isn't
    reached on the first try. Scoping the search window first keeps the
    character class widening safe.
    """
    start = chunk.find(_LOCATION_SECTION_HEADER)
    if start == -1:
        return chunk
    start += len(_LOCATION_SECTION_HEADER)
    end = chunk.find(_LOCATION_SECTION_END, start)
    return chunk[start:end] if end != -1 else chunk[start:]


def _extract_location(chunk: str) -> tuple[str | None, float | None, float | None, bool]:
    """Returns (locality, latitude, longitude, approximate_location).

    Tries the normal "locality lat, lon [approx] - Animal" column order
    first; only falls back to the reshuffled "lat, lon locality - Animal
    [approx]" order when the normal order can't be found at all in this
    chunk. Never fabricates a value — returns (None, None, None, False)
    when neither literal pattern is present.
    """
    section = _location_section(chunk)

    m = _LOCATION_RE.search(section)
    if m:
        locality = " ".join(m.group(1).split()) or None
        return locality, float(m.group(2)), float(m.group(3)), m.group(4) is not None

    m = _LOCATION_RE_COORDS_FIRST.search(section)
    if m:
        locality = " ".join(m.group(3).split()) or None
        return locality, float(m.group(1)), float(m.group(2)), m.group(4) is not None

    return None, None, None, False

_TOTAL_ROW_RE = re.compile(
    r"NEW\s+[\d-]+\s+[\d-]+\s+[\d-]+\s+[\d-]+\s+[\d-]+\s+[\d-]+"
    r"([A-Za-z][A-Za-z .()\n]*?)\s*TOTAL\s+([\d-]+)\s+([\d-]+)\s+([\d-]+)\s+([\d-]+)\s+([\d-]+)\s+([\d-]+)"
)

_OUTBREAK_DATES_RE = re.compile(
    r"OUTBREAK REFERENCE START DATE END DATE DETAILED CHARACTERISATION\s*\n"
    r".*?(\d{4}/\d{2}/\d{2})\s+(\d{4}/\d{2}/\d{2})",
    re.DOTALL,
)


def _parse_outbreak_title(chunk: str) -> tuple[str | None, str | None]:
    """Parse the "OB_id - [ref -] LOCALITY" title line.

    The outbreak_reference segment is only present when WAHIS recorded a
    non-empty OUTBREAK REFERENCE for that outbreak; when absent, the title
    is just "OB_id - LOCALITY" (two parts, not three). Splitting on the
    literal " - " token (not a bare hyphen) avoids false splits on
    hyphenated locality names.
    """
    title_line = chunk.splitlines()[0] if chunk.splitlines() else ""
    parts = title_line.split(" - ")
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip()
    if len(parts) == 2:
        return parts[0].strip(), None
    return None, None


def parse_outbreak_chunk(chunk: str, event_context: dict, source_file: str) -> RawOutbreakRecord:
    outbreak_id, outbreak_reference = _parse_outbreak_title(chunk)

    dates_match = _OUTBREAK_DATES_RE.search(chunk)
    outbreak_start_date = dates_match.group(1) if dates_match else None
    outbreak_end_date = dates_match.group(2) if dates_match else None

    locality, latitude, longitude, approximate_location = _extract_location(chunk)
    gps_quality = GpsQuality.UNKNOWN.value
    if latitude is not None:
        gps_quality = GpsQuality.APPROXIMATE.value if approximate_location else GpsQuality.EXACT.value

    species = None
    susceptible = cases = deaths = killed_disposed = vaccinated = None
    slaughtered = None
    total_match = _TOTAL_ROW_RE.search(chunk)
    if total_match:
        species = " ".join(total_match.group(1).split()) or None
        susceptible = _parse_int_or_none(total_match.group(2))
        cases = _parse_int_or_none(total_match.group(3))
        deaths = _parse_int_or_none(total_match.group(4))
        killed_disposed = _parse_int_or_none(total_match.group(5))
        slaughtered = _parse_int_or_none(total_match.group(6))
        vaccinated = _parse_int_or_none(total_match.group(7))

    diagnostic_method = None
    method_idx = chunk.find("METHOD OF DIAGNOSTIC")
    if method_idx != -1:
        window = chunk[method_idx + len("METHOD OF DIAGNOSTIC") :]
        next_header_idx = window.find("CONTROL MEASURES")
        raw_method = window[:next_header_idx] if next_header_idx != -1 else window[:100]
        raw_method = " ".join(raw_method.split()).strip(", ")
        diagnostic_method = raw_method or None
        if diagnostic_method == "-":
            diagnostic_method = None

    admin_line_raw = None
    admin_idx = chunk.find("EPIDEMIOLOGICAL UNIT")
    if admin_idx != -1:
        after = chunk[admin_idx + len("EPIDEMIOLOGICAL UNIT") :]
        loc_header_idx = after.find("LOCATION")
        raw = after[:loc_header_idx] if loc_header_idx != -1 else after[:150]
        raw = " ".join(raw.split())
        admin_line_raw = _PAGE_FOOTER.sub("", raw).strip() or None

    return RawOutbreakRecord(
        source_file=source_file,
        source_system=SourceSystem.WAHIS_PDF.value,
        country=event_context.get("country"),
        disease=event_context.get("disease"),
        event_id=event_context.get("event_id"),
        outbreak_id=outbreak_id,
        outbreak_reference=outbreak_reference,
        event_start_date=event_context.get("event_start_date"),
        event_end_date=event_context.get("event_end_date"),
        outbreak_start_date=outbreak_start_date,
        outbreak_end_date=outbreak_end_date,
        confirmation_date=event_context.get("confirmation_date"),
        report_date=event_context.get("report_date"),
        # True operational availability is unknown for this source: the
        # event's report_date is a single filing date for the WHOLE report
        # (which for a follow-up report can be years after, and cover many
        # outbreak blocks spanning years of activity — see schemas.py
        # module docstring). It must never be used as this outbreak block's
        # operational availability.
        operational_availability_date=None,
        operational_availability_quality=AvailabilityQuality.UNKNOWN.value,
        # RETROSPECTIVE_PROXY-mode-only substitute: this specific outbreak
        # block's own start date, not the shared event-level report_date —
        # keeps distinct outbreak blocks within one (possibly long-running)
        # report distinguishable by their own chronology.
        proxy_availability_date=outbreak_start_date,
        proxy_availability_quality=(
            AvailabilityQuality.EVENT_DATE_PROXY.value
            if outbreak_start_date
            else AvailabilityQuality.UNKNOWN.value
        ),
        admin1=None,
        admin2=None,
        admin3=None,
        locality=locality,
        latitude=latitude,
        longitude=longitude,
        gps_quality=gps_quality,
        approximate_location=approximate_location,
        species=species,
        susceptible=susceptible,
        cases=cases,
        deaths=deaths,
        killed_disposed=killed_disposed,
        vaccinated=vaccinated,
        diagnostic_method=diagnostic_method,
        event_status=event_context.get("event_status"),
        extra={
            "admin_line_raw": admin_line_raw,
            "slaughtered_killed_commercial": slaughtered,
            "report_id": event_context.get("report_id"),
        },
    )


_PAGE_FOOTER_LINE = re.compile(r"\n\d{1,3}/\d{1,3}\n")


def parse_wahis_text(text: str, source_file: str) -> tuple[dict, list[RawOutbreakRecord]]:
    # strip "N/M" page-footer lines (e.g. "2/6") that pypdf emits between
    # pages — left in place they can land mid-field when an outbreak block
    # spans a page break.
    text = _PAGE_FOOTER_LINE.sub("\n", text)
    event_context = parse_event_header(text)
    chunks = split_outbreak_chunks(text)
    records = [parse_outbreak_chunk(c, event_context, source_file) for c in chunks]
    return event_context, records


def extract_pdf_text(path: str | Path) -> str:
    import pypdf

    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() for page in reader.pages)


def parse_wahis_pdf(path: str | Path) -> tuple[dict, list[RawOutbreakRecord]]:
    path = Path(path)
    text = extract_pdf_text(path)
    return parse_wahis_text(text, source_file=path.name)
