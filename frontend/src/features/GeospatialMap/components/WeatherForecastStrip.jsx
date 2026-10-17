import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import { compassPoint } from '../adapters/spatialTimelineView'
import { CONDITION_ICON, CONDITION_LABEL, FORECAST_PROVIDER, HEAT_START_C, heatIntensity } from '../adapters/weatherForecast'

const CHIP_TONE = {
  RAIN: 'text-sky-300', STORM: 'text-indigo-300', WINDY: 'text-cyan-300', CLOUDY: 'text-slate-300', SUNNY: 'text-amber-300',
}

const range = (min, max, digits, unit) => (Number.isFinite(min) && Number.isFinite(max) && max - min >= 10 ** -digits ? `${min.toFixed(digits)}–${max.toFixed(digits)}${unit} across the district` : null)

function retrievedLabel(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleTimeString('en-GB', { timeZone: 'Asia/Colombo', hour: '2-digit', minute: '2-digit' })
  } catch {
    return null
  }
}

/** One weather value as an icon tile: icon, label, value and an optional note. */
function WeatherTile({ icon, tone, label, value, note = null, children = null }) {
  return (
    <div className="flex min-w-0 items-start gap-2 rounded-lg border border-white/5 bg-white/[0.03] px-2 py-1.5">
      <span className={`material-symbols-outlined mt-0.5 text-[18px] ${tone}`} aria-hidden="true">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="text-[9.5px] uppercase tracking-wide text-slate-400">{label}</div>
        <div className="flex items-center gap-1 font-mono text-[12.5px] font-semibold text-slate-100">{value}{children}</div>
        {note && <div className="truncate text-[9px] text-slate-500" title={note}>{note}</div>}
      </div>
    </div>
  )
}

/**
 * Weather along the timeline: one chip per timeline date (forecast for today
 * onward; earlier dates show "observed" and use ERA5 below) and icon tiles for
 * the selected date. `areaLabel` names what the forecast covers -- the
 * district (mean of points inside it) or a point the vet clicked on the map
 * (`pointMode`, `onClearPoint` returns to the district). Display only -- not
 * part of the C0 relative score.
 */
