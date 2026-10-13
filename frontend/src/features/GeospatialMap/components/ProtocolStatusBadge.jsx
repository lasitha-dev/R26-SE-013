import React from 'react'
import { PHASE } from '../state/snapshotAssembly'
import { DISCLAIMER_RUNTIME_MODE } from '../semanticLabels'

const BADGE_STYLE = {
  [PHASE.PROTOCOL_CHECKING]: 'bg-gray-200 text-gray-800',
  [PHASE.PROTOCOL_READY]: 'bg-green-100 text-green-800',
  [PHASE.INCOMPATIBLE_BACKEND_PROTOCOL]: 'bg-red-100 text-red-800',
  [PHASE.ERROR]: 'bg-red-100 text-red-800',
}

export default function ProtocolStatusBadge({ phase, protocol, error }) {
  const style = BADGE_STYLE[phase] || 'bg-gray-100 text-gray-600'
  return (
    <div className={`rounded px-3 py-2 text-sm ${style}`}>
      <div className="font-semibold">{phase.replaceAll('_', ' ')}</div>
      {protocol && (
        <div className="mt-1 text-xs opacity-80">
          runtime_data_mode: {protocol.runtime_data_mode} · live_operational_analysis_status: {protocol.live_operational_analysis_status}
        </div>
      )}
      {error && <div className="mt-1 text-xs">{error.message}</div>}
      <div className="mt-1 text-xs italic opacity-80">{DISCLAIMER_RUNTIME_MODE}</div>
    </div>
  )
}
