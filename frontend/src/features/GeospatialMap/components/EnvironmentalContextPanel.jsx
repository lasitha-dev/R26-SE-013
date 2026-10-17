import React from 'react'

const VARIABLE_LABEL = {
  temperature_2m: 'Air temperature (2 m)',
  dew_point_2m: 'Dew point (2 m)',
  relative_humidity_2m: 'Relative humidity (2 m)',
  precipitation: 'Rainfall',
  wind_speed_10m: 'Wind speed (10 m)',
  wind_direction_10m: 'Wind direction (10 m, from)',
}

const STATUS_TEXT = {
  NOT_INTEGRATED: 'Not integrated into the spatial model',
  INTEGRATED: 'Integrated',
}

/**
 * Environmental context exactly as the Spatial Timeline backend reports it
 * (`timeline.environment`). Today the backend states NOT_INTEGRATED and
 * returns no values (no evaluated environmental-influence model; ERA5 is
 * historical reanalysis with a publication lag; no forecast source), so
 * this shows the candidate variables, units and source -- never a
 * number the backend did not send.
 */
export default function EnvironmentalContextPanel({ environment, compact = false }) {
  if (!environment) {
    return <div className="text-[11px] text-on-surface-variant/70">Environmental status unavailable until the spatial timeline loads.</div>
  }
  const variables = Array.isArray(environment.candidate_variables) ? environment.candidate_variables : []
  const values = Array.isArray(environment.values) ? environment.values : []
  return (
    <div className="flex flex-col gap-2" aria-label="Environmental context">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-amber-400/35 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
          {STATUS_TEXT[environment.status] ?? environment.status ?? 'Status unknown'}
        </span>
        <span className="text-[10.5px] text-on-surface-variant">
          {environment.used_in_score ? 'Used in the relative score' : 'Not used in any score'}
        </span>
      </div>
      {environment.reason && <p className="text-[11px] leading-relaxed text-on-surface-variant/80">{environment.reason}</p>}
      {variables.length > 0 && (
        <table className="w-full text-left text-[10.5px]">
          <thead>
            <tr className="text-[9.5px] uppercase tracking-wide text-on-surface-variant/55">
              <th className="py-1 pr-2 font-semibold">Variable</th>
              {!compact && <th className="py-1 pr-2 font-semibold">Unit</th>}
              <th className="py-1 pr-2 font-semibold">Source</th>
              <th className="py-1 font-semibold">Value</th>
            </tr>
          </thead>
          <tbody>
            {variables.map((v) => {
              const reported = values.find((x) => x?.name === v.name)
              return (
                <tr key={v.name} className="border-t border-outline-variant/15">
                  <td className="py-1 pr-2 text-on-surface">{VARIABLE_LABEL[v.name] ?? v.name}</td>
                  {!compact && <td className="py-1 pr-2 font-mono text-on-surface-variant">{v.unit}</td>}
                  <td className="py-1 pr-2 text-on-surface-variant">{v.kind === 'REANALYSIS' ? 'ERA5 reanalysis (historical)' : v.source}</td>
                  <td className="py-1 text-on-surface-variant/70">{reported && Number.isFinite(reported.value) ? `${reported.value} ${v.unit}` : 'Not reported'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      <p className="text-[9.5px] leading-relaxed text-on-surface-variant/50">
        Historical reanalysis is never shown as current or forecast weather, and wind is never presented as a disease-movement route.
      </p>
    </div>
  )
}
