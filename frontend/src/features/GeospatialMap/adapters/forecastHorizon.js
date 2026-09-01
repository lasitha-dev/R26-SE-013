/**
 * PAGE-3-NATIONAL-KPI: derives the "Forecast Horizon" KPI from the real
 * `selected_origin_analytics.nominal_reach` block
 * (`analysisTrendsAdapter.js::normalizeNominalReach`) -- the only real
 * multi-day forecast data this application exposes. That block only
 * exists once a specific real origin is selected (this feature's own
 * "never auto-select an origin" rule), so a genuinely honest
 * `{ available: false }` state is returned until the veterinarian picks
 * one -- never a fabricated default like "D+14".
 */
export function deriveForecastHorizon(selectedOriginAnalytics) {
  if (!selectedOriginAnalytics) {
    return { available: false, days: null, note: 'Select a historical/model origin below to view forecast horizon.' }
  }

  if (selectedOriginAnalytics.status === 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY') {
    return { available: false, days: null, note: 'Scientific model is not ready for this disease.' }
  }

  const realDays = (selectedOriginAnalytics.nominalReach?.days ?? [])
    .filter((day) => typeof day.nominalReachKm === 'number')
    .map((day) => day.day)

  if (realDays.length === 0) {
    return { available: false, days: null, note: 'No forecast snapshot is available for the selected origin.' }
  }

  return {
    available: true,
    days: Math.max(...realDays),
    note: `Forecast snapshot for ${selectedOriginAnalytics.originId ?? 'the selected origin'}.`,
  }
}
