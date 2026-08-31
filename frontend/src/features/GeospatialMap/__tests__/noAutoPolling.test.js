import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * GEO-LIVE-UPDATE-RECOVERY-06 / GEO-HYBRID-LIVE-SYNC-08: this checkpoint
 * replaced the original ABSOLUTE "no polling anywhere" rule with a
 * narrower one -- a bounded, single, cleaned-up reconciliation fallback is
 * now permitted, but ONLY for the operational/live-clinical plane
 * (`context/useOperationalContext.js`), never for the scientific/
 * historical plane (national outbreaks, origins, trigger-sources, risk,
 * clusters, trajectory, environmental/model data).
 *
 * GEO-HYBRID-LIVE-SYNC-08 Phase 5 narrows the mechanism further: the
 * operational reconciliation clock is now a single self-scheduling
 * `setTimeout` loop (never `setInterval`, never `requestAnimationFrame`
 * used as a busy network-polling clock) -- so the old blanket "no
 * setTimeout anywhere" assertion is retired in favor of a SCOPED one:
 * `setTimeout` may exist ONLY in `useOperationalContext.js`; `setInterval`
 * remains banned everywhere, with no exception.
 */

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const OPERATIONAL_SCHEDULER_FILE = join('context', 'useOperationalContext.js')

const SCIENTIFIC_DATA_FILES = [
  'context/useNationalOutbreaks.js',
  'context/useSelectedOutbreakFrames.js',
  'context/useFmdOriginRisk.js',
  'context/useDiseaseOriginLedger.js',
  'context/useAnalysisTrends.js',
  'context/GeospatialContext.jsx',
]

function collectSourceFiles(dir) {
  const files = []
  for (const entry of readdirSync(dir)) {
    if (entry === '__tests__' || entry === 'node_modules') continue
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      files.push(...collectSourceFiles(full))
    } else if (/\.(js|jsx)$/.test(entry)) {
      files.push(full)
    }
  }
  return files
}

function relativePath(absolutePath) {
  return absolutePath.slice(FEATURE_ROOT.length + 1).split('\\').join('/')
}

describe('11A-POLL-01: setInterval is banned everywhere in this feature, no exception', () => {
  it('no source file under GeospatialMap/ (excluding tests) calls setInterval', () => {
    const files = collectSourceFiles(FEATURE_ROOT)
    expect(files.length).toBeGreaterThan(0)
    for (const file of files) {
      const src = readFileSync(file, 'utf-8')
      expect(src.includes('setInterval(')).toBe(false)
    }
  })
})

describe('GEO-HYBRID-LIVE-SYNC-08 Phase 5: setTimeout is scoped to exactly one file -- the operational reconciliation scheduler', () => {
  it('no source file OTHER than useOperationalContext.js calls setTimeout', () => {
    const files = collectSourceFiles(FEATURE_ROOT)
    for (const file of files) {
      const rel = relativePath(file)
      if (rel === 'context/useOperationalContext.js') continue
      const src = readFileSync(file, 'utf-8')
      expect(src.includes('setTimeout('), `${rel} unexpectedly calls setTimeout(`).toBe(false)
    }
  })

  it('useOperationalContext.js calls setTimeout exactly once -- one reconciliation scheduler, not several', () => {
    const src = readFileSync(join(FEATURE_ROOT, OPERATIONAL_SCHEDULER_FILE), 'utf-8')
    const count = src.split('setTimeout(').length - 1
    expect(count).toBe(1)
    expect(src).toContain('setTimeout(runFetch, REFRESH_INTERVAL_MS)')
  })

  it('useOperationalContext.js never calls setInterval and never uses requestAnimationFrame as a polling clock', () => {
    const src = readFileSync(join(FEATURE_ROOT, OPERATIONAL_SCHEDULER_FILE), 'utf-8')
    expect(src.includes('setInterval(')).toBe(false)
    expect(src.includes('requestAnimationFrame(')).toBe(false)
  })
})

