import React from 'react'

/**
 * GEO-ANALYSIS-02 Section 18/20: attractive but honest SVG bar chart of
 * `historical_trend.points` -- deterministic geometry, no chart
 * dependency (pure `<svg>`), no invented curve fitting between points,
 * no random points. Bars (not a line) deliberately -- a connecting line
 * would visually suggest a continuous trend between sparse real points
 * (e.g. the real Sri Lanka LSD WEEK series or FMD YEAR series) that the
 * backend never asserts; every bar's height maps to exactly one real
 * `{period, count}` pair, independent of its neighbors.
 *
 * The period-label formatter below reads ONLY the string components
 * already present in `period` (`YYYY-Www` / `YYYY-MM` / `YYYY`) -- it
 * never re-derives a calendar date, never assumes a day-of-month, and
 * falls back to the raw backend string verbatim for any basis it does
 * not recognize (never guesses).
 */

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatTrendPeriodLabel(period, periodBasis) {
  if (typeof period !== 'string') return ''
  if (periodBasis === 'WEEK') {
    const match = /^(\d{4})-W(\d{2})$/.exec(period)
    if (!match) return period
    return `Wk ${match[2]} '${match[1].slice(2)}`
  }
  if (periodBasis === 'MONTH') {
    const match = /^(\d{4})-(\d{2})$/.exec(period)
    if (!match) return period
    const abbr = MONTH_ABBR[Number(match[2]) - 1] ?? match[2]
    return `${abbr} '${match[1].slice(2)}`
  }
  // YEAR, or any basis this component does not specifically recognize --
  // render the real backend string verbatim, never a guessed format.
  return period
}

/**
 * Pure geometry builder -- unit-testable without rendering. `points`
 * must already be the adapter-normalized, real, ordered list (bounded
 * zero-fill and ordering are entirely the backend's job, Section 19 --
 * this function never adds, removes, or reorders a period).
 */
export function buildTrendChartGeometry(
  points,
  { width = 640, height = 220, paddingLeft = 34, paddingTop = 12, paddingBottom = 28, paddingRight = 12 } = {},
) {
  const safePoints = Array.isArray(points) ? points : []
  const innerWidth = Math.max(width - paddingLeft - paddingRight, 1)
  const innerHeight = Math.max(height - paddingTop - paddingBottom, 1)
  const maxCount = safePoints.reduce((max, p) => Math.max(max, p.count), 0)
  const n = safePoints.length
  const slotWidth = n > 0 ? innerWidth / n : innerWidth
  const barWidth = Math.max(Math.min(slotWidth * 0.6, 40), 2)

  const bars = safePoints.map((p, i) => {
    const slotCenter = paddingLeft + slotWidth * (i + 0.5)
    const barHeight = maxCount > 0 ? (p.count / maxCount) * innerHeight : 0
    return {
      period: p.period,
      count: p.count,
      x: slotCenter - barWidth / 2,
      y: paddingTop + innerHeight - barHeight,
      width: barWidth,
      height: barHeight,
      labelX: slotCenter,
    }
  })

  // Thin x-axis text labels only (a rendering-density choice, never a
  // data change) so a long real series (e.g. FMD's 11 real years) does
  // not overflow into illegible overlapping text.
  const labelEvery = n > 14 ? Math.ceil(n / 10) : 1

  return { width, height, paddingLeft, paddingTop, innerWidth, innerHeight, maxCount, bars, labelEvery }
}

export default function AnalysisTrendsChart({ points, periodBasis, reduceMotion = false }) {
  const safePoints = Array.isArray(points) ? points : []
  const geometry = buildTrendChartGeometry(safePoints)
  const baselineY = geometry.paddingTop + geometry.innerHeight

  const summary =
    safePoints.length === 0
      ? 'No historical trend data available.'
      : `Historical trend, ${periodBasis ?? 'unknown'} basis, ${safePoints.length} periods from ${safePoints[0].period} to ${safePoints[safePoints.length - 1].period}, maximum ${geometry.maxCount} historical source records in one period.`

  return (
    <div className="w-full">
      <svg
        role="img"
        aria-label={summary}
        viewBox={`0 0 ${geometry.width} ${geometry.height}`}
        className="w-full"
        style={{ maxHeight: 260 }}
      >
        <line
          x1={geometry.paddingLeft}
          y1={baselineY}
          x2={geometry.width - 12}
          y2={baselineY}
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="1"
        />
        {geometry.maxCount > 0 && (
          <text x={4} y={geometry.paddingTop + 4} className="fill-slate-500" fontSize="9">
            {geometry.maxCount}
          </text>
        )}
        <text x={4} y={baselineY} className="fill-slate-500" fontSize="9">
          0
        </text>
        {geometry.bars.map((bar, i) => (
          <g key={bar.period}>
            <rect
              x={bar.x}
              y={bar.height === 0 ? baselineY - 1 : bar.y}
              width={bar.width}
              height={bar.height === 0 ? 1 : bar.height}
              rx={2}
              fill={bar.count > 0 ? 'rgba(52,211,153,0.75)' : 'rgba(148,163,184,0.35)'}
              className={reduceMotion ? undefined : 'transition-[height,y] duration-300 ease-out'}
            >
              <title>{`${bar.period}: ${bar.count} historical source record${bar.count === 1 ? '' : 's'}`}</title>
            </rect>
            {i % geometry.labelEvery === 0 && (
              <text x={bar.labelX} y={geometry.height - 8} textAnchor="middle" className="fill-slate-500" fontSize="8">
                {formatTrendPeriodLabel(bar.period, periodBasis)}
              </text>
            )}
          </g>
        ))}
      </svg>
      {/* Screen-reader-accessible full data table -- never relies on the
          SVG alone for the real values (Section 46). */}
      <table className="sr-only">
        <caption>Historical trend by {periodBasis ?? 'period'}</caption>
        <thead>
          <tr>
            <th>Period</th>
            <th>Historical source records</th>
          </tr>
        </thead>
        <tbody>
          {safePoints.map((p) => (
            <tr key={p.period}>
              <td>{p.period}</td>
              <td>{p.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
