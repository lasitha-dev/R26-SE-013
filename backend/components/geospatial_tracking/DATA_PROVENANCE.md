# PISTES Data Provenance — Checkpoint 2 / 2.5

How the canonical outbreak dataset is built, reproducibly, from the raw
PISTES sources, and exactly what evidence justifies every merge decision.
This document is the methodology reference; `DATA_AUDIT.md` §10 onward
carries each checkpoint's actual counts and findings. §6 below covers
Checkpoint 2.5's conservative-view policy; §1-5 are unchanged from
Checkpoint 2.

Raw files never leave the local filesystem (`local_data/pistes_raw/`,
gitignored). The datasets this pipeline produces
(`local_data/processed/canonical_outbreaks*.csv`,
`local_data/manifests/*.csv`) are equally derived from raw data and are
**not committed** — only the generation code (this component's
`data_processing/` modules), this document, and `DATA_AUDIT.md`'s summary
statistics are. Anyone with access to the raw files can regenerate every
output byte-for-byte via:

```
cd backend
python -m components.geospatial_tracking.data_processing.build_canonical \
    ../local_data/pistes_raw ../local_data/processed ../local_data/manifests
```

## 1. Pipeline stages

1. **Source manifest** (`manifest.py`) — hashes every raw file, identifies
   byte-identical duplicates, and picks a deterministic single "included"
   copy (lexicographically-first filename) per hash group. The two
   `Latest Reported Events (3/4).csv` files hash identically; `(3)` is
   included, `(4)` is excluded and documented as a duplicate.
2. **Parse** — Checkpoint 1's `csv_parser.py` / `wahis_parser.py`, unchanged
   in field semantics (see `schemas.py` DATE SEMANTICS docstring), only
   included (non-duplicate) files.
3. **Normalize** (`normalize.py`) — reshapes `RawOutbreakRecord` into
   `NormalizedOutbreakRecord`, adding only derived, non-fabricated columns:
   - `source_record_id`: deterministic `{source_system}:{source_file}:{index:06d}`.
   - `proxy_availability_source_field`: the literal field name
     `proxy_availability_date` was copied from (`"outbreak_start_date"` for
     WAHIS, `"observation_date"` for CSV), verified by value equality —
     never just trusted from the quality label.
   - `spatial_independence`: `True` only if a record's rounded (lat, lon)
     is unique across the *entire* corpus; `False` if shared by >=2
     records (e.g. WAHIS's documented case of 3 distinct outbreak IDs on
     one approximate village-level coordinate); `None` if coordinates are
     missing. This never decides duplication by itself — see §2.
   - `species_normalized`: lowercase, filler-word-stripped token used only
     for dedup matching (`species.py`), never written back over `species`.
4. **Deduplicate** (`dedup.py`) — see §2.
5. **Quality** (`quality.py`) — see §3.
6. **Canonical assembly** (`build_canonical.py`) — one row per HIGH/MEDIUM
   duplicate group (the chosen canonical member's own fields, plus
   `duplicate_group_id` / `member_record_ids` / `dedup_confidence`), or one
   row per unmatched/LOW-confidence record.

## 2. Deduplication rules (deterministic, explainable)

### Hard gates (apply to every candidate pair, before any spatial evidence)

- **Country** must match, case-insensitive. Different countries never
  match, full stop.
- **Date** — each side's *best available* date
  (`outbreak_start_date` > `onset_date` > `event_start_date` >
  `confirmation_date`, in that priority order — deliberately never
  `report_date` or a proxy field; see `schemas.py` DATE SEMANTICS) must be
  present on both sides and within `DATE_TOLERANCE_DAYS = 3` of each
  other. Missing a usable date on either side means no candidate at all —
  coordinates alone are never sufficient evidence.

3 days is a small, documented, human-explainable buffer for cross-source
reporting/rounding lag between two independently-operated systems. It is
fixed here and is never tuned against any downstream model result.

### Level 1 — trusted identifier

Only within the same `source_system` and different `source_file`
(WAHIS `OB_` ids and FAO EMPRES-i `Event ID`s are different namespaces and
are **never** treated as comparable across sources — Checkpoint 1's audit
already established this). Automatic HIGH match. Does not fire anywhere in
the current corpus (no source_system has the same identifier duplicated
across two distinct files), but the mechanism exists and is tested.

### Level 2/3 — spatiotemporal evidence, once the hard gates pass

- `distance_km` (haversine) between coordinates, if both sides have them.
  `COORD_TOLERANCE_KM_TIGHT = 2.0`, `COORD_TOLERANCE_KM_LOOSE = 5.0`.
- `locality_match` — normalized-string equality, or Levenshtein distance
  <= 2 on names >= 4 characters (tolerates source typos like WAHIS
  "Vavuniya" vs. CSV "Vavuniy" without accepting arbitrary fuzzy matches).
