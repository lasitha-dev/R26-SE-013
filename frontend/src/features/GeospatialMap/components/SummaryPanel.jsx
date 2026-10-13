import React from 'react'
import {
  DISCLAIMER_CLARITY,
  DISCLAIMER_DIRECTION,
  DISCLAIMER_RATE,
  DISCLAIMER_REACH,
  DISCLAIMER_RISK,
  LABEL_REACH,
} from '../semanticLabels'

/**
 * Checkpoint 11A Part 16: rate/reach/risk shown verbatim from the
 * backend `summary` payload -- no recomputation, no clipping of D7 to
 * the 25km envelope.
 */
export default function SummaryPanel({ summary }) {
  if (!summary) return null
  const rate = summary.apparent_rate_context
  const reach = summary.nominal_reach_by_day

  return (
    <div className="space-y-3 text-sm">
      <section>
        <h3 className="font-semibold">Risk</h3>
        <p className="text-xs italic text-gray-600">{DISCLAIMER_RISK}</p>
        <p className="text-xs italic text-gray-600">{DISCLAIMER_DIRECTION}</p>
        <p className="text-xs italic text-gray-600">{DISCLAIMER_CLARITY}</p>
      </section>

      <section>
        <h3 className="font-semibold">{rate.apparent_rate_label}</h3>
        <p>
          {rate.apparent_rate_km_day} km/day (95% interval: [{rate.rate_interval_lower_km_day}, {rate.rate_interval_upper_km_day}])
        </p>
        <p className="text-xs text-gray-600">status: {rate.rate_status} · scope: {rate.rate_scope}</p>
        <p className="text-xs text-gray-600">{rate.conditioning_limitation}</p>
        <p className="text-xs italic text-gray-600">{DISCLAIMER_RATE}</p>
      </section>

      <section>
        <h3 className="font-semibold">{LABEL_REACH}</h3>
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left">Day</th>
              <th className="text-left">Nominal reach (km)</th>
            </tr>
          </thead>
          <tbody>
            {reach.map((d) => (
              <tr key={d.day}>
                <td>D{d.day}</td>
                <td>{d.nominal_reach_km}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs italic text-gray-600">{DISCLAIMER_REACH}</p>
        <p className="text-xs text-gray-600">operational_evaluation_envelope_km: {summary.operational_evaluation_envelope_km}</p>
      </section>
    </div>
  )
}
