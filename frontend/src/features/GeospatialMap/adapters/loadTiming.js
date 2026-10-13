/**
 * GEO33B Section 1: DEV-ONLY load-timing instrumentation for Page 1's
 * Cases-mode foundation.
 *
 * Why this module exists: every "the map feels slow" / "markers appear
 * late" report so far has been a subjective browser observation with no
 * numbers behind it. This records real `performance.mark()` timestamps at
 * the exact lifecycle boundaries that matter (page mount, MapLibre
 * construction, style load, first tile render, each real API fetch, source
 * creation, first `setData`, first outbreak render, map idle) so the owner
 * can read ACTUAL milliseconds out of a real browser session instead of
 * guessing.
 *
 * Hard rules this module follows:
 *  - It is a NO-OP outside dev (`import.meta.env.DEV`). No mark, no
 *    measure, no console output, no retained array in a production build --
 *    `isTimingEnabled()` short-circuits before any work happens, so this
 *    can never change production behavior or bundle-time cost beyond a
 *    handful of dead branches.
 *  - It NEVER participates in rendering decisions. Nothing in this feature
 *    reads a timing value back to decide what to draw; these are
 *    write-only diagnostics.
 *  - It measures presentation/transport timing only -- it never touches,
 *    derives, or reports a scientific value.
 *  - No `setTimeout`/`setInterval` (this feature's `noAutoPolling.test.js`
 *    forbids both tokens repo-wide); the summary is emitted by the caller
 *    at a real lifecycle event (`map.on('idle')`), never on a timer.
 */

/** Every mark name this feature records, so a reader has one list to look
 * at rather than hunting string literals across three files. */
export const GEO_TIMING = {
  PAGE_MOUNT: 'geo33b:page-mount',
  MAP_CONSTRUCT_START: 'geo33b:map-construct-start',
  MAP_CONSTRUCT_END: 'geo33b:map-construct-end',
  STYLE_LOAD_START: 'geo33b:style-load-start',
  STYLE_LOAD_END: 'geo33b:style-load-end',
  FIRST_RENDER: 'geo33b:first-tile-render',
  SOURCES_CREATED: 'geo33b:sources-created',
  NATIONAL_FETCH_START: 'geo33b:national-fetch-start',
  NATIONAL_FETCH_END: 'geo33b:national-fetch-end',
  OPERATIONAL_FETCH_START: 'geo33b:operational-fetch-start',
  OPERATIONAL_FETCH_END: 'geo33b:operational-fetch-end',
  DISTRICT_FETCH_START: 'geo33b:district-fetch-start',
  DISTRICT_FETCH_END: 'geo33b:district-fetch-end',
  FIRST_SET_DATA: 'geo33b:first-set-data',
  FIRST_OUTBREAK_RENDER: 'geo33b:first-outbreak-render',
  MAP_IDLE: 'geo33b:map-idle',
  // GEO-VIVA-USER-VISIBLE-RECOVERY-05: per-INTERACTION marks (all
  // `{ repeat: true }` at their call sites, unlike the once-per-page-load
  // marks above) -- these exist purely so a real QA session can measure
  // "click to actual map reaction" against `performance.getEntriesByName`
  // for a Disease/Location/Window change AFTER initial page load, not just
  // the first paint. Same dev-only/write-only/no-scientific-value rules as
  // every other mark in this module.
  NATIONAL_SOURCES_SET_DATA: 'geo33b:national-sources-set-data',
  NATIONAL_ALL_SETTLED: 'geo33b:national-all-settled',
  CAMERA_FIT_START: 'geo33b:camera-fit-start',
  CAMERA_FIT_END: 'geo33b:camera-fit-end',
  OPERATIONAL_MARKERS_SET_DATA: 'geo33b:operational-markers-set-data',
}

function devEnabled() {
  try {
    return Boolean(import.meta.env?.DEV)
  } catch {
    return false
  }
}

const ENABLED = devEnabled()

/** Exported so a caller can skip building a label/object it would only
 * throw away in production. */
export function isTimingEnabled() {
  return ENABLED && typeof performance !== 'undefined' && typeof performance.mark === 'function'
}

