import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DISEASE_CODE } from '../disease/diseaseRegistry'

/**
 * GEO-VISUAL-POLISH-02 Section 1/2: the honest per-stage resolution
 * counts this hook now exposes (`expectedOriginCount`,
 * `expectedSourceRecordCount`, `resolvedOriginCount`,
 * `failedOriginCount`). The real, reported backend defect this hook's own
 * module docstring documents -- one real per-origin geometry request can
 * take >30s while the others resolve in under a second -- is reproduced
 * here directly: N real origins, one of which never resolves in-window,
 * proving already-resolved origins stay visible and the failure is
 * counted honestly rather than silently discarded or fabricated as
 * "rendered".
 */
vi.mock('../api/geospatialApi', () => ({
  fetchOrigins: vi.fn(),
  fetchAnalysisSources: vi.fn(),
  fetchOriginTriggerSources: vi.fn(),
}))

const { fetchOrigins, fetchAnalysisSources } = await import('../api/geospatialApi')
const { useNationalOutbreaks, NATIONAL_STATUS } = await import('../context/useNationalOutbreaks')

function origin(id, t0, sourceCount = 1) {
  return { forecast_origin_id: id, country: 'Sri Lanka', t0, trigger_source_count: sourceCount }
}

function featureCollection(n) {
  return {
    type: 'FeatureCollection',
    features: Array.from({ length: n }, (_, i) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [80 + i, 8 + i] },
      properties: { source_id: `S${i}` },
    })),
  }
}

describe('GEO-VISUAL-POLISH-02: useNationalOutbreaks resolution-stage counts', () => {
  it('stage A/B are known as soon as the lightweight /origins response resolves -- before any geometry settles', async () => {
    fetchOrigins.mockResolvedValue({
      origins: [origin('O1', '2026-08-01', 1), origin('O2', '2026-08-02', 2)],
      n_origins: 2,
    })
    // Geometry never resolves within this test -- irrelevant here, only
    // the origins-list stage is being asserted.
    fetchAnalysisSources.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useNationalOutbreaks(DISEASE_CODE.LSD, 'Sri Lanka'))

    await waitFor(() => {
      expect(result.current.expectedOriginCount).toBe(2)
    })
    // trigger_source_count 1 + 2 = 3 real underlying source records.
    expect(result.current.expectedSourceRecordCount).toBe(3)
    expect(result.current.resolvedOriginCount).toBe(0)
    expect(result.current.failedOriginCount).toBe(0)
  })

  it('one real origin failing (the documented slow/serialized-handler defect) is counted, never silently dropped -- and never blocks the others from resolving/rendering', async () => {
    fetchOrigins.mockResolvedValue({
      origins: [origin('O1', '2026-08-01'), origin('O2', '2026-08-02'), origin('O3', '2026-08-03')],
      n_origins: 3,
    })
    fetchAnalysisSources.mockImplementation((outbreakId) => {
      if (outbreakId === 'O2') return Promise.reject(new Error('simulated real backend timeout'))
      return Promise.resolve(featureCollection(1))
    })

    const { result } = renderHook(() => useNationalOutbreaks(DISEASE_CODE.LSD, 'Sri Lanka'))

    await waitFor(() => {
      expect(result.current.status).toBe(NATIONAL_STATUS.READY)
    })

    expect(result.current.expectedOriginCount).toBe(3)
    expect(result.current.resolvedOriginCount).toBe(2)
    expect(result.current.failedOriginCount).toBe(1)
    // The failed origin is genuinely absent -- never a fabricated entry
    // standing in for it.
    expect(result.current.originsWithSources.map((o) => o.outbreakId).sort()).toEqual(['O1', 'O3'])
  })

  it('every origin resolving successfully leaves failedOriginCount at zero and resolvedOriginCount equal to expectedOriginCount', async () => {
    fetchOrigins.mockResolvedValue({
      origins: [origin('O1', '2026-08-01'), origin('O2', '2026-08-02')],
      n_origins: 2,
    })
    fetchAnalysisSources.mockResolvedValue(featureCollection(1))

    const { result } = renderHook(() => useNationalOutbreaks(DISEASE_CODE.LSD, 'Sri Lanka'))

    await waitFor(() => {
      expect(result.current.status).toBe(NATIONAL_STATUS.READY)
    })
    expect(result.current.expectedOriginCount).toBe(2)
    expect(result.current.resolvedOriginCount).toBe(2)
    expect(result.current.failedOriginCount).toBe(0)
  })

  it('zero real origins for this disease/country is an honest all-zero result, never a fabricated non-zero count', async () => {
    fetchOrigins.mockResolvedValue({ origins: [], n_origins: 0 })

    const { result } = renderHook(() => useNationalOutbreaks(DISEASE_CODE.LSD, 'Sri Lanka'))

    await waitFor(() => {
      expect(result.current.status).toBe(NATIONAL_STATUS.EMPTY)
    })
    expect(result.current.expectedOriginCount).toBe(0)
    expect(result.current.expectedSourceRecordCount).toBe(0)
    expect(result.current.resolvedOriginCount).toBe(0)
    expect(result.current.failedOriginCount).toBe(0)
  })

  it('a total /origins fetch failure reports an honest all-zero resolution state alongside the ERROR status', async () => {
    fetchOrigins.mockRejectedValue(new Error('network unavailable'))

    const { result } = renderHook(() => useNationalOutbreaks(DISEASE_CODE.LSD, 'Sri Lanka'))

    await waitFor(() => {
      expect(result.current.status).toBe(NATIONAL_STATUS.ERROR)
    })
    expect(result.current.expectedOriginCount).toBe(0)
    expect(result.current.resolvedOriginCount).toBe(0)
    expect(result.current.failedOriginCount).toBe(0)
  })
})
