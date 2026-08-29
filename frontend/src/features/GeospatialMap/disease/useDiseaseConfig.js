import { useMemo } from 'react'

import { getDiseaseConfig } from './diseaseRegistry'

/** Thin memoized lookup -- kept as a hook only so components re-render
 * correctly if the registry ever becomes dynamic (e.g. fetched readiness
 * from `/api/geospatial/protocol` instead of hardcoded); the registry
 * itself stays a plain object today, per the "no new dependency" plan. */
export function useDiseaseConfig(code) {
  return useMemo(() => getDiseaseConfig(code), [code])
}
