// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useSpatialTimeline } from '../context/useSpatialTimeline'
import { useStClusters } from '../context/useStClusters'
import { useEnvironmentObservations } from '../context/useEnvironmentObservations'

// FICTIONAL responses only. Each request resolves only when the test says so,
// so the "still loading the new scope" window can be observed.
function deferredFetch() {
  const pending = []
  global.fetch = vi.fn((url) => new Promise((resolve) => pending.push({ url: String(url), resolve })))
  return {
    pending,
    respond(index, body) {
      pending[index].resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    },
  }
}

afterEach(() => { vi.restoreAllMocks() })

describe('scope changes never show another scope\'s results', () => {
  it('spatial timeline: changing district or disease clears the previous snapshot while loading', async () => {
    const net = deferredFetch()
    const { result, rerender } = renderHook((props) => useSpatialTimeline(props), { initialProps: { disease: 'LSD', scope: 'district', district: 'Matara', asOf: '2026-08-31' } })
    net.respond(0, { status: 'OK', scope: { district: 'Matara' }, frames: [] })
    await waitFor(() => expect(result.current.data?.scope?.district).toBe('Matara'))

    rerender({ disease: 'LSD', scope: 'district', district: 'Galle', asOf: '2026-08-31' })
    await waitFor(() => expect(result.current.status).toBe('loading'))
    expect(result.current.data).toBeNull() // never Matara's zones under Galle's label

    rerender({ disease: 'FMD', scope: 'district', district: 'Galle', asOf: '2026-08-31' })
    expect(result.current.data).toBeNull()
    expect(net.pending.at(-1).url).toMatch(/disease=fmd.*district=Galle|district=Galle.*disease=fmd/)
  })

  it('spatial timeline: a same-scope refresh keeps the current snapshot (no flicker)', async () => {
    const net = deferredFetch()
    const { result, rerender } = renderHook((props) => useSpatialTimeline(props), { initialProps: { disease: 'LSD', scope: 'district', district: 'Matara', asOf: null, refreshToken: 0 } })
    net.respond(0, { status: 'OK', scope: { district: 'Matara' }, frames: [] })
    await waitFor(() => expect(result.current.data?.scope?.district).toBe('Matara'))
    rerender({ disease: 'LSD', scope: 'district', district: 'Matara', asOf: null, refreshToken: 1 })
    await waitFor(() => expect(result.current.status).toBe('loading'))
    expect(result.current.data?.scope?.district).toBe('Matara')
  })

  it('clusters and environment: a new disease/date/district clears old values while loading', async () => {
    const net = deferredFetch()
    const clusters = renderHook((props) => useStClusters(props), { initialProps: { disease: 'LSD', asOf: '2026-08-31', enabled: true } })
    net.respond(0, { cluster_count: 1, clusters: [], noise_locations: [] })
    await waitFor(() => expect(clusters.result.current.data?.cluster_count).toBe(1))
    clusters.rerender({ disease: 'FMD', asOf: '2026-08-31', enabled: true })
    await waitFor(() => expect(clusters.result.current.status).toBe('loading'))
    expect(clusters.result.current.data).toBeNull()

    const env = renderHook((props) => useEnvironmentObservations(props), { initialProps: { disease: 'LSD', district: 'Matara', asOf: '2026-08-31', enabled: true } })
    net.respond(net.pending.length - 1, { observations: [{ grid_cell: { latitude: 6, longitude: 80.5 } }] })
    await waitFor(() => expect(env.result.current.data?.observations).toHaveLength(1))
    env.rerender({ disease: 'LSD', district: 'Galle', asOf: '2026-08-31', enabled: true })
    await waitFor(() => expect(env.result.current.status).toBe('loading'))
    expect(env.result.current.data).toBeNull() // never Matara's weather for Galle
    expect(net.pending.at(-1).url).toContain('district=Galle')
  })
})
