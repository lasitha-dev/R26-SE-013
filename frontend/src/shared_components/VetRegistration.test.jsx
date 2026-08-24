import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import VetRegistration from './VetRegistration'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('VetRegistration Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn()
  })

  it('renders registration form with veterinarian-specific fields and district dropdown', () => {
    render(
      <BrowserRouter>
        <VetRegistration />
      </BrowserRouter>
    )

    expect(screen.getByText(/Register as Veterinarian/i)).toBeInTheDocument()
    expect(screen.getByText(/Full Name & Title/i)).toBeInTheDocument()
    expect(screen.getByText(/Veterinary License \/ Reg No\./i)).toBeInTheDocument()
    expect(screen.getByText(/Contact Phone Number/i)).toBeInTheDocument()
    expect(screen.getByText(/Primary Veterinary District Jurisdiction/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Register Veterinarian/i })).toBeInTheDocument()
  })

  it('validates password mismatch on client side', async () => {
    render(
      <BrowserRouter>
        <VetRegistration />
      </BrowserRouter>
    )

    const nameInput = screen.getByPlaceholderText(/Dr\. Samantha Perera/i)
    const emailInput = screen.getByPlaceholderText(/samantha@vet-council\.org/i)
    const licInput = screen.getByPlaceholderText(/VET-LK-88902/i)
    const phoneInput = screen.getByPlaceholderText(/\+94 77 123 4567/i)
    const districtSelect = screen.getByRole('combobox')
    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i)
    const submitBtn = screen.getByRole('button', { name: /Register Veterinarian/i })

    fireEvent.change(nameInput, { target: { value: 'Dr. Samantha Perera' } })
    fireEvent.change(emailInput, { target: { value: 'samantha@vet-council.org' } })
    fireEvent.change(licInput, { target: { value: 'VET-LK-88902' } })
    fireEvent.change(phoneInput, { target: { value: '+94771234567' } })
    fireEvent.change(districtSelect, { target: { value: 'Colombo' } })
    fireEvent.change(passwordInputs[0], { target: { value: 'password123' } })
    fireEvent.change(passwordInputs[1], { target: { value: 'mismatchPassword' } })

    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Passwords do not match/i)).toBeInTheDocument()
      expect(global.fetch).not.toHaveBeenCalled()
    })
  })

  it('submits valid registration with district and redirects to success screen', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Veterinarian registered successfully.' })
    })

    render(
      <BrowserRouter>
        <VetRegistration />
      </BrowserRouter>
    )

    const nameInput = screen.getByPlaceholderText(/Dr\. Samantha Perera/i)
    const emailInput = screen.getByPlaceholderText(/samantha@vet-council\.org/i)
    const licInput = screen.getByPlaceholderText(/VET-LK-88902/i)
    const phoneInput = screen.getByPlaceholderText(/\+94 77 123 4567/i)
    const districtSelect = screen.getByRole('combobox')
    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i)
    const submitBtn = screen.getByRole('button', { name: /Register Veterinarian/i })

    fireEvent.change(nameInput, { target: { value: 'Dr. Samantha Perera' } })
    fireEvent.change(emailInput, { target: { value: 'samantha@vet-council.org' } })
    fireEvent.change(licInput, { target: { value: 'VET-LK-88902' } })
    fireEvent.change(phoneInput, { target: { value: '+94771234567' } })
    fireEvent.change(districtSelect, { target: { value: 'Kandy' } })
    fireEvent.change(passwordInputs[0], { target: { value: 'password123' } })
    fireEvent.change(passwordInputs[1], { target: { value: 'password123' } })

    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/vet/register',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"district":"Kandy"')
        })
      )
      expect(mockNavigate).toHaveBeenCalledWith('/health/vet-registration-success')
    })
  })
})
