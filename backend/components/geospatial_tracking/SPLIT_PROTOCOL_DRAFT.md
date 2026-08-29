# Split Protocol Draft — Checkpoint 4 Parts 11-14

> **Checkpoint 4.5 update:** the PRIMARY VALIDATION STRATEGY analysis
> below (walk-forward, Part 11) and the 7-day embargo/purge rule (Part
> 14) are now **FROZEN** — see `VALIDATION_PROTOCOL.md`, the
> authoritative frozen decision document, for the exact frozen rules, the
> `PURGED_7_DAY_HORIZON_POLICY`, task-specific (risk/direction/speed)
> protocols, and real candidate walk-forward fold counts
> (`walk_forward_fold_candidates.csv`,
> `walk_forward_fold_candidates_thailand_direction.csv`). This document's
> ORIGINAL analysis (which strategy, and why) is preserved below
> unmodified, since it is exactly the chronology-only reasoning the freeze
> decision rests on. Terminology note: "canonical spatial independence" /
> "spatially non-independent" below refers to what
> `services/coordinate_collision.py` now more accurately calls
> coordinate-collision status (`UNIQUE_AMONG_RESOLVED` /
> `SHARED_WITH_RESOLVED` / `SHARED_WITH_UNRESOLVED` / `SHARED_WITH_BOTH`)
> — see `HISTORICAL_CHRONOLOGY_AUDIT.md` §5 for the corrected numbers;
> the strategic conclusions below are unaffected by the terminology fix.
>
> Still NOT frozen: the exact split-boundary DATE(s) to use, which
> candidate fold schedule (global vs. Thailand-only vs. a future nested
> variant) is "the" one applied, and the Part 14 exclusion mechanism
> beyond "purge the whole origin" (now the frozen default — see
> `VALIDATION_PROTOCOL.md` §2). No final train/test file has been built
> (master-prompt Part 11).

**Draft only [superseded in part — see notice above]. No split is
frozen. No model exists to evaluate, so nothing here is chosen because it
"performs better" — there is no performance yet to compare.**
Recommendations are based only on chronology, target counts, temporal
coverage, independence, and data quality, all documented in
`HISTORICAL_CHRONOLOGY_AUDIT.md`.

**Random shuffling is explicitly rejected as the primary strategy** —
`train_test_split(random_state=...)` or any row-level shuffle would
scatter target-events with strong temporal/spatial correlation (repeated
outbreak reports from the same epidemic wave, e.g. Thailand's 2021-05
peak) across both sides of a split, which is a textbook leakage pattern
for spatiotemporal forecasting: a model could learn from a report two
days before an "unseen" neighboring report in the same wave. This
checkpoint's own code (`services/split_embargo.py`) contains no random
shuffling — verified structurally by `test_split_01_...`.

## Part 11 — Candidate strategies

### A. Chronological blocked development / validation / evaluation

Pick two boundary dates B1 < B2 (or per-country boundaries). Everything
with `t0 < B1` is DEVELOPMENT, `B1 <= t0 < B2` is TEMPORAL_VALIDATION,
`t0 >= B2` is the final held-out evaluation set. One fixed split,
computed once.

**For:** simplest to reason about and communicate; matches the
"deployment" mental model directly (a model built on the past, checked
against a fixed later period).

**Against, given this corpus's actual chronology:** Thailand's chronology
is dominated by ONE concentrated wave (2021-04 to 2021-07, peaking
2021-05 at 185/432 records — 43% of Thailand's whole candidate count).
Any single boundary drawn through or near that wave either (a) puts
almost the entire wave on one side, leaving the other side of Thailand's
data thin and non-representative, or (b) requires drawing the boundary
well before or after the wave, which then makes one partition
disproportionately large relative to the other for the country that
matters most for Tier-A direction/speed depth (`HISTORICAL_CHRONOLOGY_AUDIT.md`
§6). A single fixed cut is fragile to exactly where it lands relative to
this one wave.

### B. Chronological walk-forward validation

Multiple boundaries, sliding forward through time: fit on
`t0 < B_k`, evaluate the immediately-following window, advance `B_k`,
repeat. Aggregate performance across all folds.

**For:** does not depend on one boundary's placement relative to
Thailand's wave — every fold sees a genuinely later period than its own
fit window, and the wave's internal structure is sampled across multiple
folds rather than being entirely inside or outside one fixed cut. Better
matches PISTES's actual deployment logic too (§ forecast-origin-triggered,
not a one-time train/deploy event) — see master-prompt Part 6.