- `species_match` — via `species_normalized` equality; absence on either
  side is never treated as agreement.

**Approximate-coordinate protection (checked first, takes priority over
everything below):** if either record's `gps_quality` is `APPROXIMATE` or
`COARSE`, and the only spatial evidence is coordinate proximity (not a
*strict*, non-fuzzy locality-name match), the pair is capped at LOW —
never HIGH or MEDIUM — regardless of species agreement. This is what
keeps WAHIS's documented case (3 distinct outbreak IDs sharing one
approximate village coordinate) from auto-merging even when species and
country also happen to agree. The strict (non-fuzzy) locality check is
used here specifically because the general fuzzy locality matcher can
itself be fooled by two genuinely different short place names that happen
to be within edit-distance 2 of each other (e.g. "Village A" / "Village
B") — exactly the scenario this protection exists to guard against.

**Tiers:**
- **HIGH** — tight distance (<=2km) AND locality match AND species match.
- **MEDIUM** — species match, plus at least loose distance (<=5km) or
  locality match (and not caught by the approximate-coordinate
  protection above).
- **LOW** — spatial evidence exists (distance or locality) but species
  doesn't match/is missing, OR the approximate-coordinate protection
  applied.

### Grouping and merge policy

Matched pairs are grouped via union-find into duplicate groups. A group's
confidence is its **weakest** pairwise edge (a chain is only as
trustworthy as its weakest link).

- **HIGH and MEDIUM groups are auto-merged** into one canonical record.
- **LOW groups are never auto-merged** — every member stays as its own
  canonical row, and the group is reported (with `review_required = True`)
  for manual review. "Never merge solely because coordinates are equal" is
  enforced structurally by this policy, not by convention.
- MEDIUM groups also carry `review_required = True` (merged provisionally,
  flagged for human confirmation); HIGH groups do not.

### Canonical record selection

Within a merged group, the canonical record is chosen deterministically:
most non-null fields first, then `WAHIS_PDF` over `FAO_EMPRESI_CSV` (WAHIS
carries species/case-count fields the CSV source never has), then
lexicographically-smallest `source_record_id` as a final tie-break. This
never depends on input ordering.

## 3. Data quality dimensions

Six categorical (`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`) components per record,
each from an explicit, stated rule — never fitted or tuned
(`quality.py`):

| Component | Rule |
|---|---|
| `gps_quality` | source `gps_quality` mapped: EXACT->HIGH, APPROXIMATE->MEDIUM, COARSE/UNKNOWN->LOW; missing coordinates -> UNKNOWN |
| `date_quality` | HIGH if `outbreak_start_date`/`onset_date` present; MEDIUM if only `event_start_date`/`confirmation_date`; LOW if only `report_date`; else UNKNOWN |
| `diagnostic_quality` | HIGH if both `diagnostic_method` and `diagnostic_result`; MEDIUM if one; else UNKNOWN |
| `identifier_quality` | HIGH if both `event_id` and `outbreak_id`; MEDIUM if one; else UNKNOWN |
| `completeness_quality` | fraction of 18 core epidemiological fields populated: >=0.75 HIGH, >=0.5 MEDIUM, >=0.25 LOW, else UNKNOWN |
| `availability_quality` | HIGH only if `operational_availability_quality == ACTUAL`; MEDIUM if a documented proxy exists; LOW if only `REPORT_PROXY`; else UNKNOWN |

An optional composite `dqs` (0-1) is a plain **equal-weighted** average
(1/6 each) of the six components, declared and fixed in `quality.py`. Per
the Checkpoint 2 rule, it is never adjusted using future model performance
or validation results, and the six component values are always reported
alongside it, never discarded.

**Naming note:** `gps_quality` appears in two places with two different
meanings — the raw/canonical dataset's `gps_quality` column is the source
precision label (`EXACT`/`APPROXIMATE`/`COARSE`/`UNKNOWN`, from
`schemas.GpsQuality`); the *quality report's* `gps_quality` column is the
derived quality-dimension category (`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`, from
this table). They are in separate output files
(`canonical_outbreaks.csv` vs. `data_quality_report.csv`) and are never
mixed in one file.

## 4. Availability semantics carried through unchanged

Checkpoint 1's operational-vs-proxy availability split (`schemas.py`) is
preserved through normalization and dedup without modification:
`operational_availability_date`/`_quality` stay `None`/`UNKNOWN` for every
record in this corpus (neither raw source has true "system knew by"
evidence), and `proxy_availability_date`/`_quality` carry the
RETROSPECTIVE_PROXY-mode substitute, now additionally paired with
`proxy_availability_source_field` for full auditability back to the exact
source column. When two records merge, the canonical row keeps the
*chosen member's own* availability fields — merging never blends or
re-derives an availability date from other group members.

## 5. Known parser-gap fix this checkpoint

Event_3644.pdf's 3 outbreak blocks with previously-missing coordinates
(flagged as a limitation in Checkpoint 1) are now resolved directly from
the source PDF text, not guessed:

- **OB_92005, OB_91966**: not actually reshuffled — their locality names
  contain parentheses and wrap across a line break
  ("Si Racha (Protected Area Regional \nOffice 2 Sriracha)"), which the
  original locality regex's character class rejected outright. Widened to
  accept `()` and newlines.
- **OB_100298**: genuinely reshuffled column order
  (`"15.02671 , 100.72298 Khok Samrong - Animal\n(Approximate location)"`
  — coordinates before locality, approximate-flag after "- Animal"). A
  second, narrow fallback regex recovers this exact literal order, tried
  only when the primary (normal-order) pattern finds nothing in that
  block.

Both fixes are scoped to the `LOCATION ... AFFECTED POPULATION
DESCRIPTION` table section of each outbreak chunk (not the whole chunk) —
widening the character class to allow parentheses/newlines without that
bound let the (non-greedy) match creep backwards across earlier section
headers (`FIRST/SECOND/THIRD ADMINISTRATIVE DIVISION`,
`EPIDEMIOLOGICAL UNIT`) on the normal fixtures; this was caught by the
existing Checkpoint 1 test suite regressing and is now covered by
dedicated regression tests (`test_reshuffled_or_parenthesized_location_never_captures_earlier_headers`
and siblings in `test_wahis_parser.py`). Result: 0/670 missing coordinates
in Event_3644.pdf (previously 3/670); 0/682 missing coordinates across all
four WAHIS PDFs.

admin1/admin2/admin3 segmentation remains unresolved and provisional (the
raw division-hierarchy line is preserved verbatim in
`extra["admin_line_raw"]`) — unchanged from Checkpoint 1, deferred to
Phase B per that checkpoint's documented limitation.

## 6. Checkpoint 2.5 — conservative deduplication for the model dataset

Checkpoint 2's policy (§2 above) auto-merges HIGH **and** MEDIUM
confidence groups. That is appropriate for an audit/reproducibility view
(fewer rows, easier to skim), but too permissive for a scientific/model
dataset: MEDIUM is real evidence, but it is *ambiguous* evidence, and an
ambiguous duplicate decision must not be silently treated as resolved
just because it produces a cleaner row count.

`data_processing/model_candidate.py` builds a **second, separate** view on
top of the exact same `build_duplicate_groups()` output — it does not
change Checkpoint 2's grouping/matching logic, its `merged` field, or its
`canonical_outbreaks.csv` / `deduplication_report.csv` outputs, which
remain available unchanged.

**Conservative merge policy:**

| Confidence | Merge? | `dedup_status` | `dedup_resolved` | `model_candidate` |
|---|---|---|---|---|
| HIGH | auto-merged | `AUTO_MERGED_HIGH` | `True` | `True` |
| MEDIUM | **not merged** | `REVIEW_MEDIUM` (every member kept separate) | `False` | `False` |
| LOW | **not merged** | `REVIEW_LOW` (every member kept separate) | `False` | `False` |
| no candidate at all | n/a | `SINGLETON` | `True` | `True` |

`MANUALLY_ACCEPTED` / `MANUALLY_REJECTED` are reserved `dedup_status`
values for a future manual-adjudication step (see `schemas.DedupStatus`)
— nothing in this pipeline assigns them automatically today.

**`model_candidate` is derived only from `dedup_status`.** The composite
DQS (`quality.py`) is never consulted by `model_candidate.py` — not as a
source-strength signal, a sample weight, or an inclusion override. A
record with a very high `dqs` but an unresolved `REVIEW_MEDIUM`/
`REVIEW_LOW` status is still `model_candidate = False`
(`test_high_dqs_does_not_make_an_unresolved_record_a_model_candidate` in
`test_model_candidate.py` proves this directly). If a later
development-only study wants to use DQS as a weighting signal, that must
be an explicit, separately-justified decision at that time — never a side
effect of this pipeline.

### Date-conflict side channel

A record can agree with a candidate on country + strict locality name +
species + tight coordinate distance, and disagree *only* on date, by more
than `DATE_TOLERANCE_DAYS`. Checkpoint 2's `match_pair` correctly treats
this as "no candidate at all" (the date hard-gate short-circuits before
any spatial evidence is even examined) — which is right for the matching
logic, but wrong for the conservative/model view: such a record would look
like an ordinary, unremarkable singleton, when it is actually a genuine
near-miss that deserves a human's attention.

`dedup.find_date_conflicts()` detects these pairs independently (same
gates minus the date check, plus a strict, non-fuzzy locality match and a
tight coordinate distance requirement) and returns them as a **separate
side channel**, deliberately NOT folded into `build_duplicate_groups`'s
union-find graph. `model_candidate.py` applies the resulting flag only to
records that have **no other resolved group membership** — a record
already merged into a clean HIGH group is never downgraded just because
some other, unrelated outlier record happens to conflict with it on date.
This is what keeps Sri Lanka's Chavakachcheri case correct (§7 below): the
well-matched CSV row + WAHIS outbreak stay `AUTO_MERGED_HIGH`, while only
the actual 8-day-outlier CSV row is downgraded to `REVIEW_LOW`.

### Outputs

- `canonical_outbreaks_conservative.csv` — one row per HIGH-merged group
  or per unresolved/singleton record, with all of
  `NORMALIZED_FIELD_NAMES` plus `duplicate_group_id`,
  `member_record_ids`, `member_count`, `dedup_confidence`,
  `dedup_status`, `dedup_resolved`, `review_required`, `model_candidate`,
  `model_exclusion_reason`, `date_conflict_ids`. For an unresolved
  MEDIUM/LOW row, `member_record_ids`/`member_count` describe **only that
  row's own raw record** (matching Checkpoint 2's original convention for
  unmerged rows) — the full candidate group is still traceable via
  `duplicate_group_id` against `deduplication_report.csv`. This matters:
  summing `member_count` across the whole conservative dataset equals the
  total raw record count exactly (an earlier draft of this module summed
  the *group's* member count onto every unresolved row, over-counting by
  ~3x — caught and fixed before this checkpoint's real-data run, now
  guarded by
  `test_member_count_sums_to_raw_record_count_including_medium_and_low`).
