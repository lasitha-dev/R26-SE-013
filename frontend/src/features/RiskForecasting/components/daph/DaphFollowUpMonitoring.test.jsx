import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DaphFollowUpMonitoring } from './DaphFollowUpMonitoring';
import {
  ROLES,
  SCOPE_LEVELS,
} from '../../contracts/viewerContext';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';

// Mock workflow API functions
vi.mock('../../services/riskForecastingWorkflowApi', async () => {
  const actual = await vi.importActual('../../services/riskForecastingWorkflowApi');
  return {
    ...actual,
    listFollowUps: vi.fn(),
    getFollowUp: vi.fn(),
    cancelFollowUp: vi.fn(),
  };
});

describe('DaphFollowUpMonitoring Component', () => {
  const validDaphContext = {
    userId: 'usr_daph_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: [],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: true,
      viewModelTransparency: true,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    },
  };

  const validVetContext = {
    userId: 'usr_vet_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    },
  };

  const validFarmerContext = {
    userId: 'usr_farmer_001',
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: false,
      recordResponse: false,
      viewReports: false,
    },
  };

  const sampleFollowUps = [
    {
      follow_up_id: 'ffu_001',
      forecast_id: 'fdr_001',
      disease: 'FMD',
      district: 'Anuradhapura',
      target_year: 2026,
      target_month: 8,
      forecast_risk_level: 'HIGH',
      forecast_probability_pct: 85,
      operational_priority: 'HIGH',
      assigned_vet_id: 'vet_officer_01',
      issued_by_daph_id: 'usr_daph_001',
      instruction_summary: 'Targeted FMD ring vaccination.',
      status: 'ISSUED',
      version: 1,
      created_at: '2026-08-20T10:00:00Z',
      updated_at: '2026-08-20T10:00:00Z',
    },
    {
      follow_up_id: 'ffu_002',
      forecast_id: 'fdr_002',
      disease: 'LSD',
      district: 'Jaffna',
      target_year: 2026,
      target_month: 8,
      forecast_risk_level: 'MEDIUM',
      forecast_probability_pct: 60,
      operational_priority: 'MEDIUM',
      assigned_vet_id: 'vet_officer_02',
      issued_by_daph_id: 'usr_daph_001',
      instruction_summary: 'Vector control advisory.',
      status: 'ACKNOWLEDGED',
      version: 2,
      created_at: '2026-08-21T09:00:00Z',
      updated_at: '2026-08-21T11:00:00Z',
      acknowledged_at: '2026-08-21T11:00:00Z',
    },
    {
      follow_up_id: 'ffu_003',
      forecast_id: 'fdr_003',
      disease: 'FMD',
      district: 'Gampaha',
      target_year: 2026,
      target_month: 8,
      forecast_risk_level: 'HIGH',
      forecast_probability_pct: 90,
      operational_priority: 'HIGH',
      assigned_vet_id: 'vet_officer_03',
      issued_by_daph_id: 'usr_daph_001',
      instruction_summary: 'Cattle movement inspection.',
      status: 'ACTION_IN_PROGRESS',
      version: 3,
      created_at: '2026-08-19T08:00:00Z',
      updated_at: '2026-08-22T14:00:00Z',
      acknowledged_at: '2026-08-19T10:00:00Z',
      action_started_at: '2026-08-22T14:00:00Z',
    },
    {
      follow_up_id: 'ffu_004',
      forecast_id: 'fdr_004',
      disease: 'LSD',
      district: 'Kandy',
      target_year: 2026,
      target_month: 7,
      forecast_risk_level: 'LOW',
      forecast_probability_pct: 20,
      operational_priority: 'LOW',
      assigned_vet_id: 'vet_officer_04',
      issued_by_daph_id: 'usr_daph_001',
      instruction_summary: 'Routine clinical check.',
      status: 'COMPLETED',
      version: 4,
      created_at: '2026-07-01T08:00:00Z',
      updated_at: '2026-07-05T16:00:00Z',
      acknowledged_at: '2026-07-01T09:00:00Z',
      action_started_at: '2026-07-02T08:00:00Z',
      completed_at: '2026-07-05T16:00:00Z',
    },
    {
      follow_up_id: 'ffu_005',
      forecast_id: 'fdr_005',
      disease: 'FMD',
      district: 'Batticaloa',
      target_year: 2026,
      target_month: 8,
      forecast_risk_level: 'HIGH',
      forecast_probability_pct: 88,
      operational_priority: 'HIGH',
      assigned_vet_id: 'vet_officer_05',
      issued_by_daph_id: 'usr_daph_001',
      instruction_summary: 'Vaccine supply request.',
      status: 'ESCALATED',
      version: 2,
      created_at: '2026-08-15T08:00:00Z',
      updated_at: '2026-08-16T12:00:00Z',
      escalated_at: '2026-08-16T12:00:00Z',
      escalation_reason: 'Regional vaccine quota exceeded.',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    workflowApi.listFollowUps.mockResolvedValue({ follow_ups: sampleFollowUps });
  });

  // 1. Authorization Tests
  describe('Authorization Gating', () => {
    it('renders workspace for valid DAPH_OFFICIAL context', async () => {
      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /Follow-Up Monitoring/i, level: 1 })).toBeInTheDocument();
      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenCalledWith(
          expect.any(Object),
          expect.objectContaining({
            actorContext: { actor_id: 'usr_daph_001', role: 'DAPH_OFFICIAL' },
          })
        );
      });
    });

    it('denies access to Veterinary Officer context', () => {
      render(<DaphFollowUpMonitoring viewerContext={validVetContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Follow-Up Monitoring is available only to authorized DAPH Officials/i)).toBeInTheDocument();
      expect(workflowApi.listFollowUps).not.toHaveBeenCalled();
    });

    it('denies access to Farmer context', () => {
      render(<DaphFollowUpMonitoring viewerContext={validFarmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(workflowApi.listFollowUps).not.toHaveBeenCalled();
    });

    it('denies access when viewerContext is missing or invalid', () => {
      render(<DaphFollowUpMonitoring viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(workflowApi.listFollowUps).not.toHaveBeenCalled();
    });

    it('denies access when userId is blank', () => {
      const blankUserContext = { ...validDaphContext, userId: '   ' };
      render(<DaphFollowUpMonitoring viewerContext={blankUserContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(workflowApi.listFollowUps).not.toHaveBeenCalled();
    });
  });

  // 2. Query & Filtering Tests
  describe('Query & Scoping Behavior', () => {
    it('queries listFollowUps with DAPH actor context and supported filters', async () => {
      const { container } = render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenCalledTimes(1);
      });

      // Select status filter
      const statusSelect = container.querySelector('select[name="status"]');
      fireEvent.change(statusSelect, { target: { value: 'ISSUED' } });

      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'ISSUED' }),
          expect.any(Object)
        );
      });
    });

    it('resets query filters cleanly via Reset Filters button', async () => {
      const { container } = render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenCalled();
      });

      const diseaseSelect = container.querySelector('select[name="disease"]');
      fireEvent.change(diseaseSelect, { target: { value: 'FMD' } });

      const resetButton = screen.getByRole('button', { name: /Reset Filters/i });
      fireEvent.click(resetButton);

      expect(diseaseSelect.value).toBe('');
    });

    it('handles empty response list without error', async () => {
      workflowApi.listFollowUps.mockResolvedValueOnce({ follow_ups: [] });
      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText(/No Follow-Up Records Found/i)).toBeInTheDocument();
      });
    });

    it('displays sanitized error message when query fails', async () => {
      workflowApi.listFollowUps.mockRejectedValueOnce(
        new Error('API Error 500: Database C:\\secret\\db.sqlite failed')
      );
      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText(/Database \[redacted-path\] failed/i)).toBeInTheDocument();
        expect(screen.queryByText(/secret/i)).not.toBeInTheDocument();
      });
    });
  });

  // 3. Summary & Detail Rendering
  describe('Workspace Layout & Summary Statistics', () => {
    it('calculates summary card metrics accurately from loaded records', async () => {
      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('ffu_001')).toBeInTheDocument();
      });

      expect(screen.getByText('Total Items')).toBeInTheDocument();
    });

    it('opens record detail drawer and displays immutable forecast snapshot and timeline', async () => {
      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('ffu_001')).toBeInTheDocument();
      });

      const row = screen.getByText('ffu_001').closest('tr');
      const detailBtn = within(row).getByRole('button', { name: /Details/i });
      fireEvent.click(detailBtn);

      expect(screen.getByText(/Scientific Forecast Snapshot \(Read-Only\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Lifecycle Timeline/i)).toBeInTheDocument();
      expect(screen.getByText(/Targeted FMD ring vaccination/i)).toBeInTheDocument();
    });
  });

  // 4. Action Matrix & Cancellation Flow
  describe('DAPH Action Matrix & Cancel Confirmation', () => {
    it('shows Cancel button ONLY for active follow-ups (ISSUED, ACKNOWLEDGED, ACTION_IN_PROGRESS)', async () => {
      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('ffu_001')).toBeInTheDocument();
      });

      // Select ffu_001 (ISSUED) -> Cancel available
      const row = screen.getByText('ffu_001').closest('tr');
      const detailBtn = within(row).getByRole('button', { name: /Details/i });
      fireEvent.click(detailBtn);
      expect(screen.getByRole('button', { name: /Cancel Follow-Up/i })).toBeInTheDocument();
    });

    it('hides Cancel button for terminal follow-ups (COMPLETED, ESCALATED)', async () => {
      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('ffu_004')).toBeInTheDocument();
      });

      // ffu_004 is COMPLETED
      const row = screen.getByText('ffu_004').closest('tr');
      const detailBtn = within(row).getByRole('button', { name: /Details/i });
      fireEvent.click(detailBtn);
      expect(screen.queryByRole('button', { name: /Cancel Follow-Up/i })).not.toBeInTheDocument();
      expect(screen.getByText(/No DAPH mutation controls available for terminal status 'COMPLETED'/i)).toBeInTheDocument();
    });

    it('opens cancellation confirmation modal and handles cancellation workflow', async () => {
      const updatedCancelledRecord = {
        ...sampleFollowUps[0],
        status: 'CANCELLED',
        version: 2,
        cancelled_at: '2026-08-23T15:00:00Z',
      };
      workflowApi.cancelFollowUp.mockResolvedValueOnce(updatedCancelledRecord);

      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('ffu_001')).toBeInTheDocument();
      });

      // Open detail drawer for ffu_001
      const row = screen.getByText('ffu_001').closest('tr');
      const detailBtn = within(row).getByRole('button', { name: /Details/i });
      fireEvent.click(detailBtn);

      // Click Cancel Follow-Up button
      const cancelBtn = screen.getByRole('button', { name: /Cancel Follow-Up/i });
      fireEvent.click(cancelBtn);

      // Verify Modal opens with warning text
      expect(screen.getByRole('heading', { name: /Confirm Cancellation/i })).toBeInTheDocument();
      expect(screen.getByText(/It does not guarantee physical field action reversal/i)).toBeInTheDocument();

      // Click Confirm Cancel
      const confirmBtn = screen.getByRole('button', { name: /Confirm Cancel/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(workflowApi.cancelFollowUp).toHaveBeenCalledWith(
          'ffu_001',
          1,
          expect.objectContaining({
            actorContext: { actor_id: 'usr_daph_001', role: 'DAPH_OFFICIAL' },
          })
        );
      });
    });
  });

  // 5. Concurrency & Error Sanitization
  describe('Optimistic Concurrency & Error Sanitization', () => {
    it('handles 409 lock conflict on cancel and provides Refresh button', async () => {
      const conflictErrorObj = { message: 'Conflict', status: 409 };
      workflowApi.cancelFollowUp.mockRejectedValueOnce(conflictErrorObj);

      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('ffu_001')).toBeInTheDocument();
      });

      const row = screen.getByText('ffu_001').closest('tr');
      const detailBtn = within(row).getByRole('button', { name: /Details/i });
      fireEvent.click(detailBtn);

      const cancelBtn = screen.getByRole('button', { name: /Cancel Follow-Up/i });
      fireEvent.click(cancelBtn);

      const confirmBtn = screen.getByRole('button', { name: /Confirm Cancel/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(screen.getByText(/Optimistic lock conflict: This follow-up was updated elsewhere/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Refresh Record/i })).toBeInTheDocument();
      });
    });

    it('refreshes record on 409 conflict recovery click', async () => {
      const freshRecord = { ...sampleFollowUps[0], version: 2, status: 'ACKNOWLEDGED' };
      workflowApi.getFollowUp.mockResolvedValueOnce(freshRecord);

      // Trigger state with conflict error by rejecting cancel
      workflowApi.cancelFollowUp.mockRejectedValueOnce({ message: 'Conflict', status: 409 });

      render(<DaphFollowUpMonitoring viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('ffu_001')).toBeInTheDocument();
      });

      const row = screen.getByText('ffu_001').closest('tr');
      const detailBtn = within(row).getByRole('button', { name: /Details/i });
      fireEvent.click(detailBtn);

      fireEvent.click(screen.getByRole('button', { name: /Cancel Follow-Up/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm Cancel/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Refresh Record/i })).toBeInTheDocument();
      });

      // Click Refresh Record
      fireEvent.click(screen.getByRole('button', { name: /Refresh Record/i }));

      await waitFor(() => {
        expect(workflowApi.getFollowUp).toHaveBeenCalledWith(
          'ffu_001',
          expect.objectContaining({
            actorContext: { actor_id: 'usr_daph_001', role: 'DAPH_OFFICIAL' },
          })
        );
      });
    });
  });
});
