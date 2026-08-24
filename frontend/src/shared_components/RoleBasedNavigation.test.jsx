import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import DashboardLayout from './DashboardLayout.jsx'
import VetLayout from './VetLayout.jsx'
import { ProfileProvider } from '../context/ProfileContext.jsx'

describe('Role-Based Navigation Controls', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('token', 'mock-jwt-token')
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  describe('Farm Owner Navigation (DashboardLayout)', () => {
    it('only renders Wellness & BCS and Herd Registry for Farm Owner', () => {
      localStorage.setItem('role', 'farm_owner')
      localStorage.setItem('owner_name', 'Julian Vane')

      render(
        <MemoryRouter initialEntries={['/health/dashboard']}>
          <ProfileProvider>
            <DashboardLayout />
          </ProfileProvider>
        </MemoryRouter>
      )

      // Must be present
      expect(screen.getByText('Wellness & BCS')).toBeInTheDocument()
      expect(screen.getByText('Herd Registry')).toBeInTheDocument()
      expect(screen.getByText('Settings')).toBeInTheDocument()
      expect(screen.getByText('Sign Out')).toBeInTheDocument()

      // Must NOT be present in Farm Owner sidebar
      expect(screen.queryByText('AI Smart Diagnosis')).not.toBeInTheDocument()
      expect(screen.queryByText('Geospatial Intelligence')).not.toBeInTheDocument()
      expect(screen.queryByText('Seasonal Forecasting')).not.toBeInTheDocument()
    })
  })

  describe('Veterinarian Navigation (VetLayout)', () => {
    it('renders Clinical Overview, Smart Diagnostics, Geospatial, and Forecasting for Vet', () => {
      localStorage.setItem('role', 'vet')
      localStorage.setItem('full_name', 'Dr. Sarah Connor')

      // Mock cattle API call inside VetLayout
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
      })

      render(
        <MemoryRouter initialEntries={['/vet/dashboard']}>
          <VetLayout />
        </MemoryRouter>
      )

      // Primary navigation items
      expect(screen.getByText('Clinical Overview')).toBeInTheDocument()
      expect(screen.getByText('Smart Diagnostics')).toBeInTheDocument()
      expect(screen.getByText('Geospatial Intelligence')).toBeInTheDocument()
      expect(screen.getByText('Seasonal Forecasting')).toBeInTheDocument()

      // Footer items maintained
      expect(screen.getByText('License & Profile')).toBeInTheDocument()
      expect(screen.getByText('Sign Out')).toBeInTheDocument()

      // Farm-owner specific links not in Vet sidebar
      expect(screen.queryByText('Wellness & BCS')).not.toBeInTheDocument()
      expect(screen.queryByText('Herd Registry')).not.toBeInTheDocument()
    })
  })
})
