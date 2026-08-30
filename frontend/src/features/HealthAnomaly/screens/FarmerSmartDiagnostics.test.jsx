import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import FarmerSmartDiagnostics from './FarmerSmartDiagnostics';
import FarmerCaseHistory from './FarmerCaseHistory';

const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('Farmer Smart Diagnostics & Case History Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.localStorage.setItem('token', 'mock-farmer-token');
    global.localStorage.setItem('owner_name', 'Sunimal Farm');
  });

  describe('FarmerSmartDiagnostics Component', () => {
    it('renders initial dropzone, headers and guidance for farmer', () => {
      global.fetch = vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve([])
        })
      );

      renderWithRouter(<FarmerSmartDiagnostics />);

      expect(screen.getByText('Smart Livestock Disease Diagnostics')).toBeInTheDocument();
      expect(screen.getByText('General Diagnostic Scan')).toBeInTheDocument();
      expect(screen.getByText('My Case History')).toBeInTheDocument();
      expect(screen.getByText(/Drag and drop clinical imagery/i)).toBeInTheDocument();
    });

    it('renders locked banner when cattle is marked deceased', async () => {
      global.fetch = vi.fn().mockImplementation((url) => {
        if (url.includes('/api/cattle/COW-123')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({
              id: 'COW-123',
              identifier: 'COW-TAG-99',
              status: 'Deceased',
              health_status: 'Deceased'
            })
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <MemoryRouter initialEntries={['/health/diagnostics?cattle_id=COW-123']}>
          <FarmerSmartDiagnostics />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('diagnostics-locked-banner')).toBeInTheDocument();
        expect(screen.getByText('Diagnostics Locked')).toBeInTheDocument();
      });
    });
  });

  describe('FarmerCaseHistory Component', () => {
    it('renders farmer case history list with status badges', async () => {
      const mockCases = [
        {
          id: 'CASE-01',
          case_number: 'REC-2026-001',
          animal_identifier: 'COW-101',
          breed: 'Jersey',
          disease_name: 'Lumpy Skin Disease',
          confidence: 94.2,
          severity: 'High',
          verified: false,
          status: 'Pending Verification',
          created_at: '2026-08-24 10:00:00',
          reported_by: 'farmer'
        },
        {
          id: 'CASE-02',
          case_number: 'REC-2026-002',
          animal_identifier: 'COW-102',
          breed: 'Friesian',
          disease_name: 'Cattle (Healthy)',
          confidence: 98.1,
          severity: 'Low',
          verified: true,
          status: 'Verified',
          created_at: '2026-08-23 15:00:00',
          vet_name: 'Dr. Sarah Connor',
          reported_by: 'vet'
        }
      ];

      global.fetch = vi.fn().mockImplementation((url) => {
        if (url.includes('/api/vet/cases')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockCases)
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithRouter(<FarmerCaseHistory />);

      await waitFor(() => {
        expect(screen.getByText('Livestock Diagnostic Case History')).toBeInTheDocument();
        expect(screen.getByText('REC-2026-001')).toBeInTheDocument();
        expect(screen.getByText('REC-2026-002')).toBeInTheDocument();
        expect(screen.getByText('Pending Verification')).toBeInTheDocument();
        expect(screen.getByText('Verified by Vet')).toBeInTheDocument();
      });
    });

    it('opens detail modal on clicking a case row', async () => {
      const mockCases = [
        {
          id: 'CASE-01',
          case_number: 'REC-2026-001',
          animal_identifier: 'COW-101',
          breed: 'Jersey',
          disease_name: 'Lumpy Skin Disease',
          confidence: 94.2,
          severity: 'High',
          stage: 'Acute Phase',
          prognosis: 'Guarded',
          rationale: 'Nodular lesions found on dermis.',
          verified: false,
          status: 'Pending Verification',
          created_at: '2026-08-24 10:00:00'
        }
      ];

      global.fetch = vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockCases)
        })
      );

      renderWithRouter(<FarmerCaseHistory />);

      await waitFor(() => {
        expect(screen.getByText('REC-2026-001')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('REC-2026-001'));

      await waitFor(() => {
        expect(screen.getByText('Livestock Pathology Disease Report')).toBeInTheDocument();
        expect(screen.getByText('Nodular lesions found on dermis.')).toBeInTheDocument();
        expect(screen.getByText('Close Report')).toBeInTheDocument();
      });
    });
  });
});