export default function WeatherForecastStrip({
  showSourceNote = true,
  district, areaLabel = null, pointMode = false, onClearPoint = null,
  dates = [], selectedDate, days, status, onSelectIndex = null, todayKey, fetchedAt = null, pointCount = 0,
}) {
  const selected = selectedDate ? days?.get(selectedDate) : null
  const title = areaLabel ?? district ?? 'your district'
  return (
    <div className="flex flex-col gap-2 text-[11px] text-slate-300" aria-label="Weather along the timeline">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1 font-semibold text-slate-100">
            <span className="material-symbols-outlined text-[15px] text-emerald-300" aria-hidden="true">{pointMode ? 'location_on' : 'map'}</span>
            <span className="truncate">Weather · {title}</span>
          </div>
          <div className="text-[9.5px] text-slate-400">
            {pointMode ? 'Forecast at the point you selected' : `District average · click the map for a point forecast`}
          </div>
        </div>
        {pointMode && onClearPoint ? (
          <button type="button" onClick={onClearPoint} className="shrink-0 rounded-full border border-white/15 px-2 py-0.5 text-[9.5px] text-slate-200 hover:border-emerald-400/60">
            District average
          </button>
        ) : (
          <span className="shrink-0 text-[9.5px] text-amber-200">Not in the risk score</span>
        )}
      </div>
      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${Math.max(1, dates.length)}, minmax(0, 1fr))` }}>
        {dates.map((date, index) => {
          const day = days?.get(date)
          const active = date === selectedDate
          const past = todayKey && date < todayKey
          return (
            <button
              key={date}
              type="button"
              onClick={() => onSelectIndex?.(index)}
              title={day ? `${formatDisplayDate(date)} · ${CONDITION_LABEL[day.condition]}` : `${formatDisplayDate(date)} · ${past ? 'observed (ERA5)' : 'no forecast'}`}
              className={`flex min-w-0 flex-col items-center rounded-md border px-0.5 py-1 ${active ? 'border-emerald-400/70 bg-emerald-400/10' : 'border-white/5 bg-white/[0.02] hover:border-white/20'}`}
            >
              <span className={`material-symbols-outlined text-[16px] ${day ? CHIP_TONE[day.condition] : 'text-slate-600'}`} aria-hidden="true">{day ? CONDITION_ICON[day.condition] : past ? 'history' : 'remove'}</span>
              <span className="text-[8.5px] font-semibold text-slate-400">{String(date).slice(8, 10)}</span>
              <span className="text-[8px] leading-none text-sky-300" title="Rain (mm)">{day && day.rainMm !== null ? Math.round(day.rainMm) : ' '}</span>
            </button>
          )
        })}
      </div>
      {selected ? (
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2">
          <div className="mb-1.5 flex items-center gap-1.5 font-semibold text-slate-100">
            <span className={`material-symbols-outlined text-[20px] ${CHIP_TONE[selected.condition]}`} aria-hidden="true">{CONDITION_ICON[selected.condition]}</span>
            <span>{formatDisplayDate(selected.date)} · {CONDITION_LABEL[selected.condition]}</span>
            {heatIntensity(selected) > 0 && (
              <span className="ml-auto flex items-center gap-0.5 rounded-full border border-orange-400/50 bg-orange-500/15 px-1.5 py-0.5 text-[9.5px] font-bold text-orange-200" title={`Under 1 mm of rain and a high of ${HEAT_START_C} °C or more`}>
                <span className="material-symbols-outlined text-[13px]" aria-hidden="true">local_fire_department</span>Hot &amp; dry
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <WeatherTile icon="water_drop" tone="text-sky-300" label="Rain (24 h)"
              value={selected.rainMm !== null ? `${selected.rainMm.toFixed(1)} mm` : '—'}
              note={pointMode ? null : range(selected.rainMinMm, selected.rainMaxMm, 1, ' mm')} />
            <WeatherTile icon="umbrella" tone="text-indigo-300" label="Rain chance"
              value={selected.rainChance !== null ? `${selected.rainChance}%` : '—'} note={selected.rainChance !== null ? 'highest in the day' : null} />
            <WeatherTile icon="device_thermostat" tone="text-amber-300" label="Temperature"
              value={selected.tempMin !== null && selected.tempMax !== null ? `${selected.tempMin.toFixed(0)}–${selected.tempMax.toFixed(0)} °C` : selected.tempMax !== null ? `max ${selected.tempMax.toFixed(0)} °C` : '—'}
              note="night low – day high" />
            <WeatherTile icon="humidity_percentage" tone="text-cyan-300" label="Humidity"
              value={Number.isFinite(selected.humidityPct) ? `${Math.round(selected.humidityPct)}%` : '—'} note={Number.isFinite(selected.humidityPct) ? 'daily mean' : null} />
            <div className="col-span-2">
              <WeatherTile icon="air" tone="text-teal-300" label="Wind"
                value={selected.windKmh !== null ? `${Math.round(selected.windKmh)} km/h` : '—'}
                note={selected.windFromDeg !== null ? `highest hourly wind · blowing from the ${compassPoint(selected.windFromDeg)}, toward the ${compassPoint((selected.windFromDeg + 180) % 360)}` : null}>
                {selected.windFromDeg !== null && (
                  // Arrow points where the air moves (downwind).
                  <span className="material-symbols-outlined ml-1 text-[16px] text-teal-300" style={{ transform: `rotate(${(selected.windFromDeg + 180) % 360}deg)` }} aria-label={`toward ${compassPoint((selected.windFromDeg + 180) % 360)}`}>navigation</span>
                )}
              </WeatherTile>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-[10.5px] text-slate-400">
          {status === 'loading' ? 'Loading the forecast…'
            : status === 'error' ? 'Forecast unavailable right now (provider or network). Nothing is substituted.'
              : selectedDate && todayKey && selectedDate < todayKey ? 'Past date: observed ERA5 weather (district reference point) is shown below.'
                : 'No forecast for this date (the forecast covers today to 15 days ahead).'}
        </p>
      )}
      {showSourceNote && <p className="text-[9px] text-slate-500">
        {FORECAST_PROVIDER} (model grid ≈10 km, today onward){pointMode ? ': the grid cell at the selected point' : pointCount > 1 ? `: mean of ${pointCount} points inside ${district ?? 'the district'}` : ': one point in the district'}. Daily values for the Asia/Colombo day; not farm-level weather.{retrievedLabel(fetchedAt) ? ` Retrieved ${retrievedLabel(fetchedAt)}.` : ''} Past dates: ERA5 reanalysis (observed) from the ADRS backend.
      </p>}
    </div>
  )
}
