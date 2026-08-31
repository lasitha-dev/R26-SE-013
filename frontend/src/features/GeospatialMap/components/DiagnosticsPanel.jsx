import React from 'react'
import { GENERATED_AT_LABEL } from '../semanticLabels'

/**
 * Checkpoint 11A Part 17: small, non-dominant developer/research
 * diagnostics section. `generated_at_utc` is explicitly labeled as
 * process-generation time, never "data last updated"/"data freshness"/
 * "live data time" -- and cache status (not shown here) is never
 * presented as scientific freshness.
 */
export default function DiagnosticsPanel({ metadata, snapshotId, generatedAtUtc }) {
  if (!metadata) return null
  return (
    <details className="rounded border bg-gray-50 p-2 text-xs text-gray-600">
      <summary className="cursor-pointer font-medium">Transport diagnostics</summary>
      <div className="mt-1 space-y-0.5">
        <div>snapshot_id: {snapshotId}</div>
        <div>
          {GENERATED_AT_LABEL}: {generatedAtUtc}
        </div>
        <div>runtime_data_mode: {metadata.runtime_data_mode}</div>
        <div>live_operational_analysis_status: {metadata.live_operational_analysis_status}</div>
      </div>
    </details>
  )
}
