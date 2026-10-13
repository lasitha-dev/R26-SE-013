import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import VetLogin from './VetLogin'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('VetLogin Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    global.fetch = vi.fn()
  })

  it('renders login form with clinical credentials branding', () => {
    render(
      <BrowserRouter>
        <VetLogin />
      </BrowserRouter>
    )

    expect(screen.getByText(/Veterinarian Login/i)).toBeInTheDocument()
    expect(screen.getByText(/Clinical Email Address/i)).toBeInTheDocument()
    expect(screen.getByText(/^Password$/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Access Clinical Workbench/i })).toBeInTheDocument()
  })

  it('submits clinical credentials and redirects on successful authentication', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'mock-vet-jwt-token',
        full_name: 'Dr. Sarah Jayasinghe',
        email: 'doctor@veterinary-council.gov',
        role: 'vet',
        license_number: 'VET-LK-88902',
        phone: '+94771234567'
      })
    })

    render(
      <BrowserRouter>
        <VetLogin />
      </BrowserRouter>
    )

    const emailInput = screen.getByPlaceholderText(/doctor@veterinary-council.gov/i)
    const passwordInput = screen.getByPlaceholderText(/••••••••/i)
    const submitBtn = screen.getByRole('button', { name: /Access Clinical Workbench/i })

    fireEvent.change(emailInput, { target: { value: 'doctor@veterinary-council.gov' } })
    fireEvent.change(passwordInput, { target: { value: 'securePass123' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/vet/login',
        expect.objectContaining({
          method: 'POST'
        })
      )
      expect(localStorage.getItem('token')).toBe('mock-vet-jwt-token')
      expect(localStorage.getItem('role')).toBe('vet')
      expect(mockNavigate).toHaveBeenCalledWith('/vet/dashboard')
    })
  })

  it('displays clinical error banner when backend authentication fails', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Invalid email or password.' })
    })

    render(
      <BrowserRouter>
        <VetLogin />
      </BrowserRouter>
    )

    const emailInput = screen.getByPlaceholderText(/doctor@veterinary-council.gov/i)
    const passwordInput = screen.getByPlaceholderText(/••••••••/i)
    const submitBtn = screen.getByRole('button', { name: /Access Clinical Workbench/i })

    fireEvent.change(emailInput, { target: { value: 'doctor@veterinary-council.gov' } })
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Invalid email or password/i)).toBeInTheDocument()
    })
  })

  it('submits clinical credentials and redirects DAPH to forecasting', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'mock-daph-jwt-token',
        full_name: 'Dr. DAPH Official',
        email: 'daph@veterinary-council.gov',
        role: 'daph',
        license_number: 'VET-DAPH-123',
        phone: '+94771234567'
      })
    })

    render(
      <BrowserRouter>
        <VetLogin />
      </BrowserRouter>
    )

    const emailInput = screen.getByPlaceholderText(/doctor@veterinary-council.gov/i)
    const passwordInput = screen.getByPlaceholderText(/••••••••/i)
    const submitBtn = screen.getByRole('button', { name: /Access Clinical Workbench/i })

    fireEvent.change(emailInput, { target: { value: 'daph@veterinary-council.gov' } })
    fireEvent.change(passwordInput, { target: { value: 'securePass123' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(localStorage.getItem('token')).toBe('mock-daph-jwt-token')
      expect(localStorage.getItem('role')).toBe('daph')
      expect(mockNavigate).toHaveBeenCalledWith('/vet/forecasting')
    })
  })

  it('fails closed when an unsupported role is returned', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'mock-farmer-jwt-token',
        full_name: 'Farmer John',
        email: 'john@farm.com',
        role: 'farmer'
      })
    })

    render(
      <BrowserRouter>
        <VetLogin />
      </BrowserRouter>
    )

    const emailInput = screen.getByPlaceholderText(/doctor@veterinary-council.gov/i)
    const passwordInput = screen.getByPlaceholderText(/••••••••/i)
    const submitBtn = screen.getByRole('button', { name: /Access Clinical Workbench/i })

    fireEvent.change(emailInput, { target: { value: 'john@farm.com' } })
    fireEvent.change(passwordInput, { target: { value: 'securePass123' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Authentication failed. Unsupported professional role./i)).toBeInTheDocument()
      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('role')).toBeNull()
      expect(mockNavigate).not.toHaveBeenCalledWith('/vet/dashboard')
    })
  })

  it('fails closed when role is missing instead of defaulting to vet', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'mock-unknown-jwt-token',
        full_name: 'Unknown User',
        email: 'unknown@council.gov'
      })
    })

    render(
      <BrowserRouter>
        <VetLogin />
      </BrowserRouter>
    )

    const emailInput = screen.getByPlaceholderText(/doctor@veterinary-council.gov/i)
    const passwordInput = screen.getByPlaceholderText(/••••••••/i)
    const submitBtn = screen.getByRole('button', { name: /Access Clinical Workbench/i })

    fireEvent.change(emailInput, { target: { value: 'unknown@council.gov' } })
    fireEvent.change(passwordInput, { target: { value: 'securePass123' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Authentication failed. Unsupported professional role./i)).toBeInTheDocument()
      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('role')).toBeNull()
    })
  })
})
