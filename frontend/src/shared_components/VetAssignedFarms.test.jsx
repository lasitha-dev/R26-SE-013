import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import VetAssignedFarms from './VetAssignedFarms.jsx'

describe('VetAssignedFarms Component', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('token', 'mock-vet-jwt-token')
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders assigned farms with GPS coordinates and links', async () => {
    const mockFarms = [
      {
        id: 'farm-101',
        owner_name: 'Pramod Wijenayake',
        email: 'pramod@gmail.com',
        location_district: 'Colombo Central Agro District',
        latitude: 6.9271,
        longitude: 79.8612,
        registration_number: 'REG-LK-9901',
        total_animals: 12,
        alert_count: 1,
        status: 'Active Synchronization'
      }
    ]

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFarms
    })

    render(
      <MemoryRouter>
        <VetAssignedFarms />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText("Pramod Wijenayake's Dairy Estate")).toBeInTheDocument()
      expect(screen.getByText('REG-LK-9901')).toBeInTheDocument()
      expect(screen.getByText('GPS: 6.9271, 79.8612')).toBeInTheDocument()
      expect(screen.getByText('1 Alerts')).toBeInTheDocument()
      expect(screen.getByText('View Herd & Select Cattle')).toBeInTheDocument()
    })
  })

  it('renders empty state when no farms are assigned', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => []
    })

    render(
      <MemoryRouter>
        <VetAssignedFarms />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('No Agricultural Estates Assigned Yet')).toBeInTheDocument()
    })
  })
})
