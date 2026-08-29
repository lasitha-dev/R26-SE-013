import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { DaphFollowUpComposer } from './DaphFollowUpComposer';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as api from '../../services/riskForecastingWorkflowApi';

vi.mock('../../services/riskForecastingWorkflowApi', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    listEligibleFollowUpVets: vi.fn(),
    issueFollowUp: vi.fn(),
    listFollowUps: vi.fn(),
  };
});

describe('DaphFollowUpComposer Component', () => {
  const mockDaphContext = {
    userId: 'daph_official_01',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      authorizedDistricts: ['Anuradhapura', 'Nuwara Eliya'],
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

  const mockFarmerContext = {
    userId: 'farmer_01',
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

  const mockVetContext = {
    userId: 'vet_officer_01',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: ['FARM_01'],
    },
    permissions: {
      viewDataQuality: true,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    },
  };

  const mockForecastRecord = {
    forecast_id: 'fc_anu_2026_10_01',
    district: 'Anuradhapura',
    disease: 'FMD',
    target_year: 2026,
    target_month: 10,
    risk_level: 'HIGH',
    probability: 0.85,
    predicted_severity: 'HIGH',
    data_quality: 'HIGH_QUALITY',
    fallback_applied: false,
    status: 'OFFICIAL',
  };

  const mockVetsResponse = {
    district: 'Anuradhapura',
    total_count: 2,
    veterinary_officers: [
      {
        vet_id: 'vet_anu_01',
        display_name: 'Dr. Perera',
        assigned_districts: ['Anuradhapura'],
        active: true,
      },
      {
        vet_id: 'vet_anu_02',
        display_name: 'Dr. Silva',
        assigned_districts: ['Anuradhapura'],
        active: true,
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    api.listEligibleFollowUpVets.mockResolvedValue(mockVetsResponse);
    api.listFollowUps.mockResolvedValue({ follow_ups: [], total_count: 0 });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. Authorization Access Gating
  describe('Authorization Access Gating', () => {
    it('renders the composer for a valid DAPH Official viewer', async () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      expect(screen.getByText('Issue Operational Follow-Up')).toBeInTheDocument();
      await waitFor(() => {
        expect(api.listEligibleFollowUpVets).toHaveBeenCalledWith(
          { district: 'Anuradhapura' },
          expect.objectContaining({ actorContext: mockDaphContext })
        );
      });
    });

    it('denies access for FARMER role', () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockFarmerContext}
        />
      );

      expect(screen.queryByText('Issue Operational Follow-Up')).not.toBeInTheDocument();
      expect(screen.getByText(/requires authenticated DAPH_OFFICIAL role/i)).toBeInTheDocument();
      expect(api.listEligibleFollowUpVets).not.toHaveBeenCalled();
    });

    it('denies access for VETERINARY_OFFICER role', () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockVetContext}
        />
      );

      expect(screen.queryByText('Issue Operational Follow-Up')).not.toBeInTheDocument();
      expect(screen.getByText(/requires authenticated DAPH_OFFICIAL role/i)).toBeInTheDocument();
      expect(api.listEligibleFollowUpVets).not.toHaveBeenCalled();
    });

    it('fails closed when viewerContext is missing or null', () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={null}
        />
      );

      expect(screen.queryByText('Issue Operational Follow-Up')).not.toBeInTheDocument();
      expect(screen.getByText(/ViewerContext must be a non-null object/i)).toBeInTheDocument();
      expect(api.listEligibleFollowUpVets).not.toHaveBeenCalled();
    });
  });

  // 2. Persisted Record Guard & Invalid Forecast ID
  describe('Persisted Record Guard & Invalid Forecast ID', () => {
    it('fails closed and renders AccessContextUnavailable when forecastRecord has blank forecast_id', () => {
      const invalidRecord = {
        ...mockForecastRecord,
        forecast_id: '   ',
      };

      render(
        <DaphFollowUpComposer
          forecastRecord={invalidRecord}
          viewerContext={mockDaphContext}
        />
      );

      expect(screen.queryByText('Issue Operational Follow-Up')).not.toBeInTheDocument();
      expect(screen.getByText(/Follow-up issuing requires a valid, persisted ForecastDecisionRecord/i)).toBeInTheDocument();
      expect(api.listEligibleFollowUpVets).not.toHaveBeenCalled();
      expect(api.listFollowUps).not.toHaveBeenCalled();
      expect(api.issueFollowUp).not.toHaveBeenCalled();
    });

    it('fails closed and renders AccessContextUnavailable when forecastRecord is marked isMissingRecord: true', () => {
      const missingRecordPlaceholder = {
        isMissingRecord: true,
        district: 'Colombo',
        disease: 'FMD',
      };

      render(
        <DaphFollowUpComposer
          forecastRecord={missingRecordPlaceholder}
          viewerContext={mockDaphContext}
        />
      );

      expect(screen.queryByText('Issue Operational Follow-Up')).not.toBeInTheDocument();
      expect(screen.getByText(/Follow-up issuing requires a valid, persisted ForecastDecisionRecord/i)).toBeInTheDocument();
      expect(api.listEligibleFollowUpVets).not.toHaveBeenCalled();
      expect(api.listFollowUps).not.toHaveBeenCalled();
      expect(api.issueFollowUp).not.toHaveBeenCalled();
    });
  });

  // 3. Forecast Snapshot Display
  describe('Forecast Snapshot Display', () => {
    it('renders selected official forecast record snapshot fields in read-only mode', async () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      expect(screen.getByText('Anuradhapura')).toBeInTheDocument();
      expect(screen.getByText('FMD')).toBeInTheDocument();
      expect(screen.getByText(/October 2026/)).toBeInTheDocument();
      expect(screen.getAllByText('HIGH').length).toBeGreaterThan(0);
      expect(screen.getByText('85.0%')).toBeInTheDocument();
      expect(screen.getByText('HIGH_QUALITY')).toBeInTheDocument();
      expect(screen.queryByText(/fc_anu_2026_10_01/)).not.toBeInTheDocument();
    });

    it('renders missing values as N/A and does not default missing probability to 0', async () => {
      const incompleteRecord = {
        forecast_id: 'fc_inc_01',
        district: 'Nuwara Eliya',
        disease: 'LSD',
        target_year: 2026,
        target_month: 11,
        risk_level: 'MEDIUM',
        probability: null,
        predicted_severity: null,
        data_quality: null,
        fallback_applied: false,
      };

      render(
        <DaphFollowUpComposer
          forecastRecord={incompleteRecord}
          viewerContext={mockDaphContext}
        />
      );

      expect(screen.getAllByText('N/A').length).toBeGreaterThan(0);
      expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
    });

    it('renders fallback data warning when fallback_applied is true', async () => {
      const fallbackRecord = {
        ...mockForecastRecord,
        fallback_applied: true,
      };

      render(
        <DaphFollowUpComposer
          forecastRecord={fallbackRecord}
          viewerContext={mockDaphContext}
        />
      );

      expect(screen.getByText('Historical proxy data used')).toBeInTheDocument();
    });
  });

  // 4. Eligible Vet Directory Querying
  describe('Eligible Vet Directory Querying', () => {
    it('loads eligible Vets for the canonical district and selects the first active Vet', async () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Dr\. Perera/)).toBeInTheDocument();
        expect(screen.getByText(/Dr\. Silva/)).toBeInTheDocument();
      });
    });

    it('handles empty eligible Vets state by displaying an explanatory message and disabling issue action', async () => {
      api.listEligibleFollowUpVets.mockResolvedValueOnce({
        district: 'Anuradhapura',
        total_count: 0,
        veterinary_officers: [],
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/No active Veterinary Officers currently assigned to Anuradhapura/i)).toBeInTheDocument();
      });

      const nextButton = screen.getByRole('button', { name: /Review & Prepare Issue/i });
      expect(nextButton).toBeDisabled();
    });
  });

  // 5. Operational Instruction Validation & Form Workflow
  describe('Form Validation & Two-Stage Review Workflow', () => {
    it('validates minimum and maximum instruction length, updates remaining characters, and prevents whitespace-only submission', async () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      expect(screen.getByText('500 characters remaining')).toBeInTheDocument();

      // Enter whitespace only
      fireEvent.change(textarea, { target: { value: '   ' } });
      fireEvent.blur(textarea);

      expect(screen.getByText(/Operational instruction is required/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Review & Prepare Issue/i })).toBeDisabled();

      // Enter 3 characters (less than 5)
      fireEvent.change(textarea, { target: { value: 'abc' } });

      expect(screen.getByText(/Instruction must be at least 5 characters long/i)).toBeInTheDocument();
      expect(screen.getByText('497 characters remaining')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Review & Prepare Issue/i })).toBeDisabled();

      // Enter valid instruction (>= 5 chars)
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Review & Prepare Issue/i })).not.toBeDisabled();
    });

    it('navigates to Stage B Review and allows returning to edit without losing draft', async () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });

      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));

      // Review Stage
      expect(screen.getByText('Review Follow-Up Summary Before Issuance')).toBeInTheDocument();
      expect(screen.getByText('Conduct immediate field vaccination drive.')).toBeInTheDocument();
      expect(screen.getByText(/Dr. Perera/)).toBeInTheDocument();


      // Click Back to Edit
      fireEvent.click(screen.getByRole('button', { name: /Back to Edit/i }));

      // Stage 1 restored with draft preserved
      expect(screen.getByPlaceholderText(/Provide specific operational guidance/i)).toHaveValue('Conduct immediate field vaccination drive.');
    });
  });

  // 6. Submission & Idempotency Key & Double Submit Safety
  describe('Submission & Idempotency Key Safety', () => {
    it('submits exact authorized payload with deterministic idempotency key and renders ISSUED success state', async () => {
      api.issueFollowUp.mockResolvedValueOnce({
        follow_up_id: 'fu_anu_999',
        forecast_id: 'fc_anu_2026_10_01',
        assigned_vet_id: 'vet_anu_01',
        instruction_summary: 'Conduct immediate field vaccination drive.',
        operational_priority: 'HIGH',
        status: 'ISSUED',
        created_at: '2026-08-24T10:00:00Z',
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));

      // Confirm & Issue
      fireEvent.click(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i }));

      await waitFor(() => {
        expect(api.issueFollowUp).toHaveBeenCalledWith(
          {
            forecast_id: 'fc_anu_2026_10_01',
            assigned_vet_id: 'vet_anu_01',
            instruction_summary: 'Conduct immediate field vaccination drive.',
            idempotency_key: 'daph-follow-up:daph_official_01:fc_anu_2026_10_01:vet_anu_01',
          },
          expect.objectContaining({ actorContext: mockDaphContext })
        );
      });

      expect(screen.getByText(/Operational Follow-Up Successfully Issued/i)).toBeInTheDocument();

      expect(screen.getByText('ISSUED')).toBeInTheDocument();
    });

    it('prevents double submission on fast double click while pending', async () => {
      let resolveSubmission;
      const pendingPromise = new Promise((resolve) => {
        resolveSubmission = resolve;
      });

      api.issueFollowUp.mockImplementationOnce(() => pendingPromise);

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));

      const confirmButton = screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i });
      fireEvent.click(confirmButton);
      fireEvent.click(confirmButton); // Fast double click

      expect(api.issueFollowUp).toHaveBeenCalledTimes(1);

      // Resolve API call to clean up
      resolveSubmission({
        follow_up_id: 'fu_anu_100',
        forecast_id: 'fc_anu_2026_10_01',
        assigned_vet_id: 'vet_anu_01',
        instruction_summary: 'Conduct immediate field vaccination drive.',
        operational_priority: 'HIGH',
        status: 'ISSUED',
      });

      await waitFor(() => {
        expect(screen.getByText(/Operational Follow-Up Successfully Issued/i)).toBeInTheDocument();
      });
    });

    it('success state does not render generic Issue Another Follow-Up reset control and provides Close button only', async () => {
      api.issueFollowUp.mockResolvedValueOnce({
        follow_up_id: 'fu_anu_999',
        forecast_id: 'fc_anu_2026_10_01',
        assigned_vet_id: 'vet_anu_01',
        instruction_summary: 'Conduct immediate field vaccination drive.',
        operational_priority: 'HIGH',
        status: 'ISSUED',
      });

      const mockClose = vi.fn();

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
          onClose={mockClose}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i }));

      await waitFor(() => {
        expect(screen.getByText(/Operational Follow-Up Successfully Issued/i)).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /Issue Another Follow-Up/i })).not.toBeInTheDocument();
      const closeBtn = screen.getByRole('button', { name: /^Close$/i });
      expect(closeBtn).toBeInTheDocument();

      fireEvent.click(closeBtn);
      expect(mockClose).toHaveBeenCalledTimes(1);
    });

    it('prevents resubmission when already in SUCCESS stage', async () => {
      api.issueFollowUp.mockResolvedValueOnce({
        follow_up_id: 'fu_anu_999',
        forecast_id: 'fc_anu_2026_10_01',
        assigned_vet_id: 'vet_anu_01',
        instruction_summary: 'Conduct immediate field vaccination drive.',
        operational_priority: 'HIGH',
        status: 'ISSUED',
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i }));

      await waitFor(() => {
        expect(screen.getByText(/Operational Follow-Up Successfully Issued/i)).toBeInTheDocument();
      });

      expect(api.issueFollowUp).toHaveBeenCalledTimes(1);
    });
  });

  // 7. Error Handling & Sanitization
  describe('Error Handling & Sanitization', () => {
    it('sanitizes stack traces, paths, and internal details on API errors and preserves draft', async () => {
      api.issueFollowUp.mockRejectedValueOnce({
        message: 'Traceback (most recent call last): File "backend/routes.py", line 45 in execute C:\\Users\\secret\\token',
        statusCode: 500,
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i }));

      await waitFor(() => {
        expect(screen.getByText(/A technical error occurred during follow-up processing/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/Traceback/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/C:\\Users\\secret/i)).not.toBeInTheDocument();

      // Back to edit keeps instruction
      fireEvent.click(screen.getByRole('button', { name: /Back to Edit/i }));
      expect(screen.getByPlaceholderText(/Provide specific operational guidance/i)).toHaveValue('Conduct immediate field vaccination drive.');
    });

    it('handles 409 conflict error cleanly', async () => {
      api.issueFollowUp.mockRejectedValueOnce({
        message: 'Follow-up already exists',
        statusCode: 409,
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i }));

      await waitFor(() => {
        expect(screen.getByText(/Operation conflict: A follow-up matching this operation key or assignment may already exist/i)).toBeInTheDocument();
      });
    });

    it('sanitizes bearer tokens, database connection strings, and raw object strings from error display', async () => {
      api.issueFollowUp.mockRejectedValueOnce({
        message: 'Failed with token Bearer eyJhbGci... mongodb://user:pass@localhost:27017/db [object Object]',
        statusCode: 500,
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i }));

      await waitFor(() => {
        expect(screen.getByText(/A technical error occurred during follow-up processing/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/Bearer/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/mongodb:\/\//i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\[object Object\]/i)).not.toBeInTheDocument();
    });
  });

  // 8. Existing Active Follow-Up Awareness & History Failure
  describe('Existing Active Follow-Up Awareness & History Failure', () => {
    it('displays active follow-up warning banner when active follow-ups exist for the forecast', async () => {
      api.listFollowUps.mockResolvedValueOnce({
        follow_ups: [
          {
            follow_up_id: 'fu_existing_01',
            forecast_id: 'fc_anu_2026_10_01',
            assigned_vet_id: 'vet_anu_01',
            status: 'ACTION_IN_PROGRESS',
          },
        ],
        total_count: 1,
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Active Follow-Up Warning \(1 Active\)/i)).toBeInTheDocument();
        expect(screen.getByText(/ID: fu_existing_01/i)).toBeInTheDocument();
        expect(screen.getByText('ACTION_IN_PROGRESS')).toBeInTheDocument();
      });
    });

    it('renders controlled warning notice when listFollowUps query fails and does not fabricate zero follow-ups', async () => {
      api.listFollowUps.mockRejectedValueOnce({
        message: 'Database query timeout while accessing follow-up ledger',
        statusCode: 500,
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Notice: Unable to verify existing follow-up history/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/Active Follow-Up Warning/i)).not.toBeInTheDocument();
    });

    it('passes exact forecast_id, DAPH actor context, and AbortSignal to listFollowUps', async () => {
      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(api.listFollowUps).toHaveBeenCalledWith(
          { forecast_id: 'fc_anu_2026_10_01' },
          expect.objectContaining({
            actorContext: mockDaphContext,
            signal: expect.any(AbortSignal),
          })
        );
      });
    });

    it('handles terminal status follow-ups without rendering status transition controls', async () => {
      api.listFollowUps.mockResolvedValueOnce({
        follow_ups: [
          {
            follow_up_id: 'fu_done_01',
            forecast_id: 'fc_anu_2026_10_01',
            assigned_vet_id: 'vet_anu_01',
            status: 'COMPLETED',
          },
          {
            follow_up_id: 'fu_canc_01',
            forecast_id: 'fc_anu_2026_10_01',
            assigned_vet_id: 'vet_anu_02',
            status: 'CANCELLED',
          },
        ],
        total_count: 2,
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(api.listFollowUps).toHaveBeenCalled();
      });

      // No status transition buttons (e.g., Acknowledge, Complete, Cancel) should be present
      expect(screen.queryByRole('button', { name: /Acknowledge/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Complete/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Escalate/i })).not.toBeInTheDocument();
    });

    it('success state clearly displays ISSUED status and target officer without claiming farmer delivery or stock allocation', async () => {
      api.issueFollowUp.mockResolvedValueOnce({
        follow_up_id: 'fu_anu_999',
        forecast_id: 'fc_anu_2026_10_01',
        assigned_vet_id: 'vet_anu_01',
        instruction_summary: 'Conduct immediate field vaccination drive.',
        operational_priority: 'HIGH',
        status: 'ISSUED',
      });

      render(
        <DaphFollowUpComposer
          forecastRecord={mockForecastRecord}
          viewerContext={mockDaphContext}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/Assign Active Veterinary Officer/i)).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
      fireEvent.change(textarea, { target: { value: 'Conduct immediate field vaccination drive.' } });
      fireEvent.click(screen.getByRole('button', { name: /Review & Prepare Issue/i }));
      fireEvent.click(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i }));

      await waitFor(() => {
        expect(screen.getByText(/Operational Follow-Up Successfully Issued/i)).toBeInTheDocument();
      });

      expect(screen.getByText('ISSUED')).toBeInTheDocument();
      expect(screen.getByText(/System Delivery Notice/i)).toBeInTheDocument();
      expect(screen.getByText(/does not guarantee physical receipt by the officer or farmer contact/i)).toBeInTheDocument();
      expect(screen.queryByText(/Farmer acknowledged/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Vaccine allocated/i)).not.toBeInTheDocument();
    });
  });
});
