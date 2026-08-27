import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import VetLayout from './VetLayout'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('VetLayout Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ([]) })
  })

  it('1. Vet sees every existing navigation entry and Geospatial', () => {
    localStorage.setItem('token', 'valid-token')
    localStorage.setItem('role', 'vet')
    render(<MemoryRouter initialEntries={['/vet/dashboard']}><VetLayout /></MemoryRouter>)
    
    expect(screen.getByText('Clinical Overview')).toBeInTheDocument()
    expect(screen.getByText('Smart Diagnostics')).toBeInTheDocument()
    expect(screen.getByText('Geospatial Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Seasonal Forecasting')).toBeInTheDocument()
    expect(screen.getByText('License & Profile')).toBeInTheDocument()
    expect(screen.getByText('Sign Out')).toBeInTheDocument()
  })

  it('2. DAPH sees Seasonal Forecasting but not Dashboard, Assigned Farms or Geospatial', () => {
    localStorage.setItem('token', 'valid-token')
    localStorage.setItem('role', 'daph')
    render(<MemoryRouter initialEntries={['/vet/forecasting']}><VetLayout /></MemoryRouter>)
    
    expect(screen.getByText('Seasonal Forecasting')).toBeInTheDocument()
    expect(screen.queryByText('Clinical Overview')).not.toBeInTheDocument()
    expect(screen.queryByText('Smart Diagnostics')).not.toBeInTheDocument()
    expect(screen.queryByText('Geospatial Intelligence')).not.toBeInTheDocument()

    // DAPH terminology proofs
    expect(screen.getByText('DAPH Forecasting Portal')).toBeInTheDocument()
    expect(screen.getByText('National Disease Oversight')).toBeInTheDocument()
    expect(screen.getByText('DAPH NATIONAL SCOPE')).toBeInTheDocument()

    // Non-vet terminology proofs
    expect(screen.queryByText('Vet Clinical Portal')).not.toBeInTheDocument()
    expect(screen.queryByText('Veterinary Authority')).not.toBeInTheDocument()
    expect(screen.queryByText('VET NODE LIVE')).not.toBeInTheDocument()
  })

  it('3. DAPH does not receive a navigable Settings/Profile action but branding remains', () => {
    localStorage.setItem('token', 'valid-token')
    localStorage.setItem('role', 'daph')
    localStorage.setItem('full_name', 'Dr. DAPH Official')
    render(<MemoryRouter initialEntries={['/vet/forecasting']}><VetLayout /></MemoryRouter>)
    
    expect(screen.queryByText('License & Profile')).not.toBeInTheDocument()
    expect(screen.getByText('ADRS CORE')).toBeInTheDocument()

    // The name is replaced by DAPH Official and title is National Scope
    expect(screen.getByText('DAPH Official')).toBeInTheDocument()
    expect(screen.getByText('National Scope')).toBeInTheDocument()
    expect(screen.queryByText('Verified Practitioner')).not.toBeInTheDocument()
    expect(screen.queryByText('Dr. DAPH Official')).not.toBeInTheDocument() // Ignored in favor of role name

    expect(screen.getByText('Sign Out')).toBeInTheDocument()
  })

  it('4. Missing/unsupported role fails closed', () => {
    localStorage.setItem('token', 'valid-token')
    localStorage.setItem('role', 'farmer')
    render(<MemoryRouter initialEntries={['/vet/dashboard']}><VetLayout /></MemoryRouter>)
    
    expect(mockNavigate).not.toHaveBeenCalled()
    // It should render Navigate to=/vet/login, not layout
    expect(screen.queryByText('ADRS CORE')).not.toBeInTheDocument()
  })

  it('5. Existing Vet logout behavior remains', () => {
    localStorage.setItem('token', 'valid-token')
    localStorage.setItem('role', 'vet')
    render(<MemoryRouter initialEntries={['/vet/dashboard']}><VetLayout /></MemoryRouter>)
    
    const signOutBtn = screen.getByText('Sign Out')
    fireEvent.click(signOutBtn)
    
    expect(localStorage.getItem('token')).toBeNull()
    expect(mockNavigate).toHaveBeenCalledWith('/vet/login')
  })
})
