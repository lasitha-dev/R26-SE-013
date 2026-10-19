import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import HerdRegistry from './HerdRegistry'

describe('HerdRegistry Component - Health Status and Filtering', () => {
  const mockCattleList = [
    {
      id: 'c1',
      identifier: 'COW-001',
      gender: 'Female',
      dob: '2021-01-01',
      breed: 'Friesian',
      health_status: 'Healthy',
      status: 'Healthy',
      bcs_score: 3.2,
    },
    {
      id: 'c2',
      identifier: 'COW-002',
      gender: 'Female',
      dob: '2020-05-10',
      breed: 'Jersey',
      health_status: 'Heat Stress',
      status: 'Heat Stress',
      bcs_score: 2.8,
    },
    {
      id: 'c3',
      identifier: 'COW-003',
      gender: 'Male',
      dob: '2022-03-15',
      breed: 'Sahiwal',
      health_status: 'Unhealthy',
      status: 'Unhealthy',
      bcs_score: 2.1,
    },
    {
      id: 'c4',
      identifier: 'COW-004',
      gender: 'Female',
      dob: '2019-11-20',
      breed: 'Local',
      health_status: 'Alert',
      status: 'Alert',
      bcs_score: 3.0,
    },
    {
      id: 'c5',
      identifier: 'COW-005',
      gender: 'Female',
      dob: '2018-08-01',
      breed: 'Friesian',
      health_status: 'Deceased',
      status: 'Deceased',
      bcs_score: null,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/cattle')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockCattleList),
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })
  })

  it('renders all distinct health status badges correctly', async () => {
    render(
      <MemoryRouter>
        <HerdRegistry />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('COW-001')).toBeInTheDocument()
    })

    expect(screen.getByText('HEALTHY')).toBeInTheDocument()
    expect(screen.getByText('HEAT STRESS')).toBeInTheDocument()
    expect(screen.getByText('UNHEALTHY')).toBeInTheDocument()
    expect(screen.getByText('ALERT')).toBeInTheDocument()
    expect(screen.getByText('DECEASED')).toBeInTheDocument()
  })

  it('accurately counts pending alerts (Heat Stress, Unhealthy, Alert)', async () => {
    render(
      <MemoryRouter>
        <HerdRegistry />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('COW-001')).toBeInTheDocument()
    })

    // 3 non-healthy living cattle: Heat Stress, Unhealthy, Alert
    expect(screen.getByText(/3 Pending Alerts/i)).toBeInTheDocument()
  })

  it('filters table rows based on status dropdown selection', async () => {
    render(
      <MemoryRouter>
        <HerdRegistry />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('COW-001')).toBeInTheDocument()
    })

    const filterSelect = screen.getByRole('combobox', { name: /Filter by Status/i })
    expect(filterSelect).toBeInTheDocument()

    // Filter by Heat Stress
    fireEvent.change(filterSelect, { target: { value: 'Heat Stress' } })
    expect(screen.getByText('COW-002')).toBeInTheDocument()
    expect(screen.queryByText('COW-001')).not.toBeInTheDocument()
    expect(screen.queryByText('COW-003')).not.toBeInTheDocument()

    // Filter by Unhealthy
    fireEvent.change(filterSelect, { target: { value: 'Unhealthy' } })
    expect(screen.getByText('COW-003')).toBeInTheDocument()
    expect(screen.queryByText('COW-002')).not.toBeInTheDocument()

    // Filter by Alert
    fireEvent.change(filterSelect, { target: { value: 'Alert' } })
    expect(screen.getByText('COW-004')).toBeInTheDocument()
    expect(screen.queryByText('COW-003')).not.toBeInTheDocument()

    // Back to ALL
    fireEvent.change(filterSelect, { target: { value: 'ALL' } })
    expect(screen.getByText('COW-001')).toBeInTheDocument()
    expect(screen.getByText('COW-002')).toBeInTheDocument()
    expect(screen.getByText('COW-003')).toBeInTheDocument()
    expect(screen.getByText('COW-004')).toBeInTheDocument()
    expect(screen.getByText('COW-005')).toBeInTheDocument()
  })
})
