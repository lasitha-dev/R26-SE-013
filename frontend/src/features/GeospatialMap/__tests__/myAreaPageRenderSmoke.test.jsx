import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import fmdNotReady from './fixtures/spatialTimeline.fmdNotReady.json'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'
import noSources from './fixtures/spatialTimeline.noSources.json'
import { formatDisplayDate } from '../adapters/forecastDate'

// The My Area 'Selected date' KPI shows the selected backend frame's date.
const kpiDate = (day) => formatDisplayDate(mataraTimeline.frames[day].date).toUpperCase()

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const realDistrictsText = readFileSync(join(FEATURE_ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8')

function jsonResponse(body) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
}

let GeospatialProvider
let MyAreaPage

function renderPage() {
  return render(
    // The app always mounts this page inside its router (App.jsx).
    <MemoryRouter>
      <GeospatialProvider>
        <MyAreaPage />
      </GeospatialProvider>
    </MemoryRouter>,
  )
}

describe('My Area renders for the logged-in vet district (mocked backend, no real database)', () => {
  // Same jsdom/maplibre-gl workaround as outbreakMapPageRenderSmoke.test.jsx: MapLibre calls
  // URL.createObjectURL at import time, so stub it and import the page afterwards.
  beforeAll(async () => {
    if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
    ;({ GeospatialProvider } = await import('../context/GeospatialContext'))
    MyAreaPage = (await import('../pages/MyAreaPage')).default
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('mounts without throwing on a total backend outage and never shows a fixed district', () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('network unavailable in test')))
    expect(() => renderPage()).not.toThrow()
    expect(screen.getByText('NOT RESOLVED')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/matara/i)
  })

  it("follows the vet's registered district from /operational-context (Galle, not Matara)", async () => {
    global.fetch = vi.fn((url) => {
      const target = String(url)
      if (target.includes('sri-lanka-districts-adm2')) return Promise.resolve(new Response(realDistrictsText, { status: 200 }))
      if (target.includes('/operational-context')) {
        return jsonResponse({
          status: 'NO_ASSIGNED_FARMS', vet: { role: 'vet' }, farms: [], clinical_contexts: [],
          vet_district: 'Galle', surveillance_farms: [], surveillance_contexts: [], surveillance_status: 'NO_FARMS_IN_DISTRICT',
          generated_at: '2026-10-13T00:00:00Z',
        })
      }
      return Promise.reject(new Error(`unmocked request in test: ${target}`))
    })
    renderPage()
    expect(await screen.findByText('GALLE')).toBeTruthy()
    expect(await screen.findByText('Future Impact - Galle')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/matara/i)
  })

  it('tells a vet with no registered district what to do instead of guessing one', async () => {
    global.fetch = vi.fn((url) => {
      const target = String(url)
      if (target.includes('sri-lanka-districts-adm2')) return Promise.resolve(new Response(realDistrictsText, { status: 200 }))
      if (target.includes('/operational-context')) {
        return jsonResponse({
          status: 'NO_ASSIGNED_FARMS', vet: { role: 'vet' }, farms: [], clinical_contexts: [],
          vet_district: null, surveillance_farms: [], surveillance_contexts: [], surveillance_status: 'NO_REGISTERED_DISTRICT',
        })
      }
      return Promise.reject(new Error(`unmocked request in test: ${target}`))
    })
    renderPage()
    expect(await screen.findByText(/No district is registered on your veterinarian profile/)).toBeTruthy()
    expect(screen.getByText('NOT RESOLVED')).toBeTruthy()
  })

  function mockBackend({ timeline, vetDistrict = 'Matara' }) {
    global.fetch = vi.fn((url) => {
      const target = String(url)
      if (target.includes('sri-lanka-districts-adm2')) return Promise.resolve(new Response(realDistrictsText, { status: 200 }))
      if (target.includes('/operational-context')) {
        return jsonResponse({
          status: 'NO_ASSIGNED_FARMS', vet: { role: 'vet' }, farms: [], clinical_contexts: [], vet_district: vetDistrict,
          surveillance_farms: [], surveillance_contexts: [], surveillance_status: 'DISTRICT_RESOLVED',
        })
      }
      if (target.includes('/spatial-timeline')) return jsonResponse(timeline)
      return Promise.reject(new Error(`unmocked request in test: ${target}`))
    })
  }

  const timelineCalls = () => global.fetch.mock.calls.filter(([url]) => String(url).includes('/spatial-timeline'))

  it('requests the district-scoped backend timeline once and shows its real dates (Phase 2 fixture, fictional farms)', async () => {
    mockBackend({ timeline: mataraTimeline })
    renderPage()
    expect(within(await screen.findByRole('group', { name: /share of the district coloured by the risk surface/ })).getAllByRole('button')).toHaveLength(15)
    const url = new URL(String(timelineCalls()[0][0]), 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toEqual({ disease: 'lsd', scope: 'district', district: 'Matara', horizon_days: '14' })
    // Selecting days only changes the frame index -- never a new request.
    screen.getByRole('button', { name: 'Select 20 Oct 2026' }).click()
    expect((await screen.findAllByText(kpiDate(7))).length).toBeGreaterThan(0)
    screen.getByRole('button', { name: 'Select 24 Oct 2026' }).click()
    expect((await screen.findAllByText(kpiDate(11))).length).toBeGreaterThan(0)
    expect(screen.getByText('12 of 15 · Day 11')).toBeTruthy() // the panel follows the selected frame
    expect(timelineCalls()).toHaveLength(1)
  })

  it('shows an honest notice when FMD has no validated spatial model', async () => {
    mockBackend({ timeline: fmdNotReady })
    renderPage()
    expect(await screen.findByText(/No validated spatial risk model for this disease/)).toBeTruthy()
  })

  // Phase 4: FICTIONAL operational context matching the fixture's two test farms.
  function mockBackendWithFictionalCases() {
    global.fetch = vi.fn((url) => {
      const target = String(url)
      if (target.includes('sri-lanka-districts-adm2')) return Promise.resolve(new Response(realDistrictsText, { status: 200 }))
      if (target.includes('/operational-context')) {
        return jsonResponse({
          status: 'OK', vet: { role: 'vet' }, farms: [], clinical_contexts: [], vet_district: 'Matara', surveillance_status: 'DISTRICT_RESOLVED',
          surveillance_farms: [
            { farm_id: 'TEST-FICTIONAL-FARM-1', latitude: 6.05, longitude: 80.52, location_status: 'VALID', location_district: 'Matara', total_animals: 12, personally_assigned: false },
            { farm_id: 'TEST-FICTIONAL-FARM-2', latitude: 6.1, longitude: 80.48, location_status: 'VALID', location_district: 'Matara', total_animals: 8, personally_assigned: false },
          ],
          surveillance_contexts: [
            { case_id: 'TEST-FICTIONAL-CASE-1', farm_id: 'TEST-FICTIONAL-FARM-1', disease: 'LSD', semantic_class: 'VERIFIED_CLINICAL_CONTEXT', verification_time: '2026-10-10 09:00:00', timestamp_basis: 'VERIFICATION_TIME' },
            { case_id: 'TEST-FICTIONAL-CASE-2', farm_id: 'TEST-FICTIONAL-FARM-2', disease: 'LSD', semantic_class: 'VERIFIED_CLINICAL_CONTEXT', verification_time: '2026-10-11 09:00:00', timestamp_basis: 'VERIFICATION_TIME' },
          ],
        })
      }
      if (target.includes('/spatial-timeline')) return jsonResponse(mataraTimeline)
      return Promise.reject(new Error(`unmocked request in test: ${target}`))
    })
  }

  it('Play advances frame by frame and stops on the last backend frame (no loop, no rewind)', async () => {
    mockBackend({ timeline: mataraTimeline })
    let clock = performance.now()
    const realRaf = window.requestAnimationFrame
    // Test-only clock: every animation frame is 2 s later, so each playback tick advances one frame.
    window.requestAnimationFrame = (cb) => setTimeout(() => { clock += 2000; cb(clock) }, 0)
    vi.spyOn(performance, 'now').mockImplementation(() => clock)
    try {
      renderPage()
      expect(within(await screen.findByRole('group', { name: /share of the district coloured by the risk surface/ })).getAllByRole('button')).toHaveLength(15)
      screen.getByRole('button', { name: 'Select 23 Oct 2026' }).click()
      expect((await screen.findAllByText(kpiDate(10))).length).toBeGreaterThan(0)
      screen.getByRole('button', { name: 'Play area forecast playback' }).click()
      expect((await screen.findAllByText(kpiDate(14), {}, { timeout: 4000 })).length).toBeGreaterThan(0)
      const done = await screen.findByRole('button', { name: 'Restart area forecast playback' })
      expect(done.disabled).toBe(false)
      expect(done.getAttribute('aria-pressed')).toBe('false')
      expect(screen.queryByRole('button', { name: 'Pause area forecast playback' })).toBeNull()
      expect(screen.getAllByText('Reach covers scored area from Day 7').length).toBeGreaterThan(0)
      expect(timelineCalls()).toHaveLength(1)
      fireEvent.click(done)
      expect(screen.getAllByText(kpiDate(0)).length).toBeGreaterThan(0)
      expect(screen.getByRole('button', { name: 'Pause area forecast playback' })).toBeTruthy()
      expect(timelineCalls()).toHaveLength(1)
    } finally {
      window.requestAnimationFrame = realRaf
    }
  })

  it('focusing a source shows its backend details; decision support stays non-prescriptive', async () => {
    mockBackendWithFictionalCases()
    renderPage()
    expect(within(await screen.findByRole('group', { name: /share of the district coloured by the risk surface/ })).getAllByRole('button')).toHaveLength(15)
    screen.getByRole('button', { name: 'Select 16 Oct 2026' }).click()
    expect((await screen.findAllByText(kpiDate(3))).length).toBeGreaterThan(0)
    // "View on Map" on an influencing card focuses that source; the panel names it.
    const list = screen.getByRole('list', { name: 'Outbreaks influencing my area' })
    within(list).getAllByRole('button', { name: 'View on Map →' })[0].click()
    const focused = await within(screen.getByLabelText('Area Intelligence')).findByText(/^OP:LSD:TEST-FICTIONAL-FARM-|^TEST-FICTIONAL/)
    expect(focused.closest('[data-row="focused"]')).toBeTruthy()
    // Suggested actions sit under the map column and are never imposed.
    const panel = screen.getByLabelText('Area explanation and actions').textContent
    expect(panel).toContain('Suggested actions')
    expect(panel).not.toMatch(/must (quarantine|vaccinate|cull)|impose (a )?quarantine|cull|movement ban/i)
  })

  it('shows an honest notice when the district has no eligible sources', async () => {
    mockBackend({ timeline: noSources, vetDistrict: 'Galle' })
    renderPage()
    expect(await screen.findByText(/No eligible sources in the last 14 days/)).toBeTruthy()
    const url = new URL(String(timelineCalls()[0][0]), 'http://localhost')
    expect(url.searchParams.get('district')).toBe('Galle')
    // The backend has answered: the score KPI must not keep saying it is waiting.
    expect(screen.getByText('NO SOURCES')).toBeTruthy()
    expect(screen.queryByText('Waiting for backend frames')).toBeNull()
  })
})