- `model_candidate_report.csv` — a focused per-record projection of the
  above (id, country, source, dedup status/resolution/candidacy columns,
  exclusion reason) for quickly auditing exactly what is/isn't eligible
  and why.
- `sri_lanka_adjudication.csv` — one row per raw Sri Lanka source record
  (not per merged group), every CSV row and WAHIS outbreak individually
  visible with its match decision — see §7.

### Availability semantics — unchanged

Checkpoint 1's operational-vs-proxy split (§4 above) passes through this
layer completely unmodified: `operational_availability_date`/`_quality`
stay `None`/`UNKNOWN` for every record (still no source has true
operational evidence), `proxy_availability_date`/`_quality`/
`_source_field` are copied verbatim from the normalized record, and
`RawOutbreakRecord.__post_init__`'s guard against assigning `ACTUAL`
without evidence still applies upstream of this layer — nothing here ever
promotes a proxy into `ACTUAL`.

## 7. Sri Lanka adjudication (Checkpoint 2.5)

Applying the conservative policy plus the date-conflict side channel to
Event_3473.pdf's 6 WAHIS outbreaks vs. the 12 Sri Lanka CSV rows (see
`DATA_AUDIT.md` §14 for the full evidence table) produces exactly the
outcome the checkpoint requires:

- **6 model-candidate outbreaks** (Kopay, Chavakachcheri, Nallur,
  Murunkan, Manthei west, Vavuniya) — each `AUTO_MERGED_HIGH`,
  `model_candidate = True` — the defensible Sri Lanka case-study set.
