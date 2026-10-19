import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NATIONAL_CASES_STATE, useNationalCases } from '../context/useNationalCases'
import { SPATIAL_TIMELINE_STATE, useSpatialTimeline } from '../context/useSpatialTimeline'

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
const fail = (status = 502) => Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) })

afterEach(() => vi.unstubAllGlobals())

describe('a failed refresh never wipes good data or gives up', () => {
  it('national cases: a failed refresh keeps the last records (stale) and flags the error', async () => {
    const records = [{ record_key: 'CASE:1', disease: 'LSD' }]
    const fetchMock = vi.fn().mockReturnValueOnce(ok({ records })).mockReturnValueOnce(fail(502)).mockReturnValueOnce(ok({ records }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useNationalCases())
    await waitFor(() => expect(result.current.status).toBe(NATIONAL_CASES_STATE.READY))
    await act(async () => { result.current.refresh() })
    await waitFor(() => expect(result.current.status).toBe(NATIONAL_CASES_STATE.ERROR))
    expect(result.current.data.records).toEqual(records) // markers stay on the map
    await act(async () => { result.current.refresh() })
    await waitFor(() => expect(result.current.status).toBe(NATIONAL_CASES_STATE.READY))
  })

  it('spatial timeline: a network/5xx failure is retried on the next sync heartbeat', async () => {
    const snapshot = { status: 'NO_ELIGIBLE_SOURCES', frames: [], sources: [] }
    const fetchMock = vi.fn().mockReturnValueOnce(fail(502)).mockReturnValue(ok(snapshot))
    vi.stubGlobal('fetch', fetchMock)
    const { result, rerender } = renderHook((props) => useSpatialTimeline(props), { initialProps: { disease: 'lsd', scope: 'national', retryKey: 1 } })
    await waitFor(() => expect(result.current.status).toBe(SPATIAL_TIMELINE_STATE.ERROR))
    rerender({ disease: 'lsd', scope: 'national', retryKey: 2 }) // next heartbeat
    await waitFor(() => expect(result.current.status).toBe(SPATIAL_TIMELINE_STATE.READY))
    expect(fetchMock).toHaveBeenCalledTimes(2)
    rerender({ disease: 'lsd', scope: 'national', retryKey: 3 }) // healthy: no extra fetch
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
