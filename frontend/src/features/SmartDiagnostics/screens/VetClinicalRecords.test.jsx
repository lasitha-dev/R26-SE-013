import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import VetClinicalRecords from './VetClinicalRecords';

// Custom render helper
const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('VetClinicalRecords Component Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.localStorage.setItem('token', 'mock-token');
  });

  it('renders VetClinicalRecords component and headers', async () => {
    // Mock APIs
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/vet/my-farms')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([])
        });
      }
      if (url.includes('/api/vet/cases')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([])
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithRouter(<VetClinicalRecords />);

    expect(screen.getByText('Diagnostic & Pathology Case Records')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search by animal ID, diagnosis, or farm...')).toBeInTheDocument();
  });

  it('fetches assigned farms and renders dropdown filter', async () => {
    const mockFarms = [
      { id: 'FARM-1', owner_name: 'Highland Dairy Holdings' },
      { id: 'FARM-2', owner_name: 'Greenfield Pastures' }
    ];

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/vet/my-farms')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockFarms)
        });
      }
      if (url.includes('/api/vet/cases')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([])
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithRouter(<VetClinicalRecords />);

    await waitFor(() => {
      expect(screen.getByText('All Assigned Farms')).toBeInTheDocument();
      expect(screen.getByText('Highland Dairy Holdings')).toBeInTheDocument();
      expect(screen.getByText('Greenfield Pastures')).toBeInTheDocument();
    });
  });

  it('filters cases when a farm is selected in the dropdown', async () => {
    const mockFarms = [
      { id: 'FARM-1', owner_name: 'Highland Dairy Holdings' }
    ];

    let lastFetchUrl = '';
    global.fetch = vi.fn().mockImplementation((url) => {
      lastFetchUrl = url;
      if (url.includes('/api/vet/my-farms')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockFarms)
        });
      }
      if (url.includes('/api/vet/cases')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 'REC-001',
              case_number: 'REC-001',
              animal_identifier: 'SL-COW-4402',
              breed: 'Holstein-Friesian',
              farm_name: 'Highland Dairy Holdings',
              disease_name: 'Lumpy Skin Disease',
              confidence: 94.2,
              status: 'Verified',
              verified: true
            }
          ])
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithRouter(<VetClinicalRecords />);

    await waitFor(() => {
      expect(screen.getByText('Highland Dairy Holdings')).toBeInTheDocument();
    });

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'FARM-1' } });

    await waitFor(() => {
      expect(lastFetchUrl).toContain('farm_id=FARM-1');
    });
  });
});
