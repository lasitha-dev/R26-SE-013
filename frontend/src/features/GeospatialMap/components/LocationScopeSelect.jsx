import React from 'react'

import {
  LABEL_LOCATION_MY_DISTRICT,
  LABEL_LOCATION_MY_DISTRICT_UNAVAILABLE,
  LABEL_LOCATION_SCOPE,
  LABEL_LOCATION_SRI_LANKA,
} from '../semanticLabels'

export const LOCATION_SCOPE = { SRI_LANKA: 'sri_lanka', MY_DISTRICT: 'my_district' }

/**
 * GEO26B/GEO26D/GEO30A/GEO31A Section 5/8: "Sri Lanka Overview" re-fits
 * the same real national bounds `resetView()` already computes -- CAMERA
 * ONLY, never a data filter (national context always stays in
 * application state regardless of which option is selected). "My
 * District · <real district>" fits the real bounds of the vet's own
 * registered-district-matched farms (falling back to personally-
 * assigned farms if the district itself has none) --
 * REAL_DISTRICT_GEOMETRY_BLOCKED: no Sri Lanka ADM2 boundary dataset
 * exists anywhere in this repo, so this never draws a fabricated
 * polygon; it only moves the camera to a real, authorized bounding box.
 * Disabled (not merely hidden) when the vet has no real farm location to
 * fit yet, so the control never silently no-ops.
 *
 * GEO31A: "bare" (no self-contained pill) -- composed inside the single
 * unified toolbar in `OutbreakMapPage.jsx`, using the host dashboard's
 * real design tokens and a real `expand_more` Material Symbol instead of
 * the native `<select>` arrow (Section 8's "avoid native browser
 * styling if the project already uses a shared Select component" --
 * this repo has no such shared component, so a real icon over the
 * native control is the closest honest equivalent without introducing a
 * new UI library, per Section 17).
 */
export default function LocationScopeSelect({ value, onChange, myDistrictAvailable, districtName }) {
  const myDistrictLabel = districtName ? `${LABEL_LOCATION_MY_DISTRICT} · ${districtName}` : LABEL_LOCATION_MY_DISTRICT

  return (
    <label className="flex items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant/70">{LABEL_LOCATION_SCOPE}</span>
      <span className="relative flex items-center">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={LABEL_LOCATION_SCOPE}
          className="cursor-pointer appearance-none rounded-md bg-surface-container-high/60 py-2 pl-3 pr-7 text-sm font-medium text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <option value={LOCATION_SCOPE.SRI_LANKA} className="bg-surface-container-high">
            {LABEL_LOCATION_SRI_LANKA} Overview
          </option>
          <option
            value={LOCATION_SCOPE.MY_DISTRICT}
            disabled={!myDistrictAvailable}
            title={myDistrictAvailable ? undefined : LABEL_LOCATION_MY_DISTRICT_UNAVAILABLE}
            className="bg-surface-container-high"
          >
            {myDistrictAvailable ? myDistrictLabel : `${myDistrictLabel} (unavailable)`}
          </option>
        </select>
        <span aria-hidden="true" className="material-symbols-outlined pointer-events-none absolute right-1.5 text-[18px] text-on-surface-variant/70">
          expand_more
        </span>
      </span>
    </label>
  )
}
