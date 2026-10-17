// @vitest-environment jsdom
// Live updates when a case arrives (FICTIONAL records, mocked backend):
// the eligible-source signature, the duplicate-request guard, session
// isolation of the timeline, and the My Area page refetching its timeline
// on a new verified case without losing the selected day.
import { act, cleanup, render, renderHook, screen, waitFor, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { eligibleSourceSignature } from '../adapters/liveSourceSignature'
import { useSourceChangeToken } from '../context/useSourceChangeToken'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const realDistrictsText = readFileSync(join(FEATURE_ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8')
const json = (body) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))

const record = (key, extra = {}) => ({
  record_key: key, disease: 'LSD', verification_status: 'VERIFIED', location_status: 'VALID', latitude: 6.05, longitude: 80.52,
  verified_at: '2026-10-10T03:30:00+00:00', reported_at: '2026-10-10T03:00:00+00:00', district: 'Matara', ...extra,
})

describe('eligible-source signature', () => {
  const base = [record('R1')]
  it('changes only for records that can be sources', () => {
    const s0 = eligibleSourceSignature(base, 'LSD')
    expect(eligibleSourceSignature([...base, record('R2', { verification_status: 'PENDING_VERIFICATION' })], 'LSD')).toBe(s0)
    expect(eligibleSourceSignature([...base, record('R3', { location_status: 'LOCATION_REQUIRED', latitude: null, longitude: null })], 'LSD')).toBe(s0)
    expect(eligibleSourceSignature([...base, record('R4', { disease: 'FMD' })], 'LSD')).toBe(s0)
    expect(eligibleSourceSignature([...base, record('R5', { latitude: 6.06, longitude: 80.55 })], 'LSD')).not.toBe(s0) // new verified GPS case
    expect(eligibleSourceSignature([record('R1', { latitude: 6.051 })], 'LSD')).not.toBe(s0) // farm GPS moved
    expect(eligibleSourceSignature([], 'LSD')).toBe('0:811c9dc5')
    expect(eligibleSourceSignature(null, 'LSD')).toBe('')
  })

  it('the first load is not a change; a later different signature is', () => {
    const { result, rerender } = renderHook(({ s }) => useSourceChangeToken(s), { initialProps: { s: '' } })
    expect(result.current).toBe(0)
    rerender({ s: '1:aaa' })
    expect(result.current).toBe(0) // records arrived: no extra request
    rerender({ s: '1:aaa' })
    expect(result.current).toBe(0)
    rerender({ s: '2:bbb' })
    expect(result.current).toBe(1) // a new eligible case
  })
})

describe('timeline hook keeps sessions apart', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); window.localStorage.clear() })
  it('another signed-in vet never sees the previous snapshot and triggers a new request', async () => {
    const { useSpatialTimeline } = await import('../context/useSpatialTimeline')
    const { AUTH_TOKEN_STORAGE_KEY } = await import('../api/operationalApi')
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'fictional-token-vet-a')
    global.fetch = vi.fn(() => json(mataraTimeline))
    const { result, rerender } = renderHook(() => useSpatialTimeline({ disease: 'LSD', scope: 'district', district: 'Matara' }))
    await waitFor(() => expect(result.current.data).toBeTruthy())
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'fictional-token-vet-b')
    rerender()
    expect(result.current.data).toBeNull() // hidden at once, before the new response
    await waitFor(() => expect(result.current.data).toBeTruthy())
    expect(global.fetch.mock.calls.filter(([u]) => String(u).includes('/spatial-timeline'))).toHaveLength(2)
  })
})

describe('My Area refreshes on a new verified case and keeps the selected day', () => {
  let GeospatialProvider
  let MyAreaPage
  beforeAll(async () => {
    if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
    ;({ GeospatialProvider } = await import('../context/GeospatialContext'))
    MyAreaPage = (await import('../pages/MyAreaPage')).default
  })
  afterEach(() => { cleanup(); vi.restoreAllMocks(); window.localStorage.clear() })

  it('a pending report does not refetch; a new verified GPS case does, on the same selected day', async () => {
    window.localStorage.setItem('token', 'fictional-signed-in-vet') // a signed-in session (the heartbeat needs one)
    let records = [record('R1')]
    global.fetch = vi.fn((url) => {
      const target = String(url)
      if (target.includes('sri-lanka-districts-adm2')) return Promise.resolve(new Response(realDistrictsText, { status: 200 }))
      if (target.includes('/operational-context')) {
        return json({ status: 'NO_ASSIGNED_FARMS', vet: { role: 'vet' }, farms: [], clinical_contexts: [], vet_district: 'Matara', surveillance_farms: [], surveillance_contexts: [], surveillance_status: 'DISTRICT_RESOLVED' })
      }
      if (target.includes('/national-cases')) return json({ records, summary: {} })
      if (target.includes('/spatial-timeline')) return json(mataraTimeline)
      return Promise.reject(new Error(`unmocked request in test: ${target}`))
    })
    const timelineCalls = () => global.fetch.mock.calls.filter(([u]) => String(u).includes('/spatial-timeline')).length
    const caseCalls = () => global.fetch.mock.calls.filter(([u]) => String(u).includes('/national-cases')).length
    render(<MemoryRouter><GeospatialProvider><MyAreaPage /></GeospatialProvider></MemoryRouter>)
    const chart = await screen.findByRole('group', { name: /share of the district coloured by the risk surface/ })
    expect(within(chart).getAllByRole('button')).toHaveLength(15)
    await waitFor(() => expect(caseCalls()).toBeGreaterThan(0))
    act(() => { screen.getByRole('button', { name: 'Select 20 Oct 2026' }).click() })
    expect(await screen.findByText('8 of 15 · Day 7')).toBeTruthy()
    expect(timelineCalls()).toBe(1)

    // The records are re-polled on the heartbeat at most every 15 s (or at once on a live
    // event); move the clock 16 s ahead instead of waiting.
    const realNow = Date.now.bind(Date)
    let offset = 0
    vi.spyOn(Date, 'now').mockImplementation(() => realNow() + offset)

    // A pending report arrives: polled, but it can never be a source.
    records = [...records, record('R2', { verification_status: 'PENDING_VERIFICATION', latitude: 6.06, longitude: 80.55 })]
    const polled = caseCalls()
    offset += 16000
    await waitFor(() => expect(caseCalls()).toBeGreaterThan(polled), { timeout: 8000 })
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(timelineCalls()).toBe(1)

    // It is verified (with farm GPS): the timeline is fetched again, the day stays.
    records = records.map((r) => (r.record_key === 'R2' ? { ...r, verification_status: 'VERIFIED' } : r))
    offset += 16000
    await waitFor(() => expect(timelineCalls()).toBe(2), { timeout: 8000 })
    expect(screen.getByText('8 of 15 · Day 7')).toBeTruthy()
  }, 30000)
})
