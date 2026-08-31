# Local Evaluation Scope Rationale — Checkpoint 7A.6 / 7A.6.1

**Purpose**: document, BEFORE any predictive score is calculated, why
`PRIMARY_LOCAL_EVALUATION_DISTANCE_KM = 25.0` was declared as the
`FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE` for PISTES's local
spread-risk evaluation domain.

**Checkpoint 7A.6.1 wording correction (Part 36)**: 25 km is a
**LITERATURE-INFORMED, PRE-MODEL OPERATIONAL LOCAL EVALUATION ENVELOPE**
— never a "literature-validated biological cutoff" or a "proven LSD
local transmission radius." Until exact bibliographic references are
independently verified (see the citation-verification caveat below),
this document never claims more than that the literature it
characterizes *informed* this pre-model scope decision.

## What this number is — and is not

25 km is an **OPERATIONAL LOCAL ANALYSIS ENVELOPE**: a computational
boundary that scopes which future outbreak events are evaluated as
candidates for "local spatial spread" from a given forecast origin's
eligible active sources.

It is explicitly **NOT**:

- an LSD transmission radius,
- a maximum vector (blood-feeding arthropod) flight distance,
- an infection boundary,
- a kernel decay-length scale (`services.hazard.kernels.distance_scale_km`
  remains its own, separately unfrozen parameter),
- a spread-front reach or rate, or
- a speed × time product.

A future event outside this envelope is not asserted to be
epidemiologically unrelated — see `MODEL_DEVELOPMENT_PROTOCOL.md` and
`services/model_development/local_evaluation_scope.py` for the exact
`WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE` /
`OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE` terminology and its precise,
limited meaning.

## Why 25 km, specifically

1. **It was already part of the predeclared domain-candidate registry**
   (`PREDECLARED_DOMAIN_CANDIDATES_KM = (25, 50, 75, 100, 150, 200)`,
   fixed in Checkpoint 7A before any coverage number was computed). This
   checkpoint selects the SMALLEST of that pre-existing list as the
   primary operational envelope — it does not introduce a new number.
2. **This is a scope/design decision, not a decision made by model
   accuracy.** No predictive score, capture rate, or held-out/Sri-Lanka
   outcome informed this choice; it was frozen before any such score
   exists anywhere in this codebase.
3. **Consistency with the general literature characterization of LSD
   spread** (as summarized in this project's own working notes — see the
   caveat below on citation verification):
   - A Thailand-focused transmission-kernel analysis is understood to
     have estimated that local herd-to-herd transmission distances were
     predominantly sub-kilometre in the provinces studied — i.e. most
     local spread happens at a much finer scale than 25 km.
   - A 2025 Sardinia spatial-epidemiology analysis is understood to have
     identified a localized high-transmission-rate cluster on a
     several-kilometre spatial scale, while also noting occasional
     longer-distance disease displacement.
   - WOAH (World Organisation for Animal Health) characterizes LSD
     transmission as predominantly associated with blood-feeding
     arthropod vectors, which is generally consistent with short-range
     local spread dominating over long-range spread.
   - Broader Thailand-focused spatial studies are understood to note
     that longer-distance spread, when it occurs, may involve animal
     movement (e.g. trade, transport) or other non-vector mechanisms
     rather than local vector-mediated transmission.
4. **25 km is therefore a deliberately CONSERVATIVE envelope** relative
   to the sub-km/several-km scales the literature above associates with
   local short-range spread — it is chosen to comfortably contain
   genuine local spread signal without narrowly cutting it off, while
   still being far short of a scale that would functionally erase the
   local/non-local distinction altogether.
5. **Animal-movement-mediated long-distance transmission is not modeled
   directly** — this codebase has no livestock movement/trade dataset
   available, so any long-distance dissemination mechanism the
   literature above associates with movement rather than vectors is,
   by construction, out of scope for the LOCAL spread-risk model. Events
   outside the 25 km envelope are not deleted — they remain in the
   complete audit ledger (`OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE`,
   never dropped) for future, separately-scoped work.

## Citation-verification caveat

The literature characterizations above are recorded as they were
described when this rationale was authored, matched to their general
topic and finding. **No specific bibliographic details (author names,
publication venue, year, DOI) have been independently verified or
fetched within this codebase**, and none are fabricated here. Before
this document is cited externally as a formal literature reference, the
exact source publications should be independently located and verified.
No literature statistic here has been converted into a fitted model
coefficient — this document informs a scope/design decision only.

## Development target-distance exposure — disclosed, not hidden

`DEVELOPMENT_TARGET_DISTANCE_DISTRIBUTION_ALREADY_EXPOSED = True`
(`services/model_development/local_evaluation_scope.py`).

Checkpoint 7A had already computed and reported the real
`FIT_DEVELOPMENT` target-to-nearest-eligible-source distance
distribution (min 0.0km, p50 33.5km, p95 161.7km, p99 372.9km, max
3,290.5km) before this 25 km envelope was declared in Checkpoint 7A.6.
**This scope choice is never claimed to have been made blind to that
distribution.** The distribution informed the checkpoint AUTHOR's
awareness that 25 km would leave most development targets
`OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE` — this was accepted
deliberately (per points 1-5 above) rather than treated as a reason to
widen the envelope, and no later real audit result was permitted to
change this number (Part 22-23: the real post-freeze audit is reported,
never used to reselect the envelope).
