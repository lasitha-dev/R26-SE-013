import React from 'react'

import CellDetailPanel from './CellDetailPanel'
import { LABEL_CELL_POPUP_DAY_PREFIX, LABEL_CELL_POPUP_TITLE } from '../semanticLabels'

/**
 * GEO26B Section 32: fixes the previous no-op cell click (it only called
 * `console.debug`) by giving `OutbreakMapPage.jsx` a real, closeable
 * popup for the clicked risk cell -- reusing `CellDetailPanel.jsx`
 * (already the shared, tested field list for a cell's real
 * `raw_c0_score`/`score_status`/`semantics`/`bearing_deg`/
 * `directional_clarity`/`direction_status`) rather than a second,
 * divergent rendering of the same fields. Adds only a header stating
 * which real forecast day/date the cell belongs to and a close control --
 * both presentation-only, no new scientific field is introduced.
 */
export default function CellPopup({ cell, dayIndex, dayDate, onClose }) {
  if (!cell) return null

  return (
    <div className="pointer-events-auto w-64 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container/95 shadow-card-subtle">
      <div className="flex items-center justify-between border-b border-outline-variant/30 bg-surface-container-high/60 px-3 py-2">
        <div>
          <div className="font-mono text-xs uppercase tracking-wide text-blue-300">{LABEL_CELL_POPUP_TITLE}</div>
          {typeof dayIndex === 'number' && (
            <div className="text-[11px] text-on-surface-variant/70">
              {LABEL_CELL_POPUP_DAY_PREFIX} D{dayIndex === 0 ? '0' : `+${dayIndex}`}
              {dayDate ? ` · ${dayDate}` : ''}
            </div>
          )}
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-on-surface-variant/70 hover:text-on-surface">
          ×
        </button>
      </div>
      <div className="max-h-64 overflow-auto p-1">
        <CellDetailPanel cell={cell} />
      </div>
    </div>
  )
}
