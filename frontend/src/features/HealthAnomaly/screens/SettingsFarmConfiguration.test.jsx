import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ProfileContext } from '../../../context/ProfileContext.jsx'
import SettingsFarmConfiguration from './SettingsFarmConfiguration.jsx'

vi.mock('leaflet', () => ({ default: {
  Icon: { Default: Object.assign(function () {}, { mergeOptions: vi.fn() }) },
  map: () => ({ whenReady: (callback) => callback(), on: vi.fn(), remove: vi.fn(), flyTo: vi.fn() }),
  tileLayer: () => ({ addTo: vi.fn() }),
  marker: () => ({ addTo: () => ({ on: vi.fn(), setLatLng: vi.fn() }) }),
} }))

const OLD_LOCATION = '7.2900, 80.6300 (Kandy District)'
const NEW_LOCATION = '6.0500, 80.2200 (Galle District)'
let savedProfile, writes, saveError, reverseError

const response = (body, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => body })

function mountSettings() {
  return render(
    <MemoryRouter>
      <ProfileContext.Provider value={{ setProfilePhoto: vi.fn(), setFarmerName: vi.fn() }}>
        <SettingsFarmConfiguration />
      </ProfileContext.Provider>
    </MemoryRouter>,
  )
}

async function openGps() {
  fireEvent.click(screen.getByRole('button', { name: /Update Location/ }))
  fireEvent.click(screen.getByRole('button', { name: /Find My Location/ }))
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('token', 'fictional-farm-session')
  savedProfile = { owner_name: 'Current Farmer', email: 'farm@example.test', veterinarian_name: 'Current Vet',
    latitude: 7.29, longitude: 80.63, location_district: 'Kandy District', location: OLD_LOCATION }
  writes = []
  saveError = null
  reverseError = false
  vi.spyOn(window, 'alert').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
  vi.stubGlobal('navigator', { geolocation: {
    getCurrentPosition: (success) => success({ coords: { latitude: 6.05, longitude: 80.22 } }),
  } })
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (url.endsWith('/api/user/profile')) {
      if (options.method === 'PUT') {
        expect(options.headers.Authorization).toBe('Bearer fictional-farm-session')
        const body = JSON.parse(options.body)
        writes.push(body)
        if (saveError === 'network') throw new Error('Network unavailable')
        if (saveError) return response({ detail: saveError }, false)
        savedProfile = { ...savedProfile, ...body }
        return response({ message: 'Saved' })
      }
      return response({ ...savedProfile })
    }
    if (url.includes('nominatim.openstreetmap.org/reverse')) {
      if (reverseError) throw new Error('Geocoder unavailable')
      return response({ address: { state_district: 'Galle', city: 'Different Town' } })
    }
    if (url.includes('nominatim.openstreetmap.org/search')) return response([{ lat: '6.05', lon: '80.22' }])
    if (url.endsWith('/api/user/breed-settings') || url.endsWith('/api/farms/assigned-vets')) return response([])
    throw new Error(`Unexpected test request: ${url}`)
  }))
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('farm location merge integration', () => {
  it('uses the loaded farm GPS and separate district when saving, even if the browser cache changes', async () => {
    mountSettings()
    await screen.findByDisplayValue(OLD_LOCATION)
    localStorage.setItem('registered_farm_lat', '9.5')
    localStorage.setItem('registered_farm_lon', '81.5')
    localStorage.setItem('registered_farm_district', 'Another District')
    fireEvent.click(screen.getByRole('button', { name: 'Save Profile Details' }))
    await waitFor(() => expect(writes).toHaveLength(1))
    expect(writes[0]).toMatchObject({ latitude: 7.29, longitude: 80.63,
      location_district: 'Kandy District', location: OLD_LOCATION })
  })

  it('clears another account’s cached GPS and location for a farm without coordinates', async () => {
    for (const key of ['lat', 'lon', 'district', 'name', 'location']) localStorage.setItem(`registered_farm_${key}`, 'stale')
    savedProfile = { owner_name: 'Current Farmer', veterinarian_name: 'Current Vet', location_district: 'Galle District' }
    mountSettings()
    await screen.findByDisplayValue('Galle District')
    expect(localStorage.getItem('registered_farm_lat')).toBeNull()
    expect(localStorage.getItem('registered_farm_lon')).toBeNull()
    expect(localStorage.getItem('registered_farm_location')).toBe('Galle District')
    fireEvent.click(screen.getByRole('button', { name: 'Save Profile Details' }))
    await waitFor(() => expect(writes[0]).toMatchObject({ latitude: null, longitude: null, location_district: 'Galle District' }))
    expect(document.querySelector('iframe')).toBeNull()
  })

  it('reads a legacy coordinate label and saves its district separately', async () => {
    savedProfile.location_district = OLD_LOCATION
    delete savedProfile.location
    mountSettings()
    await screen.findByDisplayValue(OLD_LOCATION)
    fireEvent.click(screen.getByRole('button', { name: 'Save Profile Details' }))
    await waitFor(() => expect(writes[0]).toMatchObject({ location_district: 'Kandy District', location: OLD_LOCATION }))
  })

  it('saves GPS immediately and reloads the separate location fields from the database', async () => {
    const view = mountSettings()
    await screen.findByDisplayValue(OLD_LOCATION)
    await openGps()
    await screen.findByText('Farm location saved: Galle District.')
    expect(writes).toEqual([{ latitude: 6.05, longitude: 80.22, location_district: 'Galle District', location: NEW_LOCATION }])
    expect(localStorage.getItem('registered_farm_location')).toBe(NEW_LOCATION)
    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(writes).toHaveLength(1)
    view.unmount()
    mountSettings()
    await screen.findByDisplayValue(NEW_LOCATION)
    expect(localStorage.getItem('registered_farm_district')).toBe('Galle District')
  })

  it.each(['Database unavailable', 'network'])('keeps the saved location when a GPS save fails: %s', async (failure) => {
    mountSettings()
    await screen.findByDisplayValue(OLD_LOCATION)
    saveError = failure
    await openGps()
    await waitFor(() => expect(window.alert).toHaveBeenCalled())
    expect(screen.getByDisplayValue(OLD_LOCATION)).toBeTruthy()
    expect(localStorage.getItem('registered_farm_location')).toBe(OLD_LOCATION)
    expect(screen.queryByText('Farm location saved: Galle District.')).toBeNull()
  })

  it('saves a searched map selection on confirmation', async () => {
    mountSettings()
    await screen.findByDisplayValue(OLD_LOCATION)
    fireEvent.click(screen.getByRole('button', { name: /Update Location/ }))
    fireEvent.click(screen.getByRole('button', { name: /Manual Select from Map/ }))
    const search = screen.getByPlaceholderText(/Search any location/)
    fireEvent.change(search, { target: { value: 'Galle' } })
    fireEvent.submit(search.closest('form'))
    await waitFor(() => expect(screen.getByRole('button', { name: /Confirm.*Save Location/ }).disabled).toBe(false))
    expect(writes).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: /Confirm.*Save Location/ }))
    await screen.findByDisplayValue(NEW_LOCATION)
    expect(writes[0]).toMatchObject({ location_district: 'Galle District', location: NEW_LOCATION, latitude: 6.05, longitude: 80.22 })
    expect(screen.queryByText('Manual Location Selector')).toBeNull()
  })

  it('keeps usable GPS when the district lookup is unavailable', async () => {
    mountSettings()
    await screen.findByDisplayValue(OLD_LOCATION)
    reverseError = true
    await openGps()
    await screen.findByText('Farm location saved: Unknown District.')
    expect(writes[0]).toMatchObject({ latitude: 6.05, longitude: 80.22, location_district: 'Unknown District' })
  })
})
