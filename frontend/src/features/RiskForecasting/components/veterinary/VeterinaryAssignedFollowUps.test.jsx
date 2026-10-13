import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { VeterinaryAssignedFollowUps, sanitizeErrorMessage } from './VeterinaryAssignedFollowUps.jsx';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext.js';
import * as workflowApi from '../../services/riskForecastingWorkflowApi.js';

// Mock workflow API functions
vi.mock('../../services/riskForecastingWorkflowApi.js', async () => {
  const actual = await vi.importActual('../../services/riskForecastingWorkflowApi.js');
  return {
    ...actual,
    listFollowUps: vi.fn(),
    getFollowUp: vi.fn(),
    acknowledgeFollowUp: vi.fn(),
    startFollowUpAction: vi.fn(),
    completeFollowUp: vi.fn(),
    escalateFollowUp: vi.fn(),
  };
});

describe('VeterinaryAssignedFollowUps Component', () => {
  const validVetContext = {
    userId: 'usr_vet_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Jaffna'],
      assignedFarmIds: [],
    },
    permissions: {
      manageAlerts: true,
      recordResponse: true,
    },
  };

  const multiDistrictVetContext = {
    userId: 'usr_vet_002',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.PROVINCE,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Jaffna', 'Kilinochchi'],
      assignedFarmIds: [],
    },
    permissions: {
      manageAlerts: true,
      recordResponse: true,
    },
  };

  const mockFollowUps = [
    {
      follow_up_id: 'FOL-001',
      forecast_id: 'FC-101',
      disease: 'FMD',
      district: 'Jaffna',
      target_year: 2026,
      target_month: 9,
      forecast_risk_level: 'HIGH',
      probability: 0.623,
      predicted_severity: 'LOW',
      fallback_applied: true,
      operational_priority: 'HIGH',
      status: 'ISSUED',
      instruction_summary: 'Deploy emergency ring vaccination batch.',
      assigned_vet_id: 'usr_vet_001',
      issued_by_daph_id: 'daph_official_01',
      version: 1,
      created_at: '2026-08-20T10:00:00Z',
      external_resource_request_id: null,
    },
    {
      follow_up_id: 'FOL-002',
      forecast_id: 'FC-102',
      disease: 'LSD',
      district: 'Kandy',
      target_year: 2026,
      target_month: 9,
      forecast_risk_level: 'MEDIUM',
      probability: 0.456,
      predicted_severity: 'MEDIUM',
      fallback_applied: false,
      operational_priority: 'MEDIUM',
      status: 'ACKNOWLEDGED',
      instruction_summary: 'Inspect vector breeding controls in Sector 4.',
      assigned_vet_id: 'usr_vet_001',
      issued_by_daph_id: 'daph_official_01',
      version: 2,
      created_at: '2026-08-21T09:00:00Z',
      acknowledged_at: '2026-08-21T11:00:00Z',
      external_resource_request_id: 'RES-VEC-99',
    },
    {
      follow_up_id: 'FOL-003',
      forecast_id: 'FC-103',
      disease: 'FMD',
      district: 'Galle',
      target_year: 2026,
      target_month: 8,
      risk_level: 'HIGH',
      probability_pct: 82.0,
      predicted_severity: 'CRITICAL',
      operational_priority: 'HIGH',
      status: 'ACTION_IN_PROGRESS',
      instruction_summary: 'Conduct movement restrictions enforcement.',
      assigned_vet_id: 'usr_vet_001',
      issued_by_daph_id: 'daph_official_01',
      version: 3,
      created_at: '2026-08-15T08:00:00Z',
      acknowledged_at: '2026-08-15T09:00:00Z',
      action_started_at: '2026-08-15T10:00:00Z',
      external_resource_request_id: null,
    },
    {
      follow_up_id: 'FOL-004',
      forecast_id: 'FC-104',
      disease: 'LSD',
      district: 'Matara',
      target_year: 2026,
      target_month: 7,
      risk_level: 'LOW',
      probability_pct: 12.0,
      predicted_severity: 'LOW',
      operational_priority: 'LOW',
      status: 'COMPLETED',
      instruction_summary: 'Routine sentinel herd testing.',
      assigned_vet_id: 'usr_vet_001',
      issued_by_daph_id: 'daph_official_01',
      version: 4,
      created_at: '2026-07-01T08:00:00Z',
      completed_at: '2026-07-05T16:00:00Z',
    },
    {
      follow_up_id: 'FOL-005',
      forecast_id: 'FC-105',
      disease: 'FMD',
      district: 'Trincomalee',
      target_year: 2026,
      target_month: 6,
      risk_level: 'HIGH',
      probability_pct: 91.0,
      predicted_severity: 'SEVERE',
      operational_priority: 'HIGH',
      status: 'ESCALATED',
      instruction_summary: 'Border quarantine checkpoint request.',
      assigned_vet_id: 'usr_vet_001',
      issued_by_daph_id: 'daph_official_01',
      version: 2,
      created_at: '2026-06-10T08:00:00Z',
      escalated_at: '2026-06-11T14:00:00Z',
      escalation_reason: 'Insufficient personnel for 24/7 border enforcement.',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    workflowApi.listFollowUps.mockResolvedValue({ follow_ups: mockFollowUps });
  });

  describe('Authorization & Access Control', () => {
    it('renders AccessContextUnavailable when viewerContext is missing or null', () => {
      render(<VeterinaryAssignedFollowUps viewerContext={null} />);
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('denies FARMER role access', () => {
      const farmerContext = {
        userId: 'usr_farmer_01',
        role: ROLES.FARMER,
      };
      render(<VeterinaryAssignedFollowUps viewerContext={farmerContext} />);
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('denies DAPH_OFFICIAL role access', () => {
      const daphContext = {
        userId: 'usr_daph_01',
        role: ROLES.DAPH_OFFICIAL,
      };
      render(<VeterinaryAssignedFollowUps viewerContext={daphContext} />);
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('denies VETERINARY_OFFICER with blank userId', () => {
      const invalidVet = {
        userId: '   ',
        role: ROLES.VETERINARY_OFFICER,
      };
      render(<VeterinaryAssignedFollowUps viewerContext={invalidVet} />);
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('renders workspace for valid VETERINARY_OFFICER', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      expect(screen.getByRole('heading', { level: 1, name: /Assigned Follow-Ups/i })).toBeInTheDocument();
      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenCalledWith(
          expect.objectContaining({ assigned_vet_id: 'usr_vet_001' }),
          expect.objectContaining({ actorContext: expect.any(Object) })
        );
      });
    });
  });

  describe('Querying & Scoping', () => {
    it('scopes listFollowUps query by assigned_vet_id and passes actorContext', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenCalledWith(
          { assigned_vet_id: 'usr_vet_001' },
          expect.objectContaining({
            actorContext: expect.objectContaining({ userId: 'usr_vet_001', role: 'VETERINARY_OFFICER' }),
            signal: expect.any(Object),
          })
        );
      });
    });

    it('handles empty query response without fabricating tasks', async () => {
      workflowApi.listFollowUps.mockResolvedValueOnce({ follow_ups: [] });
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText(/No Assigned Follow-Ups Found/i)).toBeInTheDocument();
      });
    });

    it('displays error banner and retry button on query failure', async () => {
      workflowApi.listFollowUps.mockRejectedValueOnce(new Error('Database connection failed C:\\secret\\path.py'));
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/Database connection failed <redacted_path>/i)).toBeInTheDocument();
      });

      const retryBtn = screen.getByRole('button', { name: /Retry/i });
      workflowApi.listFollowUps.mockResolvedValueOnce({ follow_ups: mockFollowUps });
      fireEvent.click(retryBtn);

      await waitFor(() => {
        expect(screen.getByText('Deploy emergency ring vaccination batch.')).toBeInTheDocument();
      });
    });
  });

  describe('Lifecycle & Race Condition Guard', () => {
    it('does not display an error banner when fetch is aborted with AbortError', async () => {
      const abortError = new Error('The operation was aborted.');
      abortError.name = 'AbortError';
      workflowApi.listFollowUps.mockRejectedValueOnce(abortError);

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        // We wait briefly and expect no alert
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      });
    });

    it('does not display an error banner when fetch fails with "signal is aborted without reason"', async () => {
      workflowApi.listFollowUps.mockRejectedValueOnce(new Error('signal is aborted without reason'));

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      });
    });

    it('handles React StrictMode/double-mount behavior without false errors', async () => {
      // First mount throws AbortError (simulating immediate unmount)
      const abortError = new Error('AbortError');
      abortError.name = 'AbortError';
      workflowApi.listFollowUps.mockRejectedValueOnce(abortError);
      // Second mount succeeds
      workflowApi.listFollowUps.mockResolvedValueOnce({ follow_ups: mockFollowUps });

      render(
        <React.StrictMode>
          <VeterinaryAssignedFollowUps viewerContext={validVetContext} />
        </React.StrictMode>
      );

      await waitFor(() => {
        expect(screen.getByText('Deploy emergency ring vaccination batch.')).toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      });
    });

    it('prevents a stale failed request from overwriting a later successful request', async () => {
      let resolveFirst;
      let rejectFirst;
      const firstPromise = new Promise((res, rej) => {
        resolveFirst = res;
        rejectFirst = rej;
      });

      let resolveSecond;
      const secondPromise = new Promise((res) => {
        resolveSecond = res;
      });

      workflowApi.listFollowUps
        .mockReturnValueOnce(firstPromise)
        .mockReturnValueOnce(secondPromise);

      const { unmount, rerender } = render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      // Trigger second fetch by rerendering with a different context or forcing a re-fetch
      rerender(<VeterinaryAssignedFollowUps viewerContext={multiDistrictVetContext} />);

      // Resolve second promise successfully
      resolveSecond({ follow_ups: mockFollowUps });

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      // Reject first promise with a real error (not abort)
      rejectFirst(new Error('Stale API Error'));

      // Wait to ensure the error doesn't render
      await new Promise(r => setTimeout(r, 50));
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('does not update state if unmounted before fetch completes', async () => {
      let resolveFetch;
      const fetchPromise = new Promise((res) => {
        resolveFetch = res;
      });
      workflowApi.listFollowUps.mockReturnValueOnce(fetchPromise);

      const { unmount } = render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      unmount();

      resolveFetch({ follow_ups: mockFollowUps });

      // Wait to ensure no unhandled act warning or state update on unmounted component
      await new Promise(r => setTimeout(r, 50));
    });

    it('renders only the sanitized message for a genuine failure', async () => {
      workflowApi.listFollowUps.mockRejectedValueOnce(new Error('SyntaxError: Unexpected token < in JSON at position 0'));
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/SyntaxError: Unexpected token < in JSON at position 0/i)).toBeInTheDocument();
      });
    });

    it('renders the expected empty state for an empty successful response', async () => {
      workflowApi.listFollowUps.mockResolvedValueOnce({ follow_ups: [] });
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText(/No Assigned Follow-Ups Found/i)).toBeInTheDocument();
      });
    });
  });

  describe('Workspace Layout & Summary Statistics', () => {
    it('calculates total, awaiting ack, in progress, completed, and escalated summary counts correctly', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Total Assigned')).toBeInTheDocument();
      });

      // Total: 5, ISSUED: 1, IN_PROGRESS: 2 (1 ACK + 1 IN_PROGRESS), COMPLETED: 1, ESCALATED: 1
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('filters records by status select', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const statusSelect = screen.getByLabelText(/Status/i);
      fireEvent.change(statusSelect, { target: { value: 'ISSUED' } });

      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenLastCalledWith(
          expect.objectContaining({ status: 'ISSUED' }),
          expect.any(Object)
        );
      });
    });

    it('filters records by disease select', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const diseaseSelect = screen.getByLabelText(/Disease/i);
      fireEvent.change(diseaseSelect, { target: { value: 'FMD' } });

      await waitFor(() => {
        expect(workflowApi.listFollowUps).toHaveBeenLastCalledWith(
          expect.objectContaining({ disease: 'FMD' }),
          expect.any(Object)
        );
      });
    });

    it('shows district filter dropdown only when Vet has multiple authorized districts', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={multiDistrictVetContext} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/District/i)).toBeInTheDocument();
      });
    });

    it('resets filters when Reset Filters button is clicked', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const statusSelect = screen.getByLabelText(/Status/i);
      fireEvent.change(statusSelect, { target: { value: 'COMPLETED' } });

      const resetBtn = screen.getByRole('button', { name: /Reset Filters/i });
      fireEvent.click(resetBtn);

      expect(statusSelect.value).toBe('ALL');
    });
  });

  describe('Detail Panel & Scientific Snapshot', () => {
    it('opens detail panel when View Details button is clicked', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);

      expect(screen.getByRole('heading', { name: /Follow-Up Details/i })).toBeInTheDocument();

      expect(screen.getAllByText('Deploy emergency ring vaccination batch.').length).toBeGreaterThan(0);
      expect(screen.getByText('Immutable Scientific Forecast Snapshot')).toBeInTheDocument();
      expect(screen.getAllByText('HIGH').length).toBeGreaterThan(0);
      expect(screen.getByText('62.3%')).toBeInTheDocument();
      expect(screen.getAllByText('LOW').length).toBeGreaterThan(0);
      expect(screen.getByText('Historical proxy data used')).toBeInTheDocument();
    });

    it('renders correct snapshot values for FOL-002 and absent proxy notice', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Kandy')).toBeInTheDocument();
        expect(screen.queryByText('FOL-002')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[1]);

      expect(screen.getAllByText('MEDIUM').length).toBeGreaterThan(0);
      expect(screen.getByText('45.6%')).toBeInTheDocument();
      expect(screen.queryByText('Historical proxy data used')).not.toBeInTheDocument();
    });

    it('verifies external_resource_request_id field is completely absent from DOM', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]); // FOL-001 has no resource id

      expect(screen.queryByText('External Resource')).not.toBeInTheDocument();
      expect(screen.queryByText('Not linked')).not.toBeInTheDocument();
    });

    it('verifies external_resource_request_id is never displayed even when present', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Kandy')).toBeInTheDocument();
        expect(screen.queryByText('FOL-002')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[1]); // FOL-002 has RES-VEC-99

      expect(screen.queryByText('External Resource')).not.toBeInTheDocument();
      expect(screen.queryByText('RES-VEC-99')).not.toBeInTheDocument();
    });
  });

  describe('State-Machine Transitions & Action Matrix', () => {
    it('renders Acknowledge and Escalate buttons for ISSUED record', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]); // FOL-001 is ISSUED

      expect(screen.getByRole('button', { name: /Acknowledge/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Escalate/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Start Action/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^Complete$/i })).not.toBeInTheDocument();
    });

    it('executes acknowledgeFollowUp with version payload when Acknowledge is confirmed', async () => {
      workflowApi.acknowledgeFollowUp.mockResolvedValueOnce({
        ...mockFollowUps[0],
        status: 'ACKNOWLEDGED',
        version: 2,
      });

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);

      fireEvent.click(screen.getByRole('button', { name: /Acknowledge/i }));

      const dialogs = screen.getAllByRole('dialog');
      expect(dialogs.length).toBeGreaterThan(0);
      expect(screen.getByText(/Confirm Acknowledgement/i)).toBeInTheDocument();

      const confirmBtn = screen.getByRole('button', { name: /Confirm/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(workflowApi.acknowledgeFollowUp).toHaveBeenCalledWith(
          'FOL-001',
          expect.objectContaining({
            version: 1,
            actorContext: expect.objectContaining({ userId: 'usr_vet_001' }),
          })
        );
      });
    });

    it('renders Start Action and Escalate buttons for ACKNOWLEDGED record', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Kandy')).toBeInTheDocument();
        expect(screen.queryByText('FOL-002')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[1]); // FOL-002 is ACKNOWLEDGED

      expect(screen.getByRole('button', { name: /Start Action/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Escalate/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Acknowledge/i })).not.toBeInTheDocument();
    });

    it('executes startFollowUpAction when Start Action is confirmed', async () => {
      workflowApi.startFollowUpAction.mockResolvedValueOnce({
        ...mockFollowUps[1],
        status: 'ACTION_IN_PROGRESS',
        version: 3,
      });

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Kandy')).toBeInTheDocument();
        expect(screen.queryByText('FOL-002')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[1]);

      fireEvent.click(screen.getByRole('button', { name: /Start Action/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

      await waitFor(() => {
        expect(workflowApi.startFollowUpAction).toHaveBeenCalledWith(
          'FOL-002',
          expect.objectContaining({
            version: 2,
            actorContext: expect.objectContaining({ userId: 'usr_vet_001' }),
          })
        );
      });
    });

    it('renders Complete and Escalate buttons for ACTION_IN_PROGRESS record', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Galle')).toBeInTheDocument();
        expect(screen.queryByText('FOL-003')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[2]); // FOL-003 is ACTION_IN_PROGRESS

      expect(screen.getByRole('button', { name: /^Complete$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Escalate/i })).toBeInTheDocument();
    });

    it('executes completeFollowUp with disclaimer notice when Complete is confirmed', async () => {
      workflowApi.completeFollowUp.mockResolvedValueOnce({
        ...mockFollowUps[2],
        status: 'COMPLETED',
        version: 4,
      });

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Galle')).toBeInTheDocument();
        expect(screen.queryByText('FOL-003')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[2]);

      fireEvent.click(screen.getByRole('button', { name: /^Complete$/i }));

      expect(screen.getByText(/Does not claim disease eradication or farmer notification/i)).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

      await waitFor(() => {
        expect(workflowApi.completeFollowUp).toHaveBeenCalledWith(
          'FOL-003',
          expect.objectContaining({
            version: 3,
            actorContext: expect.objectContaining({ userId: 'usr_vet_001' }),
          })
        );
      });
    });

    it('renders read-only notice for COMPLETED, CANCELLED, and ESCALATED records without action buttons', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Matara')).toBeInTheDocument();
        expect(screen.queryByText('FOL-004')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[3]); // FOL-004 is COMPLETED

      expect(screen.getByText(/Task marked complete. No further state transitions available/i)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Acknowledge/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Escalate/i })).not.toBeInTheDocument();
    });
  });

  describe('Escalation Requirements', () => {
    it('requires minimum 5 characters for escalation reason', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);

      fireEvent.click(screen.getByRole('button', { name: /Escalate/i }));

      const textarea = screen.getByPlaceholderText(/Enter explicit operational reason/i);
      fireEvent.change(textarea, { target: { value: 'Too' } }); // 3 chars

      fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

      expect(screen.getByText(/reason must be at least 5 characters long/i)).toBeInTheDocument();
      expect(workflowApi.escalateFollowUp).not.toHaveBeenCalled();
    });

    it('executes escalateFollowUp with version and reason when valid', async () => {
      workflowApi.escalateFollowUp.mockResolvedValueOnce({
        ...mockFollowUps[0],
        status: 'ESCALATED',
        version: 2,
        escalation_reason: 'Vaccine supply exhausted in central depot.',
      });

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);

      fireEvent.click(screen.getByRole('button', { name: /Escalate/i }));

      const textarea = screen.getByPlaceholderText(/Enter explicit operational reason/i);
      fireEvent.change(textarea, { target: { value: 'Vaccine supply exhausted in central depot.' } });

      fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

      await waitFor(() => {
        expect(workflowApi.escalateFollowUp).toHaveBeenCalledWith(
          'FOL-001',
          expect.objectContaining({
            version: 1,
            reason: 'Vaccine supply exhausted in central depot.',
            actorContext: expect.objectContaining({ userId: 'usr_vet_001' }),
          })
        );
      });
    });
  });

  describe('Optimistic Concurrency (HTTP 409) & Error Handling', () => {
    it('displays controlled warning banner and Refresh Follow-Up button on HTTP 409 conflict', async () => {
      const error409 = new Error('API Error 409: Record version conflict');
      error409.status = 409;
      workflowApi.acknowledgeFollowUp.mockRejectedValueOnce(error409);

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);

      fireEvent.click(screen.getByRole('button', { name: /Acknowledge/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

      await waitFor(() => {
        expect(screen.getByText(/Conflict Detected \(409\)/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Refresh Follow-Up/i })).toBeInTheDocument();
      });
    });

    it('fetches latest record via getFollowUp when Refresh Follow-Up is clicked after 409', async () => {
      const error409 = new Error('API Error 409: Record version conflict');
      error409.status = 409;
      workflowApi.acknowledgeFollowUp.mockRejectedValueOnce(error409);

      workflowApi.getFollowUp.mockResolvedValueOnce({
        ...mockFollowUps[0],
        version: 3,
        status: 'ACKNOWLEDGED',
      });

      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText('Jaffna')).toBeInTheDocument();
        expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
      });

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);

      fireEvent.click(screen.getByRole('button', { name: /Acknowledge/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Refresh Follow-Up/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Refresh Follow-Up/i }));

      await waitFor(() => {
        expect(workflowApi.getFollowUp).toHaveBeenCalledWith(
          'FOL-001',
          expect.objectContaining({ actorContext: expect.objectContaining({ userId: 'usr_vet_001' }) })
        );
        expect(screen.queryByText(/Conflict Detected \(409\)/i)).not.toBeInTheDocument();
      });
    });

    it('sanitizes error messages removing system paths and bearer tokens', () => {
      const rawError = 'Error at C:\\Users\\secret\\app.js: Bearer eyJhbGciOiJIUzI1Ni... DB mongodb://user:pass@localhost';
      const sanitized = sanitizeErrorMessage(rawError);
      expect(sanitized).not.toContain('C:\\Users\\secret\\app.js');
      expect(sanitized).not.toContain('mongodb://user:pass@localhost');
      expect(sanitized).toContain('<redacted_path>');
      expect(sanitized).toContain('<redacted_credentials>');
      expect(sanitized).toContain('<redacted_db_url>');
    });
  });

  describe('UI Defect Remediation Validation', () => {
    it('proves raw Vet Mongo ID is absent from DOM', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      expect(screen.queryByText('usr_vet_001')).not.toBeInTheDocument();
      expect(screen.queryByText(/Officer ID:/)).not.toBeInTheDocument();
    });

    it('proves raw follow-up ID is absent from DOM', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);
      expect(screen.queryByText('FOL-001')).not.toBeInTheDocument();
    });

    it('proves raw forecast ID is absent from DOM', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);
      expect(screen.queryByText('FC-101')).not.toBeInTheDocument();
    });

    it('proves the hidden follow-up ID is still passed to mocked acknowledge', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]); // FOL-001
      fireEvent.click(screen.getByRole('button', { name: /Acknowledge/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));
      await waitFor(() => {
        expect(workflowApi.acknowledgeFollowUp).toHaveBeenCalledWith('FOL-001', expect.any(Object));
      });
    });

    it('proves opening View Details performs zero POST/mutation calls', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());

      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);

      expect(workflowApi.acknowledgeFollowUp).not.toHaveBeenCalled();
      expect(workflowApi.startFollowUpAction).not.toHaveBeenCalled();
      expect(workflowApi.completeFollowUp).not.toHaveBeenCalled();
      expect(workflowApi.escalateFollowUp).not.toHaveBeenCalled();
    });

    it('proves Details modal uses role="dialog" and aria-modal="true"', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);
      const dialogs = screen.getAllByRole('dialog');
      expect(dialogs[0]).toHaveAttribute('aria-modal', 'true');
    });

    it('proves modal contains centered responsive layout classes', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);
      const dialogWrapper = screen.getAllByRole('dialog')[0];
      expect(dialogWrapper).toHaveClass('fixed', 'inset-0', 'flex', 'items-center', 'justify-center');
    });

    it('proves modal close button works', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);
      expect(screen.getByRole('heading', { name: /Follow-Up Details/i })).toBeInTheDocument();

      const closeBtn = screen.getByRole('button', { name: /Close detail modal/i });
      fireEvent.click(closeBtn);

      expect(screen.queryByRole('heading', { name: /Follow-Up Details/i })).not.toBeInTheDocument();
    });

    it('proves Guardrails box is absent', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      expect(screen.queryByText(/Operational Workflow Semantics & Guardrails/i)).not.toBeInTheDocument();
    });

    it('proves Record Version field is absent', async () => {
      render(<VeterinaryAssignedFollowUps viewerContext={validVetContext} />);
      await waitFor(() => expect(screen.getByText('Jaffna')).toBeInTheDocument());
      const viewBtns = screen.getAllByRole('button', { name: /View Details/i });
      fireEvent.click(viewBtns[0]);
      expect(screen.queryByText(/Record Version:/i)).not.toBeInTheDocument();
    });
  });
});
