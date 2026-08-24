import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import VetSettings from './VetSettings'

describe('VetSettings Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    localStorage.setItem('token', 'mock-vet-token')
    localStorage.setItem('full_name', 'Dr. Samantha Perera')
    localStorage.setItem('email', 'samantha@vet-council.org')
    localStorage.setItem('license_number', 'VET-LK-88902')
    localStorage.setItem('phone', '+94771234567')
    localStorage.setItem('district', 'Colombo')
    localStorage.setItem('role', 'vet')
    global.fetch = vi.fn()
  })

  it('fetches vet profile on mount and populates form fields including district', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        full_name: 'Dr. Ruwan Wickramasinghe',
        email: 'ruwan@vet-council.org',
        license_number: 'VET-LK-99001',
        phone: '+94719876543',
        district: 'Kandy',
        role: 'vet'
      })
    })

    render(
      <BrowserRouter>
        <VetSettings />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/vet/profile',
        expect.objectContaining({
          headers: { Authorization: 'Bearer mock-vet-token' }
        })
      )
      expect(screen.getByDisplayValue('Dr. Ruwan Wickramasinghe')).toBeInTheDocument()
      expect(screen.getByDisplayValue('ruwan@vet-council.org')).toBeInTheDocument()
      expect(screen.getByDisplayValue('VET-LK-99001')).toBeInTheDocument()
      expect(screen.getByDisplayValue('+94719876543')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Kandy District')).toBeInTheDocument()
    })
  })

  it('submits updated profile via PUT /api/vet/profile and updates localStorage', async () => {
    // Initial fetch mock
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        full_name: 'Dr. Samantha Perera',
        email: 'samantha@vet-council.org',
        license_number: 'VET-LK-88902',
        phone: '+94771234567',
        district: 'Colombo',
        role: 'vet'
      })
    })

    // PUT update mock
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: 'Veterinarian profile updated successfully.',
        full_name: 'Dr. Samantha Silva',
        email: 'samantha@vet-council.org',
        license_number: 'VET-LK-88902',
        phone: '+94779998888',
        district: 'Galle',
        role: 'vet'
      })
    })

    render(
      <BrowserRouter>
        <VetSettings />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByDisplayValue('Dr. Samantha Perera')).toBeInTheDocument()
    })

    const nameInput = screen.getByDisplayValue('Dr. Samantha Perera')
    const phoneInput = screen.getByDisplayValue('+94771234567')
    const districtSelect = screen.getByRole('combobox')
    const saveBtn = screen.getByRole('button', { name: /Save Profile Details/i })

    fireEvent.change(nameInput, { target: { value: 'Dr. Samantha Silva' } })
    fireEvent.change(phoneInput, { target: { value: '+94779998888' } })
    fireEvent.change(districtSelect, { target: { value: 'Galle' } })

    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/vet/profile',
        expect.objectContaining({
          method: 'PUT',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer mock-vet-token'
          }),
          body: JSON.stringify({
            full_name: 'Dr. Samantha Silva',
            license_number: 'VET-LK-88902',
            phone: '+94779998888',
            district: 'Galle'
          })
        })
      )
      expect(screen.getByText(/Practitioner profile updated successfully/i)).toBeInTheDocument()
      expect(localStorage.getItem('full_name')).toBe('Dr. Samantha Silva')
      expect(localStorage.getItem('district')).toBe('Galle')
      expect(localStorage.getItem('phone')).toBe('+94779998888')
    })
  })
})
