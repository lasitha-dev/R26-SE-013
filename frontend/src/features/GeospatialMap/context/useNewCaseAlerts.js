/**
 * "New case" alerts from the REAL national case records. Each refresh of
 * `/national-cases` (realtime data-change event or the existing heartbeat)
 * is compared with the previous one by stable `record_key`:
 *  - a key never seen before          -> NEW_CASE
 *  - pending -> verified on a known key -> VERIFIED
 * The first successful load only primes the comparison (never alerts), so a
 * page open never floods the vet with old records. Alerts expire after a
 * short visible period on an event-driven RAF (no second polling timer).
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { normalizeDistrictDisplayName } from '../adapters/districtGeometry'

export const MAX_ALERTS = 3
export const CASE_ALERT_DURATION_MS = 8000

/** Pure diff between two record lists (testable without React). */
export function diffCaseRecords(previousByKey, records) {
  const alerts = []
  for (const record of Array.isArray(records) ? records : []) {
    const key = record?.record_key
    if (!key) continue
    const before = previousByKey.get(key)
    if (before === undefined) alerts.push({ kind: 'NEW_CASE', record })
    else if (before !== 'VERIFIED' && record.verification_status === 'VERIFIED') alerts.push({ kind: 'VERIFIED', record })
  }
  return alerts
}

export function alertText(alert) {
  const r = alert.record ?? {}
  const district = normalizeDistrictDisplayName(r.district) ?? 'district not recorded'
  return alert.kind === 'NEW_CASE'
    ? `New ${r.disease ?? ''} case ${r.verification_status === 'VERIFIED' ? '(vet-verified)' : '(pending verification)'} · ${district}`
    : `${r.disease ?? ''} case verified · ${district}`
}

export function useNewCaseAlerts(records) {
  const previousRef = useRef(null)
  const seenKeysRef = useRef(new Set())
  const [alerts, setAlerts] = useState([])

  useEffect(() => {
    if (!Array.isArray(records)) return
    const current = new Map(records.filter((r) => r?.record_key).map((r) => [r.record_key, r.verification_status]))
    if (previousRef.current) {
      const fresh = diffCaseRecords(previousRef.current, records)
        .filter((alert) => alert.kind !== 'NEW_CASE' || !seenKeysRef.current.has(alert.record.record_key))
        .map((alert) => ({ ...alert, expiresAt: performance.now() + CASE_ALERT_DURATION_MS, id: `${alert.kind}:${alert.record.record_key}:${alert.record.verification_status}` }))
      if (fresh.length) setAlerts((prev) => [...fresh, ...prev.filter((a) => !fresh.some((f) => f.id === a.id))].slice(0, MAX_ALERTS))
    }
    previousRef.current = current
    for (const key of current.keys()) seenKeysRef.current.add(key)
  }, [records])

  useEffect(() => {
    if (!alerts.length) return undefined
    let frameId
    const expire = (now) => {
      if (alerts.some((alert) => alert.expiresAt <= now)) {
        setAlerts((current) => current.filter((alert) => alert.expiresAt > now))
        return
      }
      frameId = requestAnimationFrame(expire)
    }
    frameId = requestAnimationFrame(expire)
    return () => cancelAnimationFrame(frameId)
  }, [alerts])

  const dismiss = useCallback((id) => setAlerts((prev) => prev.filter((a) => a.id !== id)), [])
  return { alerts, dismiss }
}
