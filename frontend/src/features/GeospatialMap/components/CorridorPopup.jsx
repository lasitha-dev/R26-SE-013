import React from 'react'

import { compassPoint, HORIZON_STATUS, horizonLabel } from '../adapters/spatialTimelineView'
import { formatDisplayDate } from '../adapters/forecastDate'
import { BAND_LABEL } from '../adapters/riskFieldModel'

function finite(value) {
  const number = value == null || value === '' ? Number.NaN : Number(value)
  return Number.isFinite(number) ? number : null
}

// Why a path ended (backend engine 3.0 `stop_reason`): the model's own limits.
const STOP_TEXT = {
  NEXT_STEP_OFF_LAND: 'Stopped: the next step would leave land. No point is placed at sea (model limit).',
  REACHED_25KM_LOCAL_DOMAIN: 'Stopped at 25 km: the area the model and its direction were evaluated in.',
  NO_DIRECTIONAL_EVIDENCE: 'Stopped: no directional evidence at this point.',
}
const NO_PATH_TEXT = {
  NO_DIRECTIONAL_EVIDENCE: 'Insufficient directional evidence: land, cattle, wind and nearby cases give no preferred direction here, so no path is drawn. Its risk is shown evenly around the farm.',
}
const WIND_SOURCE = { ERA5_REANALYSIS: 'ERA5 reanalysis', OPEN_METEO_FORECAST: 'forecast' }

function Row({ label, children, tone = 'text-on-surface' }) {
  return <div className="flex justify-between gap-2"><dt className="text-on-surface-variant/70">{label}</dt><dd className={`text-right ${tone}`}>{children}</dd></div>
}

/** The selected case's ST-DBSCAN result (`clusterForCase`), or a clear "none". */
function ClusterResult({ cluster }) {
  if (!cluster) return null
  let text
  if (cluster.status === 'loading') text = 'Loading space-time cluster result…'
  else if (cluster.status === 'member') text = `In a space-time cluster: ${cluster.memberCount} reports from ${cluster.supportCount} farms, ${cluster.startDate} to ${cluster.endDate}. Shown as group context, not as this case's forecast.`
  else if (cluster.status === 'noise') text = 'Not in any space-time cluster: no other farm reported within 12.37 km and 3 days.'
  else text = 'Space-time cluster result unavailable.'
  return (
    <div className="border-t border-outline-variant/20 px-3 py-2 text-[11px] leading-snug text-on-surface">
      <div className="font-semibold">Associated cluster (exploratory ST-DBSCAN)</div>
      <div className="text-on-surface-variant/85">{text}</div>
    </div>
  )
}

/** Details for one backend case path (`frames[d].source_paths[]`) or case
 * origin, for the selected day. Shows only backend values; `cluster` is the
 * selected case's ST-DBSCAN result, `risk` its farm on the day's risk raster.
 * `pinned` = opened by a click (stays until closed); otherwise a hover preview. */
