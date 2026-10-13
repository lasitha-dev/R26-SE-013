import React, { useState } from 'react'

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
  { width = 640, height = 300, paddingLeft = 34, paddingTop = 14, paddingBottom = 32, paddingRight = 12 } = {},
) {
  const safePoints = Array.isArray(points) ? points : []
  const innerWidth = Math.max(width - paddingLeft - paddingRight, 1)
  const innerHeight = Math.max(height - paddingTop - paddingBottom, 1)
  const maxCount = safePoints.reduce((max, p) => Math.max(max, p.count), 0)
  const n = safePoints.length
  const slotWidth = n > 0 ? innerWidth / n : innerWidth
  const barWidth = Math.max(Math.min(slotWidth * 0.6, 48), 2)

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

  // Three evenly spaced horizontal reference lines (0%, 50%, 100% of the
  // real maximum) -- pure axis scaffolding deterministically derived from
  // the already-loaded `maxCount`, never a new/fabricated data value.
  const gridLines = [0, 0.5, 1].map((frac) => ({
    y: paddingTop + innerHeight * (1 - frac),
    value: frac === 1 ? maxCount : Math.round(maxCount * frac),
  }))

  return { width, height, paddingLeft, paddingTop, paddingRight, innerWidth, innerHeight, maxCount, bars, labelEvery, gridLines }
}

const TOOLTIP_WIDTH = 112
const TOOLTIP_HEIGHT = 36

export default function AnalysisTrendsChart({ points, periodBasis, reduceMotion = false }) {
  const [hoveredIndex, setHoveredIndex] = useState(null)
  const safePoints = Array.isArray(points) ? points : []
  const geometry = buildTrendChartGeometry(safePoints)
  const hoveredBar = hoveredIndex !== null ? geometry.bars[hoveredIndex] ?? null : null

  const summary =
    safePoints.length === 0
      ? 'No historical trend data available.'
      : `Historical trend, ${periodBasis ?? 'unknown'} basis, ${safePoints.length} periods from ${safePoints[0].period} to ${safePoints[safePoints.length - 1].period}, maximum ${geometry.maxCount} historical source records in one period.`

  const tooltipX = hoveredBar
    ? Math.min(
        Math.max(hoveredBar.labelX - TOOLTIP_WIDTH / 2, geometry.paddingLeft),
        geometry.width - geometry.paddingRight - TOOLTIP_WIDTH,
      )
    : 0
  const tooltipY = hoveredBar ? Math.max(hoveredBar.y - TOOLTIP_HEIGHT - 8, 2) : 0

  return (
    <div className="w-full">
      <svg
        role="img"
        aria-label={summary}
        viewBox={`0 0 ${geometry.width} ${geometry.height}`}
        className="w-full"
        style={{ maxHeight: 340 }}
      >
        {geometry.gridLines.map((line, i) => (
          <line
            key={`grid-${i}`}
            x1={geometry.paddingLeft}
            y1={line.y}
            x2={geometry.width - geometry.paddingRight}
            y2={line.y}
            stroke={i === 0 ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.06)'}
            strokeWidth="1"
          />
        ))}
        {geometry.gridLines.map((line, i) =>
          i === 0 || geometry.maxCount > 0 ? (
            <text key={`grid-label-${i}`} x={4} y={line.y + 3} className="fill-slate-500" fontSize="9">
              {line.value}
            </text>
          ) : null,
        )}
        {geometry.bars.map((bar, i) => (
          <g
            key={bar.period}
            onMouseEnter={() => setHoveredIndex(i)}
            onMouseLeave={() => setHoveredIndex((cur) => (cur === i ? null : cur))}
          >
            {/* Enlarged, invisible hit area so a short/zero bar is still easy to hover precisely. */}
            <rect x={bar.x - 2} y={geometry.paddingTop} width={bar.width + 4} height={geometry.innerHeight} fill="transparent" />
            <rect
              x={bar.x}
              y={bar.height === 0 ? geometry.paddingTop + geometry.innerHeight - 1 : bar.y}
              width={bar.width}
              height={bar.height === 0 ? 1 : bar.height}
              rx={2}
              fill={bar.count > 0 ? 'rgba(52,211,153,0.75)' : 'rgba(148,163,184,0.35)'}
              className={reduceMotion ? undefined : 'transition-[height,y] duration-300 ease-out'}
            />
            {i % geometry.labelEvery === 0 && (
              <text x={bar.labelX} y={geometry.height - 8} textAnchor="middle" className="fill-slate-500" fontSize="8">
                {formatTrendPeriodLabel(bar.period, periodBasis)}
              </text>
            )}
          </g>
        ))}
        {hoveredBar && (
          <g pointerEvents="none">
            <rect
              x={tooltipX}
              y={tooltipY}
              width={TOOLTIP_WIDTH}
              height={TOOLTIP_HEIGHT}
              rx={6}
              fill="rgba(2,6,23,0.95)"
              stroke="rgba(255,255,255,0.12)"
            />
            <text x={tooltipX + 8} y={tooltipY + 14} fontSize="9" className="fill-slate-400">
              {formatTrendPeriodLabel(hoveredBar.period, periodBasis)}
            </text>
            <text x={tooltipX + 8} y={tooltipY + 27} fontSize="10" fontWeight="600" className="fill-white">
              {hoveredBar.count} {hoveredBar.count === 1 ? 'record' : 'records'}
            </text>
          </g>
        )}
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