- **1 preserved-but-excluded record**: the Chavakachcheri CSV row with
  observation date `2020-09-17` (8 days off its matching sibling and the
  WAHIS outbreak, both `2020-09-09`). It is **not deleted** — it remains
  in `canonical_outbreaks_conservative.csv` and `sri_lanka_adjudication.csv`
  with its original fields untouched, `dedup_status = REVIEW_LOW`,
  `review_required = True`, `model_candidate = False`, and
  `model_exclusion_reason` spelling out the exact 8-day conflict against
  both its CSV sibling and the WAHIS outbreak it almost — but does not —
  match. It is **not force-merged** to manufacture a clean count of 6; the
  discrepancy is a genuine source-data inconsistency, surfaced rather than
  hidden, pending manual adjudication.

## 8. Checkpoint 3 — `disease` field added; historical records now importable

Full domain/repository/source-selection design lives in
`REPOSITORY_DESIGN.md`, not here — this section only documents the one
change to the pipeline described above.

**Schema addition:** `RawOutbreakRecord`/`NormalizedOutbreakRecord` gained
a `disease` field (previously absent — every Checkpoint 1-2 source
happened to be Lumpy Skin Disease, so it was never captured explicitly,
but `services/source_selector.get_eligible_sources` genuinely needs a
disease filter). Populated from:
- CSV: the `Disease` column verbatim (`"Lumpy skin disease"`).
- WAHIS PDF: the event title line's middle `" - "`-delimited segment
  (`"{country} - {disease} - {report type}"`, verified against all 4 real
  fixtures — e.g. `"Sri Lanka - Lumpy skin disease virus (Inf. with) -
  Follow-up report 1"` → `"Lumpy skin disease virus (Inf. with)"`).