export default function CorridorPopup({ corridor, cluster = null, risk = null, onClose, pinned = true }) {
  if (!corridor) return null
  const bearing = finite(corridor.bearingDeg)
  const length = finite(corridor.lengthKm)
  const nominal = finite(corridor.nominalReachKm)
  const displacement = finite(corridor.displacementKm)
  const low = finite(corridor.reachLowKm)
  const high = finite(corridor.reachHighKm)
  const day = finite(corridor.day)
  const nearby = finite(corridor.casesWithin25Km)
  const confidence = finite(corridor.confidence)
  const windToward = finite(corridor.windTowardDeg)
  const windWeight = finite(corridor.windWeight)
  const windSpeed = finite(corridor.windSpeedMs)
  const cattleHere = finite(corridor.cattleHere)
  const cattleAhead = finite(corridor.cattleAhead)
  const caseBearing = finite(corridor.caseBearingDeg)
  const caseShare = finite(corridor.caseShare)
  const domain = corridor.recordDomain === 'OPERATIONAL' ? 'Vet-verified case' : corridor.recordDomain === 'HISTORICAL' ? 'Historical record' : 'Source'
  const exploratory = corridor.horizonStatus === HORIZON_STATUS.EXPLORATORY
  const isPath = !corridor.isOrigin && bearing != null
  const reachText = day === 0 || length == null
    ? 'Starts on Day 1'
    : `${length.toFixed(1)} km${low != null && high != null ? ` (${low.toFixed(1)}–${high.toFixed(1)})` : ''}`
  return (
    <div
      className="pointer-events-auto w-80 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container/95 shadow-card-subtle"
      role="dialog"
      aria-label="Direction tendency details"
    >
      <div className="flex items-center justify-between border-b border-outline-variant/30 bg-surface-container-high/60 px-3 py-2">
        <div>
          <div className="font-mono text-xs uppercase tracking-wide text-violet-300">
            {isPath ? 'Modelled direction tendency' : 'Case origin'}
          </div>
          <div className="text-[11px] text-on-surface-variant/70">
            {day != null ? `Day ${day}` : 'Selected day'}
            {corridor.date ? ` · ${formatDisplayDate(corridor.date)}` : ''}
          </div>
        </div>
        {pinned ? (
          <button type="button" onClick={onClose} aria-label="Close" className="text-on-surface-variant/70 hover:text-on-surface">
            ×
          </button>
        ) : (
          <span className="text-[10px] text-on-surface-variant/55">Click to pin</span>
        )}
      </div>
      {isPath && (
        <div className="border-b border-violet-300/15 bg-violet-400/[0.06] px-3 py-2 text-sm font-semibold text-violet-200">
          Heading {compassPoint(bearing)} · {Math.round(bearing)}° today
          <span className="block text-[10px] font-normal text-on-surface-variant/70">Re-evaluated as the front moves, so it can change day by day</span>
        </div>
      )}
      <dl className="space-y-1 p-3 text-xs">
        <Row label="Source"><span className="block max-w-[11rem] truncate font-mono" title={corridor.sourceId}>{corridor.sourceId}</span></Row>
        {corridor.disease && <Row label="Disease">{corridor.disease}</Row>}
        <Row label="Type">{domain}</Row>
        {corridor.observationDate && <Row label="Observed">{formatDisplayDate(corridor.observationDate)}</Row>}
        {corridor.horizonStatus && <Row label="Status" tone={exploratory ? 'text-amber-200' : 'text-on-surface'}>{horizonLabel(corridor.horizonStatus)}</Row>}
        <Row label="Bearing">{bearing != null ? `${Math.round(bearing)}° ${compassPoint(bearing)}` : 'No directional tendency'}</Row>
        <Row label={isPath ? 'Distance along path' : 'Nominal reach'}>{reachText}</Row>
        {isPath && displacement != null && <Row label="Straight-line from farm">{displacement.toFixed(1)} km</Row>}
        {isPath && nominal != null && length != null && length + 0.05 < nominal && <Row label="Model reach today">{nominal.toFixed(1)} km</Row>}
        {risk && <Row label="Risk at the farm">{BAND_LABEL[risk.band]} · {risk.score.toFixed(2)}{risk.trend ? ` · ${risk.trend}` : ''} · {risk.contributingCount} case{risk.contributingCount === 1 ? '' : 's'}</Row>}
        {isPath && confidence != null && <Row label="Direction confidence">{Math.round(confidence * 100)}%</Row>}
        {isPath && (windToward != null
          ? <Row label="Net wind (this day)">toward {compassPoint(windToward)} · {Math.round((windWeight ?? 0) * 100)}% steady{windSpeed != null ? ` · ${(windSpeed * 3.6).toFixed(0)} km/h` : ''}{WIND_SOURCE[corridor.windKind] ? ` · ${WIND_SOURCE[corridor.windKind]}` : ''}</Row>
          : <Row label="Net wind (this day)">No data -- land, cattle and cases only</Row>)}
        {isPath && cattleAhead != null && <Row label="Cattle (here → ahead)">{cattleHere != null ? `${cattleHere.toFixed(0)} → ` : ''}{cattleAhead.toFixed(0)} /km²</Row>}
        {isPath && <Row label="Nearby cases">{caseBearing != null ? `push toward ${compassPoint(caseBearing)} (${Math.round((caseShare ?? 0) * 100)}%)` : 'none within 25 km'}{nearby != null ? ` · ${nearby} ≤ 25 km` : ''}</Row>}
        {isPath && corridor.heldAtCoast && <Row label="Today" tone="text-amber-200">Waited at the coast (no step over sea)</Row>}
      </dl>
      {corridor.stopReason && STOP_TEXT[corridor.stopReason] && <div className="border-t border-outline-variant/20 px-3 py-2 text-[11px] text-amber-200/90">{STOP_TEXT[corridor.stopReason]}</div>}
      {!isPath && corridor.noPathReason && <div className="border-t border-outline-variant/20 px-3 py-2 text-[11px] text-on-surface-variant/90">{NO_PATH_TEXT[corridor.noPathReason] ?? 'No individual trajectory for this case.'}</div>}
      <ClusterResult cluster={cluster} />
      <ul className="space-y-0.5 border-t border-outline-variant/20 px-3 py-2 text-[10.5px] leading-snug text-on-surface-variant/70">
        <li>Each day the heading is chosen from land ahead, cattle ahead (FAO GLW4), the day&apos;s net wind (sea and land breezes cancel) and the push of nearby verified cases away from where cases are dense (8B.3), then turned gradually; it moves at the evaluated 3.9 km/day. Wind and cattle are labelled extensions, not part of the validated model; rain and humidity are not used.</li>
        <li>An estimated spatial direction, not a confirmed route. &quot;Near&quot; a place does not mean an outbreak there. Nominal reach is a visualisation distance, not a disease boundary.</li>
        {exploratory && <li className="text-amber-200/80">Days 8–14 extend the Day 1–7 reach formula (exploratory).</li>}
      </ul>
    </div>
  )
}
