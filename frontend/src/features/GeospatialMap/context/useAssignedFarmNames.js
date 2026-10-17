import { useEffect, useState } from 'react'

import { readAuthToken } from '../api/operationalApi'

/**
 * Display names for the vet's assigned farms, read from the team's own
 * `GET /api/vet/my-farms` (health_anomaly router -- the same endpoint the
 * Assigned Farms page uses). Geospatial's operational context deliberately
 * carries only farm ids and GPS; this adds the human-readable name the vet
 * already sees elsewhere in ADRS. Read-only, once per page mount. On any
 * failure the map stays usable and rows fall back to "Assigned farm".
 *
 * Returns `Map<farmId, { name, district }>`.
 */
export function useAssignedFarmNames(refreshKey = null) {
  const [names, setNames] = useState(() => new Map())
  // Re-read for another signed-in vet (never keep the previous vet's farm
  // names) and after a live data change (a newly assigned farm).
  const session = readAuthToken()

  useEffect(() => {
    const token = session
    if (!token) {
      setNames(new Map())
      return undefined
    }
    const controller = new AbortController()
    fetch('/api/vet/my-farms', { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then((response) => (response.ok ? response.json() : []))
      .then((rows) => {
        if (!Array.isArray(rows)) return
        const next = new Map()
        for (const row of rows) {
          if (row && typeof row.id === 'string' && typeof row.owner_name === 'string' && row.owner_name.trim()) {
            next.set(row.id, { name: row.owner_name.trim(), district: typeof row.location_district === 'string' ? row.location_district : null })
          }
        }
        setNames(next)
      })
      .catch(() => {})
    return () => controller.abort()
  }, [session, refreshKey])

  return names
}
