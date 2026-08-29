import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * GEO-OWNED-FINAL-08 Section 17: re-proves, on the FRONTEND side, the same
 * scientific-non-mutation guarantee the backend already locks with
 * `test_operational_structural_ownership.py`/
 * `test_operational_events_structural_ownership.py` (no foreign-component
 * import, no scientific-write-capable import). The operational/clinical
 * boundary files listed below must never import a historical-outbreak,
 * forecast-origin, or model-run module, and must never call a
 * camera/scientific-recomputation primitive that would let a clinical-case
 * event fabricate or move scientific state.
 *
 * Deliberately excludes `OutbreakMapPage.jsx`/`MyAreaPage.jsx` themselves --
 * those pages are the legitimate ORCHESTRATORS that combine both universes
 * (already covered by `verifiedClinicalEventsWiring.test.js`'s handler-body
 * checks); this file is about the operational boundary's OWN modules never
 * reaching into the historical/model side on their own.
 */

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

// Mirrors `visualLayerStructural.test.js`'s own comment-stripping
// convention: a comment that legitimately DOCUMENTS a forbidden token
// (e.g. explaining what this module deliberately does NOT import) must
// never false-positive a plain substring scan the same way real code
// would -- strip comments first, then scan.
function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
}

function readSourceWithoutComments(relativePath) {
  return stripComments(readFileSync(join(FEATURE_ROOT, relativePath), 'utf-8'))
}

const OPERATIONAL_BOUNDARY_FILES = [
  'api/operationalApi.js',
  'api/operationalEventsApi.js',
  'adapters/operationalContextAdapter.js',
  'adapters/operationalEventRelevance.js',
  'adapters/alertMessageAdapter.js',
  'context/operationalRefreshReducer.js',
  'context/operationalEventsReducer.js',
  'context/useOperationalContext.js',
  'context/useVerifiedClinicalEvents.js',
  'components/operationalIcons.js',
  'components/operationalMarkerLayer.js',
  'components/OperationalStatusChip.jsx',
  'components/OperationalContextPopup.jsx',
  'components/GeospatialAlertBanner.jsx',
]

const FORBIDDEN_HISTORICAL_MODEL_IMPORTS = [
  'useNationalOutbreaks',
  'useSelectedOutbreakFrames',
  'useFmdOriginRisk',
  'useAnalysisTrends',
  'useDiseaseOriginLedger',
  'lsdOutbreakAdapter',
  'fmdOutbreakAdapter',
  'analysisTrendsAdapter',
  'outbreakSelectionReducer',
  'GeospatialContext',
]

const FORBIDDEN_CAMERA_OR_SCIENTIFIC_CALLS = [
  'fitBounds(',
  'flyTo(',
  'easeTo(',
  'setAvailableFrames(',
  'selectOutbreak(',
  'ctx.play(',
  'ctx.pause(',
]

describe('GEO-OWNED-FINAL-08 Section 17: operational boundary files never import historical/model modules', () => {
  for (const relativePath of OPERATIONAL_BOUNDARY_FILES) {
    it(`${relativePath} imports nothing historical/model-owning`, () => {
      const src = readSourceWithoutComments(relativePath)
      for (const forbidden of FORBIDDEN_HISTORICAL_MODEL_IMPORTS) {
        expect(src.includes(forbidden), `${relativePath} references "${forbidden}"`).toBe(false)
      }
    })
  }
})

describe('GEO-OWNED-FINAL-08 Section 17: operational boundary files never move the camera or mutate scientific/outbreak state', () => {
  for (const relativePath of OPERATIONAL_BOUNDARY_FILES) {
    it(`${relativePath} calls no camera/scientific-recomputation primitive`, () => {
      const src = readSourceWithoutComments(relativePath)
      for (const forbidden of FORBIDDEN_CAMERA_OR_SCIENTIFIC_CALLS) {
        expect(src.includes(forbidden), `${relativePath} calls "${forbidden}"`).toBe(false)
      }
    })
  }
})

describe('GEO-OWNED-FINAL-08 Section 11: identity firewall -- case_id is never conflated with outbreak/origin/model-run ids', () => {
  it('operationalContextAdapter.js and alertMessageAdapter.js never reference outbreak/origin/model-run identity fields', () => {
    for (const relativePath of ['adapters/operationalContextAdapter.js', 'adapters/alertMessageAdapter.js']) {
      const src = readSourceWithoutComments(relativePath)
      for (const forbidden of ['selectedOutbreakId', 'outbreak_id', 'origin_id', 'originId', 'model_run_id', 'modelRunId']) {
        expect(src.includes(forbidden), `${relativePath} references "${forbidden}"`).toBe(false)
      }
    }
  })

  it('the deep-link/event identity fields stay to case_id/farm_id/disease -- no naked cross-domain id reuse', () => {
    const src = readSourceWithoutComments('adapters/alertMessageAdapter.js')
    expect(src).toContain('event.farm_id')
    expect(src).not.toContain('event.outbreak_id')
    expect(src).not.toContain('event.origin_id')
  })
})
