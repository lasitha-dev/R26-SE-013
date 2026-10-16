import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import WellnessDataIntake from './WellnessDataIntake'
import { ProfileContext } from '../../../context/ProfileContext'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('WellnessDataIntake - Bulk CSV Upload & Automated Monitoring', () => {
  const mockCattleList = [
    {
      id: 'c1',
      identifier: 'kiri katiya',
      breed: 'Jersey',
      calving_date: '2026-05-01',
      dob: '2022-01-01'
    },
    {
      id: 'c2',
      identifier: 'sudu putha',
      breed: 'Holstein-Friesian',
      calving_date: '2026-06-01',
      dob: '2021-03-01'
    }
  ]

  const mockProfileContext = {
    profilePhoto: '',
    setProfilePhoto: vi.fn(),
    farmerName: 'Farmer Test',
    setFarmerName: vi.fn(),
    hasAlerts: false,
    checkAlertsStatus: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn((url, options) => {
      if (url.includes('/api/cattle')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockCattleList),
        })
      }
      if (url.includes('/api/monitor/predict')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ is_anomaly: true, status: 'Alert' }),
        })
      }
      if (url.includes('/api/daily-logs/bulk')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: 'success',
              message: 'Successfully imported 2 logs and evaluated 2 cattle.',
              inserted_count: 2,
              evaluated_count: 2,
              alerts_triggered: 1,
              results: [
                {
                  cattle_id: 'c1',
                  identifier: 'kiri katiya',
                  breed: 'Jersey',
                  date: '2026-10-14',
                  milk_yield: 6.5,
                  weight: 380.0,
                  is_anomaly: true,
                  new_status: 'Alert'
                },
                {
                  cattle_id: 'c2',
                  identifier: 'sudu putha',
                  breed: 'Holstein-Friesian',
                  date: '2026-10-14',
                  milk_yield: 22.0,
                  weight: 550.0,
                  is_anomaly: false,
                  new_status: 'Healthy'
                }
              ]
            }),
        })
      }
      if (url.includes('/api/daily-logs')) {
        if (options?.method === 'POST') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ id: 'log1', cattle_id: 'c1', date: '2026-10-15', milk_yield: 6.5, weight: 380.0 }),
          })
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      })
    })
  })

  it('renders bulk upload tab and download sample CSV button', async () => {
    render(
      <MemoryRouter>
        <ProfileContext.Provider value={mockProfileContext}>
          <WellnessDataIntake />
        </ProfileContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/Bulk Upload CSV/i)).toBeInTheDocument()
    })

    // Switch to bulk tab
    fireEvent.click(screen.getByText(/Bulk Upload CSV/i))

    // Check Download Sample CSV button is present
    const downloadBtn = screen.getByText(/Download Sample CSV/i)
    expect(downloadBtn).toBeInTheDocument()

    // Test clicking download button (doesn't throw)
    fireEvent.click(downloadBtn)
  })

  it('parses CSV and renders Automated Batch Monitoring Report after submit', async () => {
    render(
      <MemoryRouter>
        <ProfileContext.Provider value={mockProfileContext}>
          <WellnessDataIntake />
        </ProfileContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/Bulk Upload CSV/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText(/Bulk Upload CSV/i))

    // Simulate file upload with identifier header
    const csvContent = "identifier,date,milk_yield,weight\nkiri katiya,2026-10-14,6.5,380.0\nsudu putha,2026-10-14,22.0,550.0\n"
    const file = new File([csvContent], 'test_intake.csv', { type: 'text/csv' })

    const fileInput = document.getElementById('csv-file-upload')
    expect(fileInput).toBeInTheDocument()

    fireEvent.change(fileInput, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByText(/Successfully parsed 2 data entries/i)).toBeInTheDocument()
    })

    // Click Import Bulk Data
    const submitBtn = screen.getByText(/Import Bulk Data/i)
    fireEvent.click(submitBtn)

    // Verify Automated Batch Monitoring Report displays
    await waitFor(() => {
      expect(screen.getByText(/Automated Batch Monitoring Report/i)).toBeInTheDocument()
    })

    // Verify evaluation summary metrics
    expect(screen.getByText(/Ingested:/i)).toBeInTheDocument()
    expect(screen.getByText(/Evaluated:/i)).toBeInTheDocument()
    expect(screen.getByText(/Alerts:/i)).toBeInTheDocument()

    // Verify row items and anomaly alert badge
    expect(screen.getByText(/• ALERT/i)).toBeInTheDocument()
    expect(screen.getByText(/• HEALTHY/i)).toBeInTheDocument()

    // Verify Start 7-Day Diagnosis link
    const diagnosisLink = screen.getByText(/Start 7-Day Diagnosis/i).closest('a')
    expect(diagnosisLink).toHaveAttribute('href', '/health/7-day-triage-scan?cattle_id=c1')

    // Verify checkAlertsStatus was called
    expect(mockProfileContext.checkAlertsStatus).toHaveBeenCalled()
  })

  it('displays Clinical Anomaly Detected modal on anomaly and closes it when Dismiss is clicked', async () => {
    render(
      <MemoryRouter>
        <ProfileContext.Provider value={mockProfileContext}>
          <WellnessDataIntake />
        </ProfileContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/kiri katiya/i)).toBeInTheDocument()
    })

    // Select subject animal
    const selectElem = screen.getByRole('combobox')
    fireEvent.change(selectElem, { target: { value: 'c1' } })

    // Fill form fields
    const dateInput = document.querySelector('input[name="date"]')
    const milkInput = document.querySelector('input[name="milk_yield"]')
    const weightInput = document.querySelector('input[name="weight"]')

    fireEvent.change(dateInput, { target: { value: '2026-10-15' } })
    fireEvent.change(milkInput, { target: { value: '6.5' } })
    fireEvent.change(weightInput, { target: { value: '380.0' } })

    // Submit single log form
    const submitBtn = screen.getByText(/Update Yield/i)
    fireEvent.click(submitBtn)

    // Verify Anomaly Warning Modal appears
    await waitFor(() => {
      expect(screen.getByText(/Clinical Anomaly Detected!/i)).toBeInTheDocument()
    })

    // Click Dismiss button inside modal
    const dismissBtn = screen.getByTestId('modal-dismiss')
    expect(dismissBtn).toBeInTheDocument()
    fireEvent.click(dismissBtn)

    // Verify modal is closed
    await waitFor(() => {
      expect(screen.queryByText(/Clinical Anomaly Detected!/i)).not.toBeInTheDocument()
    })
  })

  it('navigates to 7-Day Triage Scan with selected cattle ID when Start 7-Day Diagnosis is clicked in modal', async () => {
    render(
      <MemoryRouter>
        <ProfileContext.Provider value={mockProfileContext}>
          <WellnessDataIntake />
        </ProfileContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/kiri katiya/i)).toBeInTheDocument()
    })

    // Select subject animal
    const selectElem = screen.getByRole('combobox')
    fireEvent.change(selectElem, { target: { value: 'c1' } })

    // Fill form fields
    const dateInput = document.querySelector('input[name="date"]')
    const milkInput = document.querySelector('input[name="milk_yield"]')
    const weightInput = document.querySelector('input[name="weight"]')

    fireEvent.change(dateInput, { target: { value: '2026-10-15' } })
    fireEvent.change(milkInput, { target: { value: '6.5' } })
    fireEvent.change(weightInput, { target: { value: '380.0' } })

    // Submit single log form
    const submitBtn = screen.getByText(/Update Yield/i)
    fireEvent.click(submitBtn)

    // Verify modal appears
    await waitFor(() => {
      expect(screen.getByText(/Clinical Anomaly Detected!/i)).toBeInTheDocument()
    })

    // Click Start 7-Day Diagnosis button in modal
    const triageBtn = screen.getByTestId('modal-start-triage')
    expect(triageBtn).toBeInTheDocument()
    fireEvent.click(triageBtn)

    // Verify modal is dismissed
    await waitFor(() => {
      expect(screen.queryByText(/Clinical Anomaly Detected!/i)).not.toBeInTheDocument()
    })

    // Verify navigation was triggered
    expect(mockNavigate).toHaveBeenCalledWith(
      '/health/7-day-triage-scan?cattle_id=c1',
      { state: { cattleId: 'c1' } }
    )
  })
})