**Against:** more folds to manage/report; requires deciding a
minimum-fit-window size before the first fold is meaningful (too little
early data — see `HISTORICAL_CHRONOLOGY_AUDIT.md` §4/§7: pre-2020-09
data across all countries totals only 284 candidates, thin for an early
fold).

### C. Nested chronological walk-forward (if a reliable final holdout is too small)

Walk-forward (B) used for *model selection/tuning* within an outer
chronological split, so the true final evaluation window is never touched
during any tuning decision, even across folds.

**Relevant here because:** Thailand is the only country with real Tier-A
depth (313 unique targets — `HISTORICAL_CHRONOLOGY_AUDIT.md` §6). If
Thailand's late-chronology tail (thin: single digits per month from
2021-08 onward, per §4) is reserved as a genuinely untouched final
window, it may be too small on its own for a stable final-evaluation
estimate — nesting lets walk-forward do the tuning work on the richer
middle period while keeping a small but real final holdout clean.

### D. Geographic transfer case study (separate analysis, not a substitute for A/B/C)

Fit on one geography's chronology (e.g. Thailand, or a multi-country
DEVELOPMENT pool), evaluate against a *different* geography (Sri Lanka)
with no chronological ordering claim implied. Reported as its own
analysis, explicitly labeled `GEOGRAPHIC_TRANSFER_CASE_STUDY` (see
`DATA_EXPOSURE_AUDIT.md` §3), not folded into the primary temporal-split
numbers.

**Required regardless of which of A/B/C is chosen as primary** — Sri
Lanka's N=6 (§Part 12 below) cannot support a temporal-split role on its
own no matter how the boundary is drawn.

## Part 12 — Sri Lanka: the concrete chronology problem

Sri Lanka has exactly 6 defensible model-candidate episodes
(`HISTORICAL_CHRONOLOGY_AUDIT.md` §2), all within a 52-day window
(2020-09-07 to 2020-10-28). This is **not** a "large external validation
dataset" or "statistically strong external test" under any framing — N=6
cannot support a powered statistical test of anything.

**The specific chronology check the master prompt requires:** does
development data occur after the Sri Lanka 2020 event, which would rule
out calling a Sri-Lanka-2020 evaluation "prospective"?

**Answer: yes, and unavoidably so for any development pool that includes
Thailand.** 11 countries have data starting before 2020-09-07 (284
candidates total: Russian Federation 146, China 37, Bhutan 26, Nepal 21,
India 15, Israel 18, Bangladesh 11, Namibia 3, Georgia 3, Syrian Arab
Republic 3, West Bank 1 —
`HISTORICAL_CHRONOLOGY_AUDIT.md` §7 has the full list). **Thailand's data
starts 2021-03-10 — entirely AFTER Sri Lanka's event — and Thailand is
the only country in this corpus with meaningful Tier-A direction/speed
depth (313 of ~314 unique Tier-A targets corpus-wide,
`HISTORICAL_CHRONOLOGY_AUDIT.md` §6).** Any development process that
wants that Tier-A depth — which any serious direction/speed model
development would — necessarily uses data that postdates Sri Lanka's
event.

**Conclusion:** Sri Lanka 2020 must be labeled a
**GEOGRAPHIC_TRANSFER_CASE_STUDY** (retrospective), not
`TEMPORAL_VALIDATION`, for any development pool realistically including
Thailand. It could only be called genuinely prospective temporal
validation if development were restricted to the 284-candidate,
pre-2020-09 pool — which has no Tier-A depth to speak of (all Thailand's
own Tier-A depth comes from 2021+) and is far thinner than what a
direction/speed model would need. This tradeoff is exactly why Part 13
below matters.

**Recommended framing:** report Sri Lanka results as a labeled
qualitative/limited-quantitative geographic transfer case study (N=6,
explicitly stated), never as a validation-set performance number
alongside the primary chronological split's metrics.

## Part 13 — Older-international-data-first design: options, not a decision

Could a genuinely chronological design use the 11 pre-2020-09 countries'
284 candidates as early DEVELOPMENT, with later-arriving countries
(including but not limited to Thailand/Sri Lanka) as later validation
folds — without forcing Thailand and Sri Lanka into pre-decided roles?

**Option 1 — pooled early-international development, single later
evaluation window (all countries mixed after the boundary).** Simple, but
mixes highly heterogeneous countries (different reporting systems,
mostly UNKNOWN GPS precision except Thailand) into one evaluation pool —
a model's error on that pool would be hard to attribute to genuine
skill vs. one country's data characteristics dominating.

