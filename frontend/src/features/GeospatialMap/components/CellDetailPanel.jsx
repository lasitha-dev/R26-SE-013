import React from 'react'

/**
 * Checkpoint 11B Part 12: shared cell-inspection panel, used by both
 * the MapLibre view and the dependency-free SVG fallback so the "at
 * minimum" required field list is defined exactly once. Presentation
 * only -- values are read and displayed verbatim from the backend
 * feature, never rounded-then-overwritten in storage (only the
 * DISPLAYED text may be formatted).
 */
export default function CellDetailPanel({ cell }) {
  if (!cell) return null
  const { risk, direction, scientific_cell_id: cellId } = cell.properties
  const [lon, lat] = cell.geometry.coordinates

  return (
    <div className="mt-2 rounded border bg-white p-2 text-sm">
      <div className="font-semibold">{cellId}</div>
      <div className="text-xs text-gray-500">
        lon: {lon}, lat: {lat}
      </div>
      <div>raw_c0_score: {risk.raw_c0_score === null || risk.raw_c0_score === undefined ? 'unavailable' : risk.raw_c0_score}</div>
      <div>score_status: {risk.score_status}</div>
      <div>semantics: {risk.semantics}</div>
      <div>
        bearing_deg:{' '}
        {direction.bearing_deg === null || direction.bearing_deg === undefined ? 'null (undefined direction)' : direction.bearing_deg}
      </div>
      <div>directional_clarity: {direction.directional_clarity ?? 'null'}</div>
      {direction.directional_input_coverage !== undefined && <div>directional_input_coverage: {direction.directional_input_coverage ?? 'null'}</div>}
      <div>direction_status: {direction.direction_status}</div>
      {direction.direction_semantics !== undefined && <div>direction_semantics: {direction.direction_semantics}</div>}
    </div>
  )
}
