/**
 * Checkpoint 11A Part 15: pure, framework-independent direction-arrow
 * geometry -- extracted from `MapCanvas.jsx` so the null-vs-0.0 bearing
 * rule is unit-testable without rendering.
 *
 * `0.0` is a VALID bearing (true North) and must never be treated the
 * same as "no direction" -- callers must use `bearing !== null &&
 * bearing !== undefined`, never a bare truthiness check like
 * `if (bearing)` (which would incorrectly treat 0.0 as falsy).
 */
export function shouldDrawArrow(bearingDeg) {
  return bearingDeg !== null && bearingDeg !== undefined
}

/** Arrow tip offset from (x, y) for a given bearing (compass degrees,
 * 0 = North, clockwise) and screen-space arrow length. */
export function arrowTipOffset(bearingDeg, length) {
  if (!shouldDrawArrow(bearingDeg)) return null
  const rad = (bearingDeg * Math.PI) / 180
  return { dx: Math.sin(rad) * length, dy: -Math.cos(rad) * length }
}
