import React from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { EVENT_STREAM_STATE } from '../context/operationalEventsReducer'

// React StrictMode (development) mounts, unmounts and remounts effects. The
// first stream is aborted by the cleanup; the remount must still open a live
// stream. Previously the connect guard stayed set, the remount's connect()
// was skipped and the status chip stayed on RECONNECTING forever.
const opened = []
vi.mock('../api/operationalEventsApi', () => ({
  OPERATIONAL_EVENTS_FETCH_STATUS: { NETWORK_ERROR: 'NETWORK_ERROR' },
  openOperationalEventStream: vi.fn(({ signal, onReady }) => new Promise((resolve, reject) => {
    const stream = { signal, onReady }
    opened.push(stream)
    signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })))
    // Like the real backend: `ready` arrives shortly after connecting.
    setTimeout(() => { if (!signal.aborted) onReady({ transport: 'push' }) }, 0)
  })),
}))
vi.mock('../api/operationalApi', () => ({
  readAuthToken: () => 'test-token',
  hasTokenDisappeared: () => false,
}))

const { useVerifiedClinicalEvents } = await import('../context/useVerifiedClinicalEvents')

describe('useVerifiedClinicalEvents under React StrictMode', () => {
  it('reconnects after the StrictMode remount and reaches CONNECTED (never stuck connecting)', async () => {
    const { result } = renderHook(() => useVerifiedClinicalEvents(), { wrapper: React.StrictMode })
    await waitFor(() => expect(result.current.state).toBe(EVENT_STREAM_STATE.CONNECTED))
    expect(result.current.transportMode).toBe('push')
    // One stream aborted by the StrictMode cleanup, exactly one live stream.
    expect(opened.filter((s) => !s.signal.aborted)).toHaveLength(1)
  })
})