describe('GEO-HYBRID-LIVE-SYNC-08: the scientific/historical plane is never polled', () => {
  for (const relPath of SCIENTIFIC_DATA_FILES) {
    it(`${relPath} has no recurring-fetch loop (no setInterval, setTimeout, or requestAnimationFrame)`, () => {
      let src
      try {
        src = readFileSync(join(FEATURE_ROOT, relPath), 'utf-8')
      } catch {
        return // file doesn't exist on this branch -- nothing to poll
      }
      expect(src.includes('setInterval(')).toBe(false)
      expect(src.includes('setTimeout(')).toBe(false)
      expect(src.includes('requestAnimationFrame(')).toBe(false)
    })
  }

  it('the slow trigger-sources/origins endpoints are never referenced by the operational reconciliation hook', () => {
    const src = readFileSync(join(FEATURE_ROOT, OPERATIONAL_SCHEDULER_FILE), 'utf-8')
    expect(src).not.toContain('trigger-sources')
    expect(src).not.toContain('/origins')
  })
})

describe('GEO-HYBRID-LIVE-SYNC-08: the operational reconciliation scheduler is safe (cleanup, overlap, staleness, hidden-tab, resume)', () => {
  const hookSrc = readFileSync(join(FEATURE_ROOT, OPERATIONAL_SCHEDULER_FILE), 'utf-8')

  it('exists only while mounted -- clears the pending cycle, aborts any in-flight request, and removes the visibility listener on unmount', () => {
    const cleanupStart = hookSrc.lastIndexOf('return () => {')
    const cleanupBody = hookSrc.slice(cleanupStart)
    expect(cleanupBody).toContain('mountedRef.current = false')
    expect(cleanupBody).toContain('clearTimeout(timeoutRef.current)')
    expect(cleanupBody).toContain('abortControllerRef.current?.abort()')
    expect(cleanupBody).toContain("removeEventListener('visibilitychange'")
  })

  it('prevents overlapping requests -- a new fetch aborts any still-in-flight one first', () => {
    expect(hookSrc).toContain('if (inFlightRef.current) {')
    expect(hookSrc).toContain('abortControllerRef.current?.abort()')
  })

  it('ignores a stale response that resolves after unmount or abort', () => {
    expect(hookSrc).toContain('if (!mountedRef.current || controller.signal.aborted) return null')
  })

  it('recovers after a transient request failure -- a NETWORK_ERROR/OPERATIONAL_UNAVAILABLE result keeps polling rather than terminating it', () => {
    const reducerSrc = readFileSync(join(FEATURE_ROOT, 'context', 'operationalRefreshReducer.js'), 'utf-8')
    expect(reducerSrc).toContain("case 'OPERATIONAL_UNAVAILABLE':")
    expect(reducerSrc).toContain("case 'NETWORK_ERROR':")
  })

  it('a terminal 401/403/404 result stops the scheduler -- the next-cycle timer is never armed', () => {
    expect(hookSrc).toContain('if (!shouldPoll(next.state)) return')
  })

  it('pauses fully on a hidden tab -- no fetch, no reschedule while document.visibilityState is hidden', () => {
    expect(hookSrc).toContain('shouldPauseForHiddenTab(')
    expect(hookSrc).toContain('document.visibilityState')
  })

  it('resumes with exactly one immediate reconciliation when the tab becomes visible again', () => {
    const listenerStart = hookSrc.indexOf('function onVisibilityChange()')
    const listenerBody = hookSrc.slice(listenerStart, hookSrc.indexOf('\n    }\n', listenerStart) + 6)
    expect(listenerBody).toContain("document.visibilityState === 'visible'")
    expect(listenerBody).toContain('runFetch()')
  })

  it('a visibility flip always clears any pending timer first, in either direction -- never two timers, never a stale scheduled request racing a fresh one', () => {
    const listenerStart = hookSrc.indexOf('function onVisibilityChange()')
    const listenerEnd = hookSrc.indexOf('\n    }\n', listenerStart) + 6
    const listenerBody = hookSrc.slice(listenerStart, listenerEnd)
    const clearIndex = listenerBody.indexOf('clearTimeout(timeoutRef.current)')
    const visibleCheckIndex = listenerBody.indexOf("document.visibilityState === 'visible'")
    expect(clearIndex).toBeGreaterThan(0)
    expect(clearIndex).toBeLessThan(visibleCheckIndex)
  })

  it('every settled fetch (scheduled cycle, manual refresh, or SSE-triggered refresh) is the one that reschedules -- an aborted/superseded call never reschedules on its own', () => {
    expect(hookSrc).toContain('if (!mountedRef.current || next == null) return')
  })

  it('the visibilitychange listener is added exactly once, paired with exactly one removal', () => {
    expect(hookSrc.split("addEventListener('visibilitychange'").length - 1).toBe(1)
    expect(hookSrc.split("removeEventListener('visibilitychange'").length - 1).toBe(1)
  })
})
