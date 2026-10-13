import React from 'react'
import {
  DISCLAIMER_CLARITY,
  DISCLAIMER_DIRECTION,
  DISCLAIMER_RISK,
  LABEL_RISK_SCORE,
  PRESENTATION_ONLY_COLOR_SCALE,
} from '../semanticLabels'
import { NEUTRAL_SINGLE_COLOR, UNAVAILABLE_RISK_COLOR } from './mapLibreAdapter'

/**
 * Checkpoint 11B Part 14/18: a compact, textual legend -- every layer
 * is identified by a WORD, not only by color/shape, so color is never
 * the sole carrier of scientific meaning. Cross-snapshot color
 * incomparability (Part 8) is stated explicitly whenever a gradient is
 * shown.
 */
export default function MapLegend({ stats }) {
  return (
    <div className="mt-2 space-y-1 rounded border bg-white p-2 text-xs text-gray-700">
      <div className="flex flex-wrap items-center gap-3">
        <span>
          <span aria-hidden="true" className="mr-1 inline-block h-2 w-2 rounded-full border border-slate-700 bg-blue-500 align-middle" />
          Scientific cells
        </span>
        <span>
          <span aria-hidden="true" className="mr-1 inline-block h-2 w-2 border border-slate-700 bg-amber-500 align-middle" />
          Eligible outbreak sources
        </span>
        <span>
          <span aria-hidden="true" className="mr-1 inline-block align-middle">
            ➤
          </span>
          Direction arrow (C0-derived local geometric tendency)
        </span>
      </div>

      <div>
        <span className="font-medium">{LABEL_RISK_SCORE}</span> ({PRESENTATION_ONLY_COLOR_SCALE}):{' '}
        {stats.allUnavailable ? (
          <span>
            all cells <span style={{ color: UNAVAILABLE_RISK_COLOR }}>unavailable</span> in this snapshot
          </span>
        ) : !stats.hasVariation ? (
          <span>
            all valid scores equal -- one neutral color (<span style={{ color: NEUTRAL_SINGLE_COLOR }}>&#9679;</span>), no gradient available in this
            snapshot
          </span>
        ) : (
          <span>
            low <span className="text-blue-500">&#9679;</span> &rarr; high <span className="text-red-600">&#9679;</span> (range {stats.min} to{' '}
            {stats.max} in THIS snapshot only)
          </span>
        )}
        {stats.hasUnavailable && (
          <span>
            {' '}
            &middot; <span style={{ color: UNAVAILABLE_RISK_COLOR }}>unavailable</span> = score not computed for that cell, never rendered as low risk
          </span>
        )}
      </div>
      <div className="italic text-gray-500">
        Color is normalized within the current snapshot for visualization only. Colors are not directly comparable between different snapshots.
      </div>

      <div className="italic text-gray-500">{DISCLAIMER_RISK}</div>
      <div className="italic text-gray-500">{DISCLAIMER_DIRECTION}</div>
      <div className="italic text-gray-500">{DISCLAIMER_CLARITY}</div>
    </div>
  )
}