/** Ordered record of every mark actually taken this session, kept only in
 * dev. `performance.mark` itself is also called so the marks show up in
 * the browser's own Performance panel/timeline, not just here. */
const recorded = []
const seen = new Set()

/**
 * Records `name` once per page session. Repeated calls for a "first X"
 * boundary (e.g. the first `setData`, which runs again on every later
 * refresh) are ignored, so the recorded value always means "the FIRST
 * time this happened" -- never silently overwritten by a later refresh.
 * Pass `{ repeat: true }` for a boundary that legitimately recurs.
 */
export function markTiming(name, { repeat = false } = {}) {
  if (!isTimingEnabled()) return
  if (!repeat && seen.has(name)) return
  seen.add(name)
  const at = performance.now()
  recorded.push({ name, at })
  try {
    performance.mark(name)
  } catch {
    // A browser that refuses a duplicate/invalid mark name must never
    // break the page -- the in-memory record above is the primary output.
  }
}

/** Milliseconds between two already-recorded marks, or `null` when either
 * one genuinely never happened (never a fabricated 0). */
export function durationBetween(startName, endName) {
  const start = recorded.find((m) => m.name === startName)
  const end = recorded.find((m) => m.name === endName)
  if (!start || !end) return null
  return Math.round((end.at - start.at) * 10) / 10
}

/** The checkpoint's own named intervals, computed from real marks only.
 * A missing mark yields `null` (honest "did not happen"), never 0. */
export function buildTimingSummary() {
  const { PAGE_MOUNT } = GEO_TIMING
  return {
    GEO33B_PAGE_TO_STYLE_LOAD_MS: durationBetween(PAGE_MOUNT, GEO_TIMING.STYLE_LOAD_END),
    GEO33B_STYLE_TO_FIRST_TILE_MS: durationBetween(GEO_TIMING.STYLE_LOAD_END, GEO_TIMING.FIRST_RENDER),
    GEO33B_PAGE_TO_NATIONAL_DATA_MS: durationBetween(PAGE_MOUNT, GEO_TIMING.NATIONAL_FETCH_END),
    GEO33B_PAGE_TO_OPERATIONAL_DATA_MS: durationBetween(PAGE_MOUNT, GEO_TIMING.OPERATIONAL_FETCH_END),
    GEO33B_PAGE_TO_FIRST_OUTBREAK_MS: durationBetween(PAGE_MOUNT, GEO_TIMING.FIRST_OUTBREAK_RENDER),
    GEO33B_PAGE_TO_MAP_IDLE_MS: durationBetween(PAGE_MOUNT, GEO_TIMING.MAP_IDLE),
    GEO33B_MAP_CONSTRUCT_MS: durationBetween(GEO_TIMING.MAP_CONSTRUCT_START, GEO_TIMING.MAP_CONSTRUCT_END),
  }
}

/** Every raw mark, in the real order they happened, relative to page mount
 * (or to the first mark taken, if page mount was somehow never recorded). */
export function timingMarks() {
  if (recorded.length === 0) return []
  const base = recorded.find((m) => m.name === GEO_TIMING.PAGE_MOUNT)?.at ?? recorded[0].at
  return recorded.map((m) => ({ mark: m.name, msSincePageMount: Math.round((m.at - base) * 10) / 10 }))
}

/**
 * Prints the full picture once, at a real lifecycle event the caller
 * chooses (`map.on('idle')`). Dev-only and idempotent -- a later idle
 * event never re-prints, so this can be wired to a recurring map event
 * without spamming the console.
 */
let summaryLogged = false
export function logTimingSummary(label = 'GEO33B load timing') {
  if (!isTimingEnabled() || summaryLogged) return
  summaryLogged = true
  const summary = buildTimingSummary()
  /* eslint-disable no-console */
  console.groupCollapsed?.(`[${label}] real measured milliseconds (dev only)`)
  console.table?.(timingMarks())
  console.table?.(summary)
  console.groupEnd?.()
  /* eslint-enable no-console */
}

/** Test/diagnostic escape hatch -- lets a caller re-arm the one-shot
 * summary (e.g. a client-side route change back onto this page). */
export function resetTimingSummaryGuard() {
  summaryLogged = false
}