**Option 2 — walk-forward (Part 11.B) over the pooled, all-country
chronology, with country identity retained as a reported dimension (not
a split rule).** Avoids hardcoding "Thailand = training, Sri Lanka =
test" while still surfacing per-country performance differences.
Consistent with master-prompt Part 8's rule ("the repository may FILTER
by country, but must not hardcode scientific split policy").

**Option 3 — do not use all 37 countries.** `HISTORICAL_CHRONOLOGY_AUDIT.md`
§3 lists 14 countries with 1-4 candidates each — not enough for any
within-country temporal structure, and their inclusion would mean a
model "learns" almost nothing generalizable from them while they still
count toward "37 countries used." A minimum-depth inclusion threshold
(e.g. requiring some minimum number of unique event dates, not just raw
count — Indonesia's 60-candidates-but-3-dates case in §8 shows why count
alone is insufular) should be decided **later**, with justification, not
assumed now.

These are options for the next checkpoint to decide among, with
`HISTORICAL_CHRONOLOGY_AUDIT.md`'s per-country counts/coverage as the
input — not a decision made here.

## Part 14 — Horizon-boundary / split embargo rule

The forecast horizon is D1-D7. A development forecast origin's own
targets can extend up to 7 days past its `t0`. If a split boundary `B` is
drawn without accounting for this, a development-partition origin whose
`t0` is within 7 days of `B` would have real target-label information
(what happened 1-7 days later) reaching into the validation/evaluation
period while the origin itself is still counted as "development" —
target leakage across the boundary.

**Rule, implemented and tested (`services/split_embargo.py`,
SPLIT-02):**

```
partition(origin) = BEFORE_BOUNDARY   if t0 <  B
                   = AT_OR_AFTER_BOUNDARY  if t0 >= B     (B itself is "after")

embargoed(origin) = partition == BEFORE_BOUNDARY
                     AND (t0 + 7) >= B
```

An embargoed BEFORE_BOUNDARY origin's target window `[t0+1, t0+7]`
reaches or crosses `B`. This function only **identifies** which origins
the embargo rule applies to — it does not yet choose an exclusion
strategy. Options for a later checkpoint to pick among (documented here,
not decided):

1. **Drop the embargoed origin entirely** from the BEFORE_BOUNDARY
   partition (simplest, loses some development data near the boundary).
2. **Keep the origin, but drop only the specific targets whose
   `historical_event_date >= B`** (keeps more development data, requires
   per-target rather than per-origin filtering — `historical_forecast_targets.csv`
   already carries `historical_event_date` per target, so this is
   mechanically available).
3. **Shrink the boundary-adjacent origins' evaluation horizon** so no
   target crosses `B` (most complex, avoids losing origins or targets
   outright at the cost of inconsistent horizon lengths near the
   boundary).

No default is chosen. Whichever a later checkpoint picks, it must apply
`embargoed_before_origins(...)` (or the per-target equivalent) before any
development work touches boundary-adjacent origins — never a silent
default of "development gets everything with `t0 < B`."

## Recommendation (chronology/coverage/quality only — no model exists)

**Primary: walk-forward validation (B), nested if the final Thailand-tail
window proves too small on its own (C).** Reasons, from
`HISTORICAL_CHRONOLOGY_AUDIT.md`:

- Thailand's one dominant 2021 wave makes a single fixed boundary (A)
  fragile to exactly where it lands.
- PISTES's own deployment model (forecast-origin-triggered, master-prompt
  Part 6) is inherently walk-forward-shaped — evaluating that way matches
  how the system would actually run.
- Nesting (C) is available as a fallback specifically because Thailand's
  post-2021-07 tail is thin (§4), and Thailand is the only country
  carrying real Tier-A depth (§6) — a naive single final holdout drawn
  from that thin tail risks an unstable evaluation estimate.

**Required alongside the primary strategy, not instead of it:** a
separately labeled Sri Lanka geographic transfer case study (D), per Part
12's chronology finding — Sri Lanka cannot be a temporal-validation fold
under any boundary placement given its N and its 2020 timing relative to
Thailand's data.

**Deferred, not decided:** whether to restrict which of the 37 countries
enter the walk-forward pool at all (Part 13, Option 3) and the exact
embargo-exclusion mechanism (Part 14) — both require a decision this
checkpoint deliberately does not make.