Purely additive (new `None`-default field) — re-running
`build_canonical.py` reproduces byte-for-byte identical dedup/quality/
canonical results (743 duplicate groups, 2179/2587 canonical/conservative
counts unchanged), just with one extra populated column. The two sources'
different spelling conventions for the same disease are reconciled only
for *matching* purposes (`services/disease.normalize_disease`, mirroring
`data_processing/species.py`'s approach) — never collapsed in the stored
field itself.

**Historical import:** `services/historical_import.py` reads
`canonical_outbreaks_conservative.csv` (Checkpoint 2.5's output) and loads
every row — including `REVIEW_MEDIUM`/`REVIEW_LOW`/`model_candidate=False`
ones — into the local SQLite dev DB's `historical_outbreak_records` table,
unmodified and with the source CSV untouched. See `REPOSITORY_DESIGN.md`
§8 for why the model-candidate gate is deliberately enforced at query
time (by `get_eligible_sources`) rather than at import time.

## 9. Checkpoint 3.5 — no change to historical data or its provenance

Checkpoint 3.5 corrected a date-purity and animal-count bug in the
**live-domain** aggregation service (`services/aggregation.py`,
`OutbreakEpisode`) — see `REPOSITORY_DESIGN.md` §12 for the full
correction. `historical_outbreak_records`, `HistoricalOutbreakRecord`,
`services/historical_import.py`, and everything documented in this file's
§1-8 are **unmodified**. Confirmed, not assumed: the Thailand smoke query
(`t0=2021-05-20`, `active_window_days=14`) still returns exactly 109
RETROSPECTIVE_PROXY sources and 0 STRICT_OPERATIONAL sources after
re-seeding the (recreated, schema-changed-only-for-`outbreak_episodes`)
dev DB from the same, byte-identical `canonical_outbreaks_conservative.csv`.

## 10. Checkpoint 4 — historical replay layer derived from this same data

Checkpoint 4 adds a full historical-replay derivation layer
(`services/canonical_spatial.py`, `services/historical_event_date.py`,
`services/target_quality.py`, `services/forecast_origin.py`,
`services/forecast_target.py`, orchestrated by
`services/build_historical_replay.py`) — all computed from
`canonical_outbreaks_conservative.csv` (unchanged in content;
regenerated only to pick up the `disease` field, see §8) plus the
`historical_outbreak_records` SQLite table (imported unchanged via
Checkpoint 3's `services/historical_import.py`, still importing the FULL
corpus, still gating at query time — see §8's cross-reference). No raw
source file, canonical CSV row, or SQLite table introduced before this
checkpoint was altered.

Full derivation rules, real-corpus counts, and the historical event-date
vs. source-availability distinction: see `DATA_AUDIT.md` §42-51,
`HISTORICAL_CHRONOLOGY_AUDIT.md`, `DATA_EXPOSURE_AUDIT.md`, and
`REPOSITORY_DESIGN.md` §13 (this file stays the canonical raw-to-canonical
data-lineage reference; those documents cover the replay/forecasting
layer built on top of it).

## 11. Checkpoint 4.5 — coordinate-collision correction, no change to raw/canonical lineage

Checkpoint 4.5 corrected the historical-replay layer's coordinate-
independence terminology and hardened forecast-origin discovery — see
`DATA_AUDIT.md` §56-64, `VALIDATION_PROTOCOL.md`. Nothing in this file's
§1-10 (raw parsing, dedup, conservative dataset, historical import)
changed. `canonical_outbreaks_conservative.csv` is byte-identical to the
Checkpoint 4 version; `services/coordinate_collision.py` reads it exactly
as `services/canonical_spatial.py` did, just computing a corrected,
more granular status. Confirmed, not assumed: 2587 historical records
imported (unchanged), 1480 model candidates (unchanged), and the
Thailand smoke query (`t0=2021-05-20`, `active_window_days=14`,
`domain_scope=HISTORICAL_ONLY`, now required explicitly) still returns
exactly 109 RETROSPECTIVE_PROXY sources and 0 STRICT_OPERATIONAL sources.

## 12. Checkpoint 5 — real GIS/environmental data foundation (parallel layer, no outbreak-lineage change)

Checkpoint 5 adds a real GIS/environmental data layer
(`services/geospatial/`) alongside — not on top of — the outbreak
lineage documented in §1-11. Nothing in `canonical_outbreaks*.csv`,
`historical_outbreak_records`, or any derivation service listed above
was read, regenerated, or modified. The only connection back to this
data is that Checkpoint 5's two real-data smoke tests (Sri Lanka
Event_3473 / Chavakachcheri, Thailand Event_3644 / Muang Suang) use
real coordinates and `outbreak_start_date` values taken directly from
`canonical_outbreaks_conservative.csv` rows already documented in §7 and
`DATA_AUDIT.md` — never invented AOI centers.

Full source-by-source provenance (provider, license, dataset version,
reference year, retrieval method, known limitations, SHA-256 hashes of
every cached local file) lives in the new `GIS_DATA_SOURCES.md` and its
machine-readable mirror `local_data/manifests/gis_source_registry.json`
— this file does not duplicate that content. One provenance correction
worth recording here because it was a real, caught scientific error:
FAO GLW4's shipped raster stores animal **count per pixel**, not a
density; an early adapter draft misread it as `animals_per_km2` directly
and produced an implausible ~3785 animals/km² for the Sri Lanka smoke
AOI. Fixed by deriving density from `sum(count) / sum(real per-pixel
area)` using GLW4's own companion area raster — see `GIS_DATA_SOURCES.md`
§2 for the corrected, re-verified values (~44.6 animals/km² for the same
AOI).

## 13. Checkpoint 5.5 — weather dataset-identity, wind-vector, and t0-purity corrections (still no outbreak-lineage change)

Three further corrections to the GIS/environmental layer, none touching
§1-11's outbreak lineage: (1) the historical weather adapter now passes
`models=era5` explicitly on every Open-Meteo request — Checkpoint 5's
adapter never set this parameter and was actually served by whichever
model Open-Meteo's unset `best_match` default picked per date/location,
despite being labeled "ERA5/ERA5-Land" in its own documentation; (2)
`u10`/`v10` are now derived from PAIRED HOURLY wind speed/direction
(each hour's own pair, converted independently then vector-averaged),
replacing a Checkpoint 5 path that paired a daily maximum speed with a
daily dominant direction — two independent statistics that never
described one coherent vector; (3) a historical forecast origin known
only as a calendar date (`T0Precision.DATE_ONLY`, this corpus's normal
case) now excludes the entire t0 calendar day from the primary weather
feature path (`weather_timestamp < t0_start`), not just dates strictly
after t0 — full rationale, live-probed model-selection evidence, and
before/after real-data regression: `ENVIRONMENTAL_FEATURE_PROTOCOL.md`,
`GIS_DATA_SOURCES.md` §3, `DATA_AUDIT.md` §66.

## 14. Checkpoint 5.6 — valid-time/availability-time split, timezone-safe t0, grid-cell host density

Three further corrections, none touching §1-11's outbreak lineage or
§12-13's GLW/model-identity corrections (both remain intact). (1) Every
weather result now separates METEOROLOGICAL VALID TIME (was this
value's own timestamp before t0?) from DATA AVAILABILITY TIME (was it
actually published by t0?) — Checkpoint 5.5's `OBSERVED_REANALYSIS_AT_T0`
name and its "information a real deployed forecaster would have had"
description conflated these two questions; the role is renamed
`RETROSPECTIVE_REANALYSIS_STATE_PROXY` and availability is a separate,
explicit `UNKNOWN`-by-default field, backed by official ECMWF/Copernicus
ERA5T lag documentation where used. (2) `DATE_ONLY` historical t0 dates
are now interpreted as the AOI's own source-local civil date (real IANA
timezone resolved offline, historically-correct UTC offset via
`zoneinfo`) rather than an unconditional UTC date — verified empirically
necessary, not just theoretically: Sri Lanka's real UTC offset differed
before ~2006 from today's, which a hardcoded per-country offset would
have gotten wrong for older records. (3) GLW4 host-density extraction
for the computational risk grid now uses overlap-area-weighted density
across real intersecting source pixels per grid cell, replacing an
arbitrary AOI-window radius that Checkpoint 5.5 showed could swing the
same Sri Lanka centroid's density from 0.0 to ~44.6 animals/km² depending
only on window size. Full rationale, official-documentation citations,
and before/after real-data regression: `ENVIRONMENTAL_FEATURE_PROTOCOL.md`,
`GIS_DATA_SOURCES.md` §2-3, `DATA_AUDIT.md` §67.

## 15. Checkpoint 6A — feature-assembly layer (new consumer, no lineage change)

`services/features/` (`FEATURE_ASSEMBLY_PROTOCOL.md`) is a new
consumer layer built on top of §1-14's outbreak lineage and §12-14's
GIS/environmental corrections — it reads `get_eligible_sources`'
already-correct output and every geospatial adapter's already-correct
`FeatureResult`s, and introduces no new raw-to-canonical processing of
its own. Two real forecast origins already present in
`local_data/manifests/historical_forecast_origins.csv`
(`ORIGIN:Sri Lanka:2020-09-09`, `ORIGIN:Thailand:2021-03-10` — both
derived unchanged from this document's §1-8 pipeline) were used for the
Checkpoint 6A real-data assembly smoke, confirming the assembly layer
consumes existing lineage correctly rather than re-deriving it.

## 16. Checkpoint 6A.5 — feature-assembly reproducibility corrections (no lineage change)

No change to §1-15's outbreak or GIS/environmental lineage. This
checkpoint corrected the feature-assembly layer's OWN reproducibility
guarantees: (1) a real bug where `FeaturePolicy`'s declared
`weather_model` could disagree with the model actually requested from
Open-Meteo (now impossible — `era5.py`'s request always uses its
caller's own `model` argument, and any non-`"era5"` model is refused,
never silently substituted); (2) an ambiguous, hash-only-no-op
`environment_temporal_mode` field removed from `FeaturePolicy`; (3) a
previously-hidden `search_radius_km=25.0` hydrology parameter promoted
to an explicit, hashed `FeaturePolicy.hydrorivers_search_radius_km`;
(4) snapshot identity split into three explicit hashes
(`feature_policy_hash` for declared config, `resolved_data_signature_hash`
for what actually resolved, `snapshot_id` combining both plus
`t0_precision`/`temporal_mode`/etc.) — verified against the same two
real forecast origins from §15: Sri Lanka and Thailand share an
identical `feature_policy_hash` but resolve to different
`resolved_data_signature_hash`es (real WorldCover v100 vs. v200), which
`compare_feature_compatibility` correctly flags as
`LANDCOVER_VERSION_MISMATCH`. Full rationale: `FEATURE_ASSEMBLY_PROTOCOL.md`.

## 17. Checkpoint 6B — model-fitting exposure lineage + ST-DBSCAN context-cluster lineage

Two new provenance chains, both real, both traceable back to the same
already-audited historical corpus (no new raw data source introduced):

**Exposure role**: every forecast origin's `role` (`FIT_DEVELOPMENT` /
`HELD_OUT_FROM_MODEL_FITTING` / `SRI_LANKA_TRANSFER_CASE_STUDY`) is a
pure function of its own `t0` and `country` against the frozen
`MODEL_FITTING_CUTOFF = 2024-01-01` — traceable per-origin in
`local_data/manifests/model_fitting_exposure_manifest.csv` (gitignored,
reproducible via `smoke_tests/run_stdbscan_smoke.py`), with a `reason`
string on every row. See `SPLIT_USAGE_FREEZE.md`.

**Cluster provenance**: every `ClusterAssignment`/`ClusterSummary`
traces back to real `EligibleSource` records via
`services.source_selector.get_eligible_sources` (unchanged reuse) and
real `cluster_event_date`s via
`services.historical_event_date.derive_historical_event_date`
(unchanged reuse) — no new date-fallback chain, no synthetic
coordinates. `config_hash` on every snapshot pins the exact
`STDBSCANConfig` that produced it, so any cluster result is
reproducible from `(forecast_origin_id, t0, config_hash)` alone. Real
smoke provenance recorded in
`local_data/st_cluster_snapshots/{thailand_fit_development_smoke,sri_lanka_case_study_demo}.json`
(gitignored). Full semantics: `STDBSCAN_PROTOCOL.md`.

## 18. Checkpoint 6B.5 — validated development-source-universe lineage

Every `DevelopmentSource` row in
`local_data/manifests/stdbscan_development_source_universe.csv`
traces back to one real `HistoricalOutbreakRecord` via `source_id`,
admitted only because `source_selector.get_eligible_sources` actually
placed it inside a real `FIT_DEVELOPMENT` origin's eligible window —
never because of a raw event-date comparison alone. Every excluded
record is traceable too, with one specific reason, in
`stdbscan_development_source_exclusions.csv` — nothing is silently
dropped. Country-scoped parameter quantiles
(`stdbscan_country_parameter_candidates.csv`) and the deterministic
21-config sensitivity grid
(`stdbscan_international_development_sensitivity.csv`/
`stdbscan_thailand_development_sensitivity.csv`) are both fully
reproducible from `(disease, MODEL_FITTING_CUTOFF, config_hash)` —
no manual/undocumented step. Full rationale: `STDBSCAN_PROTOCOL.md`
§15-19.

## 19. Checkpoint 6C — hazard-engine provenance (software-fixture only)

Every `HazardSnapshot` produced in Checkpoint 6C carries a
deterministic `hazard_config_hash` (covers every kernel/anisotropy/
mixing/link scientific choice — never `generated_at`). **No real hazard
value exists yet** — every factor consumed in this checkpoint carries
`status=SOFTWARE_FIXTURE_ONLY`, and `CellHazardFactors`/
`SourceHazardFactors` structurally refuse any `REAL`-status usable
value. The one real-data artifact this checkpoint produces,
`local_data/hazard_snapshots/software_fixture_only_smoke.json`
(gitignored), is explicitly labeled `SOFTWARE_FIXTURE_ONLY` and must
never be read as, or compared against, real outbreak outcomes. Full
rationale: `HAZARD_ENGINE_PROTOCOL.md`.

## 20. Checkpoint 6C.5 — cell-vs-source indexing correction + hazard input-signature identity

Checkpoint 6C's `HazardFactors` incorrectly grouped cell-level
environmental properties (host/environmental-suitability/water-context)
under a per-SOURCE bag — corrected to `CellHazardFactors` (one per
cell, shared identically by every source's contribution to that cell)
+ `SourceHazardFactors` (one per source, `source_strength_factor`
only) before any real transformer was built, so the mistake never
reached real feature provenance. `HazardSnapshot.hazard_snapshot_id`
now also covers a new `hazard_input_signature_hash` — a deterministic
SHA-256 of every effective mathematical input (cell factors, source
factors, geometry, per-cell meteorology, the expected grid-cell set,
active source IDs). Any change to a real value feeding a future hazard
run (a different cell factor, a different wind vector, an added/removed
grid cell) will change `hazard_snapshot_id`, making every hazard result
traceable to its exact inputs — never just to its config. Full
rationale: `HAZARD_ENGINE_PROTOCOL.md` §0, §14, §17-19; before/after
correction record: `DATA_AUDIT.md` §73.

## 21. Checkpoint 6D — real factor-transformation development provenance

Every `FactorSnapshot` traces back to a real `FeatureSnapshot.snapshot_id`
(never mutated), a `FactorTransformConfig` hash, and a
`FactorReferenceProfile` hash built ONLY from real `FIT_DEVELOPMENT`
material — reused, not re-derived, from the same
`model_fitting_exposure` firewall as every earlier development-only
layer (ST-DBSCAN, 6B.5). Real audit run: 8/8 Thailand `FIT_DEVELOPMENT`
origins successfully assembled (0 blocked), 200 unique host-density
reference observations, single consistent dataset-version composition
throughout (GLW4 2015 / WorldCover v200 2021 / ERA5). Every
`TransformedFactorProvenance` carries its raw feature name(s)/value(s)/
unit(s)/status(es)/dataset version(s) alongside the transformed value —
a bare number never enters a `FactorSnapshot` without this lineage
(Part 21). Full rationale: `FACTOR_TRANSFORMATION_PROTOCOL.md`.

## 22. Checkpoint 6D.5 — corrected reference identity + real full-universe provenance

Checkpoint 6D's `reference_profile_hash()` covered only summary
quantiles, not the full `EMPIRICAL_CDF_REFERENCE` support — corrected
with a `reference_observation_digest` covering every contributing
observation's identity+value (`DATA_AUDIT.md` §75). Static reference
observations (host density) now identify the real underlying GLW4
raster pixel(s) a value was computed from
(`FeatureResult.sample_identity`, populated from the raster's own real
affine-transform geometry, never fabricated) instead of relying
primarily on the rounded query location — two different query
centroids resolving to the same coarse pixel now correctly collapse to
one reference observation. Re-run against the REAL, full,
runtime-derived `FIT_DEVELOPMENT` universe (579 origins, 29 countries,
0 blocked, via a new weather-free host-only gathering path): 12,591 raw
appearances -> 4,974 unique underlying raster observations;
`GLOBAL_REFERENCE_PROFILE_READY` honestly reported (100% universe
coverage); real per-country clipping variation surfaced, not smoothed
away. Full rationale: `FACTOR_TRANSFORMATION_PROTOCOL.md` §16-20.

## 23. Checkpoint 6D.6 — effective weighted-raster identity + real conflict-tolerance correction

§22's `sample_identity` identified only the pixel SET, not the
normalized overlap weights — insufficient, since two cells can share a
pixel set but blend it with different weights and produce genuinely
different values. **CONTRIBUTING PIXEL SET != EFFECTIVE
AREA-WEIGHTED RASTER OBSERVATION unless the contribution weights are
also equivalent.** New `sample_support_digest`
(`FeatureResult`, from `fao_glw.contributing_pixel_sample_support`)
hashes the real weighted contribution support itself — verified against
the live GLW4 cache, not just synthetic fixtures. **Same observation
identity + different raw value is now treated as a DATA/IDENTITY
CONFLICT, never a duplicate** — never resolved by first/last/average.
Rerunning this firewall over the real universe with an initial EXACT
value comparison produced 1,690 false-positive conflicts; direct
measurement showed every one differed by ~3.5e-18 to ~5.7e-14 —
floating-point summation-order noise, not real data. A tiny, documented
SOFTWARE numerical tolerance (`math.isclose(rel_tol=1e-9, abs_tol=1e-9)`,
`reference_observations.values_conflict`) was adopted instead — never a
scientific-similarity judgement, and confirmed via full-population
measurement before being adopted, not assumed. After correction: 579/579
`FIT_DEVELOPMENT` origins, 12,591 raw appearances -> **6,780** unique
effective raster observations (up from §22's 4,974 — the stricter,
weight-aware identity correctly stops over-merging), 26,786 real
observations via `RASTER_EFFECTIVE_SAMPLE_IDENTITY` and 0 via
`QUERY_CENTROID_FALLBACK`, 0 conflicts, `GLOBAL_REFERENCE_PROFILE_READY`
re-earned honestly under the corrected protocol. Full rationale:
`FACTOR_TRANSFORMATION_PROTOCOL.md` §21.
