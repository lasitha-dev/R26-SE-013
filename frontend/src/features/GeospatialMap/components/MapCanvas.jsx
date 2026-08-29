import React, { useMemo, useState } from 'react'
import CellDetailPanel from './CellDetailPanel'
import MapLegend from './MapLegend'
import { arrowTipOffset, shouldDrawArrow } from './directionGeometry'
import { NEUTRAL_SINGLE_COLOR, UNAVAILABLE_RISK_COLOR, computeRiskColorStats } from './mapLibreAdapter'
import { computeBounds, lonLatFromFeature, project } from './mapProjection'

/**
 * Checkpoint 11B Part 19: this is now the DEGRADED-MODE fallback,
 * rendered by `MapView.jsx` when MapLibre is unavailable (no WebGL /
 * style load failure). Originally the 11A baseline map foundation --
 * kept dependency-free on purpose so it never depends on WebGL and can
 * never itself fail the way the primary map can.
 *
 * Coordinates are read verbatim as `[longitude, latitude]` (EPSG:4326,
 * RFC 7946) from `feature.geometry.coordinates` -- never reversed,
 * never unit-converted. Color derivation reuses the exact same
 * `computeRiskColorStats` used by the MapLibre path (`mapLibreAdapter.js`)
 * so the two rendering modes never disagree on risk-color semantics.
 */

const WIDTH = 640
const HEIGHT = 480
const PADDING = 24

function presentationColorForScore(score, stats) {
  if (score === null || score === undefined) return UNAVAILABLE_RISK_COLOR
  if (!stats.hasVariation) return NEUTRAL_SINGLE_COLOR
  const t = Math.max(0, Math.min(1, (score - stats.min) / (stats.max - stats.min)))
  const hue = 220 - t * 220 // blue (low) -> red (high), continuous, no thresholds
  return `hsl(${hue}, 70%, 50%)`
}

export default function MapCanvas({ cellFeatures, sourceFeatures }) {
  const [selectedCell, setSelectedCell] = useState(null)

  const allPoints = useMemo(() => {
    const cellPoints = cellFeatures.map(lonLatFromFeature)
    const sourcePoints = sourceFeatures.map(lonLatFromFeature)
    return [...cellPoints, ...sourcePoints]
  }, [cellFeatures, sourceFeatures])

  const bounds = useMemo(() => computeBounds(allPoints), [allPoints])
  const stats = useMemo(() => computeRiskColorStats(cellFeatures), [cellFeatures])

  if (!bounds) {
    return <div className="flex h-[480px] items-center justify-center text-sm text-gray-500">No geometry to display.</div>
  }

  return (
    <div>
      <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-auto w-full max-w-full rounded border bg-slate-50">
        {cellFeatures.map((feature) => {
          const [lon, lat] = lonLatFromFeature(feature)
          const [x, y] = project(lon, lat, bounds, WIDTH, HEIGHT, PADDING)
          const score = feature.properties.risk.raw_c0_score
          const bearing = feature.properties.direction.bearing_deg
          const color = presentationColorForScore(score, stats)
          const showArrow = shouldDrawArrow(bearing)
          const offset = arrowTipOffset(bearing, 8)
          const cellId = feature.properties.scientific_cell_id
          return (
            <g
              key={cellId}
              role="button"
              tabIndex={0}
              aria-label={`Scientific cell ${cellId}`}
              onClick={() => setSelectedCell(feature)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setSelectedCell(feature)
              }}
              style={{ cursor: 'pointer' }}
            >
              <circle cx={x} cy={y} r={3} fill={color} stroke="#1e293b" strokeWidth={0.5} />
              {showArrow && <line x1={x} y1={y} x2={x + offset.dx} y2={y + offset.dy} stroke="#1e293b" strokeWidth={1} />}
            </g>
          )
        })}
        {sourceFeatures.map((feature) => {
          const [lon, lat] = lonLatFromFeature(feature)
          const [x, y] = project(lon, lat, bounds, WIDTH, HEIGHT, PADDING)
          return (
            <rect
              key={feature.properties.source_id}
              x={x - 4}
              y={y - 4}
              width={8}
              height={8}
              fill="#f59e0b"
              stroke="#1e293b"
              strokeWidth={0.75}
            />
          )
        })}
      </svg>
      <MapLegend stats={stats} />
      <CellDetailPanel cell={selectedCell} />
    </div>
  )
}
