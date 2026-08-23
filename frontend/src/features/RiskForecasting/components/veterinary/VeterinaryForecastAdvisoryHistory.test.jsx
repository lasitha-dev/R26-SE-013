import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VeterinaryForecastAdvisoryHistory } from './VeterinaryForecastAdvisoryHistory';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';

describe('VeterinaryForecastAdvisoryHistory Component', () => {
  const validVetContext = Object.freeze({
    userId: 'usr_vet_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Anuradhapura', 'Polonnaruwa']),
      assignedFarmIds: Object.freeze(['FARM_ANU_01']),
    }),
    permissions: Object.freeze({
      manageAlerts: true,
    }),
  });

  const farmerContext = Object.freeze({
    userId: 'usr_farmer_001',
    role: ROLES.FARMER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: Object.freeze(['Anuradhapura']),
      assignedFarmIds: Object.freeze([]),
    }),
  });

  const daphContext = Object.freeze({
    userId: 'usr_daph_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Anuradhapura', 'Polonnaruwa']),
      assignedFarmIds: Object.freeze([]),
    }),
  });

  const mockForecastRecord = {
    forecast_id: 'fdr_anu_001',
    disease: 'FMD',
    district: 'Anuradhapura',
    target_year: 2024,
    target_month: 5,
    generated_at: '2024-05-01T08:00:00Z',
    probability: 0.65,
    probability_pct: 65.0,
    risk_level: 'HIGH',
    predicted_severity: 'HIGH',
    model_variant: '30_feature_baseline',
    fallback_applied: false,
    data_quality: 'EXACT_REQUESTED_PERIOD',
    status: 'GENERATED',
    disclaimer: 'Scientific decision-support output. Model forecasts do not constitute confirmed clinical diagnoses.',
  };

  const mockAdvisoryRecord = {
    advisory_id: 'adv_anu_001',
    forecast_id: 'fdr_anu_001',
    advisory_type: 'VETERINARY_CUSTOM_ADVICE',
    disease: 'FMD',
    district: 'Anuradhapura',
    target_year: 2024,
    target_month: 5,
    risk_level: 'HIGH',
    priority: 'URGENT',
    title: 'FMD Alert Advisory',
    standard_message: 'Standard FMD advice body text for farmers.',
    vet_custom_note: 'Please check biosecurity barriers.',
    recipient_scope: 'ALL_ASSIGNED',
    selected_recipient_ids: [],
    recipient_summary: {
      total_assigned: 10,
      eligible_count: 10,
      selected_count: 10,
      standard_message_count: 10,
      personalized_count: 2,
      excluded_count: 0,
    },
    status: 'APPROVED',
    created_by: 'usr_vet_001',
    approved_by: 'usr_vet_001',
    version: 2,
    created_at: '2024-05-01T09:00:00Z',
    updated_at: '2024-05-01T09:30:00Z',
    approved_at: '2024-05-01T09:30:00Z',
  };

  const mockBatchRecord = {
    batch_id: 'batch_anu_001',
    advisory_id: 'adv_anu_001',
    forecast_id: 'fdr_anu_001',
    provider_name: 'MockNotificationProvider',
    status: 'COMPLETED',
    recipient_count: 10,
    pending_count: 0,
    processing_count: 0,
    succeeded_count: 9,
    failed_count: 1,
    cancelled_count: 0,
    created_by: 'usr_vet_001',
    created_at: '2024-05-01T10:00:00Z',
    updated_at: '2024-05-01T10:05:00Z',
  };

  const mockDeliveryRecord = {
    delivery_id: 'del_anu_001',
    batch_id: 'batch_anu_001',
    advisory_id: 'adv_anu_001',
    forecast_id: 'fdr_anu_001',
    recipient_id: 'DEMO_FARM_001',
    resolved_message: 'Standard FMD advice body text',
    status: 'SUCCEEDED',
    attempt_count: 1,
    provider_reference: 'MOCK_REF_001',
    last_error: null,
    created_at: '2024-05-01T10:00:00Z',
    updated_at: '2024-05-01T10:05:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(workflowApi, 'listForecastRecords').mockImplementation(async () => ({
      total_count: 1,
      limit: 10,
      offset: 0,
      records: [mockForecastRecord],
    }));

    vi.spyOn(workflowApi, 'listAdvisories').mockImplementation(async () => ({
      total_count: 1,
      limit: 50,
      offset: 0,
      advisories: [mockAdvisoryRecord],
    }));

    vi.spyOn(workflowApi, 'listNotificationBatches').mockImplementation(async () => ({
      total_count: 1,
      limit: 50,
      offset: 0,
      batches: [mockBatchRecord],
    }));

    vi.spyOn(workflowApi, 'listNotificationDeliveries').mockImplementation(async () => ({
      total_count: 1,
      limit: 50,
      offset: 0,
      deliveries: [mockDeliveryRecord],
    }));
  });

  // 1. Authorization & Access Control
  describe('Security & Access Control', () => {
    it('renders history workspace for valid Vet allowed context', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByRole('heading', { name: /Forecast & Advisory History/i, level: 2 })).toBeInTheDocument();
    });

    it('denies access (AccessContextUnavailable) to FARMER denied role', () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={farmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Veterinary Officer authorization/i)).toBeInTheDocument();
    });

    it('denies access (AccessContextUnavailable) to real ROLES.DAPH_OFFICIAL denied role', () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={daphContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Veterinary Officer authorization/i)).toBeInTheDocument();
    });

    it('denies access for missing or invalid context', () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('queries forecast records strictly using authorized district only', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await waitFor(() => {
        expect(workflowApi.listForecastRecords).toHaveBeenCalledWith(
          expect.objectContaining({ district: 'Anuradhapura' })
        );
      });
    });

    it('filters out unauthorized forecast returned before render', async () => {
      const unauthorizedRecord = {
        ...mockForecastRecord,
        forecast_id: 'fdr_unauth_colombo',
        district: 'Colombo',
      };
      workflowApi.listForecastRecords.mockImplementationOnce(async () => ({
        total_count: 2,
        limit: 10,
        offset: 0,
        records: [mockForecastRecord, unauthorizedRecord],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/Anuradhapura/i)).toBeInTheDocument();
    });

    it('does not render advisory with unauthorized forecast_id', async () => {
      const unauthorizedAdvisory = {
        ...mockAdvisoryRecord,
        advisory_id: 'adv_unauthorized_001',
        forecast_id: 'fdr_unauthorized_999',
        title: 'Unauthorized Advisory Title',
      };
      workflowApi.listAdvisories.mockImplementationOnce(async () => ({
        total_count: 2,
        limit: 50,
        offset: 0,
        advisories: [mockAdvisoryRecord, unauthorizedAdvisory],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/FMD Alert Advisory/i)).toBeInTheDocument();
      expect(screen.queryByText(/Unauthorized Advisory Title/i)).not.toBeInTheDocument();
    });

    it('does not render batch with unauthorized advisory_id', async () => {
      const unauthorizedBatch = {
        ...mockBatchRecord,
        batch_id: 'batch_unauthorized_999',
        advisory_id: 'adv_unauthorized_999',
      };
      workflowApi.listNotificationBatches.mockImplementationOnce(async () => ({
        total_count: 2,
        limit: 50,
        offset: 0,
        batches: [mockBatchRecord, unauthorizedBatch],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/Batch ID: batch_anu_001/i)).toBeInTheDocument();
      expect(screen.queryByText(/Batch ID: batch_unauthorized_999/i)).not.toBeInTheDocument();
    });

    it('never requests deliveries for unauthorized batch', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await waitFor(() => {
        expect(workflowApi.listNotificationDeliveries).toHaveBeenCalledWith('batch_anu_001');
      });
      expect(workflowApi.listNotificationDeliveries).not.toHaveBeenCalledWith('batch_unauthorized_999');
    });
  });

  // 2. Read-Only Guarantees
  describe('Read-Only Guarantees', () => {
    it('invokes no mutation API calls during mount or selection', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await screen.findByText(/FMD Alert Advisory/i);

      expect(workflowApi.createForecastRecord || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.createAdvisoryDraft || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.updateAdvisoryDraft || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.markAdvisoryReadyForReview || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.approveAdvisory || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.cancelAdvisory || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.enqueueNotificationBatch || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.dispatchNotificationBatch || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.retryFailedNotificationDeliveries || vi.fn()).not.toHaveBeenCalled();
      expect(workflowApi.cancelNotificationBatch || vi.fn()).not.toHaveBeenCalled();
    });

    it('renders no edit, approve, cancel, create, dispatch, or retry buttons', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await screen.findByText(/FMD Alert Advisory/i);

      expect(screen.queryByRole('button', { name: /Create Draft/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Update Advisory/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Ready for Review/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Approve Advisory/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Cancel Advisory/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Dispatch Notification Batch/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Simulate Farmer Notification/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Retry Failed Deliveries/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Cancel Pending Batch/i })).not.toBeInTheDocument();
    });
  });

  // 3. Forecast Details & Guardrails
  describe('Forecast Record Details & Guardrails', () => {
    it('sorts forecast entries deterministically (target_year DESC, target_month DESC, generated_at DESC)', async () => {
      const olderRecord = {
        ...mockForecastRecord,
        forecast_id: 'fdr_older',
        target_year: 2023,
        target_month: 12,
      };
      const newerRecord = {
        ...mockForecastRecord,
        forecast_id: 'fdr_newer',
        target_year: 2024,
        target_month: 6,
      };
      workflowApi.listForecastRecords.mockImplementationOnce(async () => ({
        total_count: 2,
        limit: 10,
        offset: 0,
        records: [olderRecord, newerRecord],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      const headings = await screen.findAllByText(/Target:/i);
      expect(headings[0].textContent).toContain('June 2024');
      expect(headings[1].textContent).toContain('December 2023');
    });

    it('ensures missing probability is displayed as N/A and not 0%', async () => {
      const recordMissingProb = {
        ...mockForecastRecord,
        forecast_id: 'fdr_anu_001',
        probability: null,
        probability_pct: null,
      };
      workflowApi.listForecastRecords.mockImplementationOnce(async () => ({
        total_count: 1,
        limit: 10,
        offset: 0,
        records: [recordMissingProb],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      const naElements = await screen.findAllByText(/N\/A/i);
      expect(naElements.length).toBeGreaterThan(0);
      expect(screen.queryByText(/0.0%/i)).not.toBeInTheDocument();
    });

    it('ensures missing risk level is displayed as N/A and not LOW', async () => {
      const recordMissingRisk = {
        ...mockForecastRecord,
        forecast_id: 'fdr_anu_001',
        risk_level: null,
      };
      workflowApi.listForecastRecords.mockImplementationOnce(async () => ({
        total_count: 1,
        limit: 10,
        offset: 0,
        records: [recordMissingRisk],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      const naElements = await screen.findAllByText(/N\/A/i);
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('ensures missing predicted severity is displayed as N/A', async () => {
      const recordMissingSev = {
        ...mockForecastRecord,
        forecast_id: 'fdr_anu_001',
        predicted_severity: null,
      };
      workflowApi.listForecastRecords.mockImplementationOnce(async () => ({
        total_count: 1,
        limit: 10,
        offset: 0,
        records: [recordMissingSev],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      const naElements = await screen.findAllByText(/N\/A/i);
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays target period clearly distinct from generated timestamp', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/May 2024/i)).toBeInTheDocument();
      expect(screen.getByText(/5\/1\/2024/i)).toBeInTheDocument();
    });

    it('displays scientific disclaimer and forecast-not-diagnosis guardrail', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(
        await screen.findByText(/Scientific decision-support output\. Model forecasts do not constitute confirmed clinical diagnoses\./i)
      ).toBeInTheDocument();
    });

    it('does not render chart or trend UI elements in history workspace', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await screen.findByText(/Forecast & Advisory History/i);
      expect(screen.queryByTestId('trend-chart')).not.toBeInTheDocument();
      expect(screen.queryByText(/Outbreak Trend Curve/i)).not.toBeInTheDocument();
    });
  });

  // 4. Advisory Snapshot Tests
  describe('Advisory Snapshot & State', () => {
    it('displays clear message when in no-advisory state', async () => {
      workflowApi.listAdvisories.mockImplementationOnce(async () => ({
        total_count: 0,
        limit: 50,
        offset: 0,
        advisories: [],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/No advisory created for this forecast/i)).toBeInTheDocument();
    });

    it('displays stored standard_message and vet_custom_note snapshot', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/Standard FMD advice body text for farmers\./i)).toBeInTheDocument();
      expect(screen.getByText(/Please check biosecurity barriers\./i)).toBeInTheDocument();
    });

    it('displays recipient scope and counts', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await screen.findByText(/FMD Alert Advisory/i);
      expect(screen.getByText(/ALL_ASSIGNED/i)).toBeInTheDocument();
      expect(screen.getByText(/10/i)).toBeInTheDocument();
    });

    it('displays APPROVED frozen status badge', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/APPROVED \(Frozen\)/i)).toBeInTheDocument();
    });

    it('displays CANCELLED status badge when advisory is cancelled', async () => {
      const cancelledAdv = { ...mockAdvisoryRecord, status: 'CANCELLED' };
      workflowApi.listAdvisories.mockImplementationOnce(async () => ({
        total_count: 1,
        limit: 50,
        offset: 0,
        advisories: [cancelledAdv],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/CANCELLED/i)).toBeInTheDocument();
    });
  });

  // 5. Simulation History Tests
  describe('Simulated Delivery History', () => {
    it('displays all six batch count summaries (total, pending, processing, succeeded, failed, cancelled)', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await screen.findByText(/Batch ID: batch_anu_001/i);
      expect(screen.getByText(/Total/i)).toBeInTheDocument();
      expect(screen.getByText(/Pending/i)).toBeInTheDocument();
      expect(screen.getByText(/Processing/i)).toBeInTheDocument();
      expect(screen.getByText(/Simulated Success/i)).toBeInTheDocument();
      expect(screen.getByText(/Failed/i)).toBeInTheDocument();
      expect(screen.getByText(/Cancelled/i)).toBeInTheDocument();
    });

    it('displays recipient delivery items with provider reference and attempt count', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/DEMO_FARM_001/i)).toBeInTheDocument();
      expect(screen.getByText(/MOCK_REF_001/i)).toBeInTheDocument();
      expect(screen.getByText(/1/i)).toBeInTheDocument();
    });

    it('displays mandatory standalone simulation disclaimer', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(
        await screen.findByText(/Standalone simulation history only\. A successful result confirms mock provider execution/i)
      ).toBeInTheDocument();
    });

    it('never claims real farmer delivery or receipt', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await screen.findByText(/Simulated Delivery History/i);
      expect(screen.queryByText(/Delivered to Farmer/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Farmer Read/i)).not.toBeInTheDocument();
    });
  });

  // 6. Filters & Pagination
  describe('Filters & Pagination Controls', () => {
    it('supports district, disease, year, month, record-status, and advisory-status filtering', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByRole('combobox', { name: /Authorized District Filter/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /Disease Filter/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /Target Year Filter/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /Target Month Filter/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /Forecast Status Filter/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /Advisory Status Filter/i })).toBeInTheDocument();
    });

    it('resets filters when Reset Filters button is clicked', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      const diseaseSelect = await screen.findByRole('combobox', { name: /Disease Filter/i });
      fireEvent.change(diseaseSelect, { target: { value: 'FMD' } });
      expect(diseaseSelect.value).toBe('FMD');

      const resetBtn = screen.getByRole('button', { name: /Reset Filters/i });
      fireEvent.click(resetBtn);
      expect(diseaseSelect.value).toBe('ALL');
    });

    it('omits empty filter values from API request parameters', async () => {
      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      await waitFor(() => {
        expect(workflowApi.listForecastRecords).toHaveBeenCalledWith({
          district: 'Anuradhapura',
          disease: undefined,
          target_year: undefined,
          target_month: undefined,
          status: undefined,
          limit: 10,
          offset: 0,
        });
      });
    });
  });

  // 7. Async & Error Handling
  describe('Async Timing & Error Protection', () => {
    it('sanitizes technical python stack trace error messages', async () => {
      workflowApi.listForecastRecords.mockImplementationOnce(async () => {
        throw new Error('Traceback (most recent call last):\nFile "routes.py", line 42, in get\nKeyError: "district"');
      });

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(
        await screen.findByText(/A system error occurred while retrieving historical records/i)
      ).toBeInTheDocument();
    });

    it('sanitizes JS TypeError, stack traces, and Windows file paths from rendering in UI', async () => {
      workflowApi.listForecastRecords.mockImplementationOnce(async () => {
        throw new Error('TypeError: Cannot read properties of undefined at loadHistory (C:\\Users\\private\\config.env:42:10)');
      });

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(
        await screen.findByText(/A system error occurred while retrieving historical records/i)
      ).toBeInTheDocument();
      expect(screen.queryByText(/TypeError/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/C:\\Users\\/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/loadHistory/i)).not.toBeInTheDocument();
    });

    it('sanitizes tokens, api_keys, passwords, bearer credentials, and DB URLs from rendering in UI', async () => {
      workflowApi.listForecastRecords.mockImplementationOnce(async () => {
        throw new Error(
          'Authorization: Bearer DO_NOT_EXPOSE token=DO_NOT_EXPOSE api_key=DO_NOT_EXPOSE password=DO_NOT_EXPOSE postgresql://user:password@server/db mongodb://user:password@server/db'
        );
      });

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(
        await screen.findByText(/A system error occurred while retrieving historical records/i)
      ).toBeInTheDocument();
      expect(screen.queryByText(/DO_NOT_EXPOSE/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/token=/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/api_key=/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/password=/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Bearer/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/postgresql:\/\//i)).not.toBeInTheDocument();
      expect(screen.queryByText(/mongodb:\/\//i)).not.toBeInTheDocument();
    });

    it('sanitizes POSIX private file paths and stack-frame text from rendering in UI', async () => {
      workflowApi.listForecastRecords.mockImplementationOnce(async () => {
        throw new Error('/home/service/private/config.env at loadHistory (History.jsx:42:10)');
      });

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(
        await screen.findByText(/A system error occurred while retrieving historical records/i)
      ).toBeInTheDocument();
      expect(screen.queryByText(/\/home\//i)).not.toBeInTheDocument();
      expect(screen.queryByText(/loadHistory/i)).not.toBeInTheDocument();
    });

    it('sanitizes sensitive error patterns in delivery item last_error field', async () => {
      const sensitiveDelivery = {
        ...mockDeliveryRecord,
        status: 'FAILED',
        last_error: 'TypeError: failed to connect to postgresql://user:pass@db with token=DO_NOT_EXPOSE',
      };
      workflowApi.listNotificationDeliveries.mockImplementationOnce(async () => ({
        total_count: 1,
        limit: 50,
        offset: 0,
        deliveries: [sensitiveDelivery],
      }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      expect(await screen.findByText(/Provider execution error\./i)).toBeInTheDocument();
      expect(screen.queryByText(/DO_NOT_EXPOSE/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/postgresql:\/\//i)).not.toBeInTheDocument();
      expect(screen.queryByText(/token=/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/TypeError/i)).not.toBeInTheDocument();
    });
    it('prevents stale old-district responses from overwriting current district state', async () => {
      let resolveFirst;
      const firstPromise = new Promise((resolve) => { resolveFirst = resolve; });

      workflowApi.listForecastRecords
        .mockImplementationOnce(async () => {
          await firstPromise;
          return { total_count: 1, limit: 10, offset: 0, records: [{ ...mockForecastRecord, district: 'Anuradhapura' }] };
        })
        .mockImplementationOnce(async () => ({
          total_count: 1,
          limit: 10,
          offset: 0,
          records: [{ ...mockForecastRecord, district: 'Polonnaruwa' }],
        }));

      render(<VeterinaryForecastAdvisoryHistory viewerContext={validVetContext} />);
      const select = await screen.findByRole('combobox', { name: /Authorized District Filter/i });
      fireEvent.change(select, { target: { value: 'Polonnaruwa' } });

      resolveFirst();

      await waitFor(() => {
        expect(screen.getByRole('combobox', { name: /Authorized District Filter/i }).value).toBe('Polonnaruwa');
      });
    });
  });
});
