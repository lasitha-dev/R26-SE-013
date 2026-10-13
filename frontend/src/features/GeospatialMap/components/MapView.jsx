import React, { useState } from 'react'
import { BASEMAP_MODE_REMOTE_STYLE, resolveBasemapConfig } from './basemapConfig'
import CellDetailPanel from './CellDetailPanel'
import MapCanvas from './MapCanvas'
import MapLegend from './MapLegend'
import MapLibreCanvas from './MapLibreCanvas'
import { computeRiskColorStats } from './mapLibreAdapter'

export const MAP_STATUS_MAPLIBRE_AVAILABLE = 'MAPLIBRE_AVAILABLE'
export const MAP_STATUS_VISUAL_MAP_UNAVAILABLE = 'VISUAL_MAP_UNAVAILABLE_SNAPSHOT_DATA_PRESERVED'

/**
 * Checkpoint 11B Part 4/19: consumes ONLY the already-committed
 * snapshot (`state.currentCommittedSnapshot`) -- never the reducer's
 * in-flight assembly buffer, never a second fetching architecture. If
 * MapLibre cannot render (no WebGL / style load failure), this falls
 * back to the dependency-free SVG view WITHOUT ever classifying the
 * scientific snapshot itself as unavailable
 * (`VISUAL_MAP_UNAVAILABLE_SNAPSHOT_DATA_PRESERVED` -- a presentation
 * failure -- is a distinct concept from the backend's own analysis-
 * unavailable statuses).
 */
export default function MapView({ snapshot }) {
  const [mapStatus, setMapStatus] = useState(MAP_STATUS_MAPLIBRE_AVAILABLE)
  const [selectedCell, setSelectedCell] = useState(null)

  const basemap = resolveBasemapConfig(import.meta.env.VITE_GEOSPATIAL_BASEMAP_STYLE_URL)

  if (mapStatus === MAP_STATUS_VISUAL_MAP_UNAVAILABLE) {
    return (
      <div>
        <div className="mb-2 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
          The interactive map could not be rendered in this browser. The scientific snapshot data below is unaffected and remains fully inspectable
          in the fallback view.
        </div>
        <MapCanvas cellFeatures={snapshot.cells} sourceFeatures={snapshot.sources.features} />
      </div>
    )
  }

  const stats = computeRiskColorStats(snapshot.cells)

  return (
    <div>
      <MapLibreCanvas
        key={snapshot.snapshotId}
        cellFeatures={snapshot.cells}
        sourceFeatures={snapshot.sources.features}
        onSelectCell={setSelectedCell}
        onMapUnavailable={() => setMapStatus(MAP_STATUS_VISUAL_MAP_UNAVAILABLE)}
      />
      <div className="mt-1 text-xs text-gray-500">
        {basemap.mode === BASEMAP_MODE_REMOTE_STYLE ? 'Basemap: external style (see attribution control on map).' : 'Basemap: neutral, token-free background (no remote style configured).'}{' '}
        {basemap.note}
      </div>
      <MapLegend stats={stats} />
      <CellDetailPanel cell={selectedCell} />
    </div>
  )
}
