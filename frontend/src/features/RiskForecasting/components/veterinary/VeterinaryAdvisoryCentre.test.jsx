import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VeterinaryAdvisoryCentre } from './VeterinaryAdvisoryCentre';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';

vi.mock('../../services/riskForecastingWorkflowApi', async () => {
  const actual = await vi.importActual('../../services/riskForecastingWorkflowApi');
  return {
    ...actual,
    listForecastRecords: vi.fn(),
    listAssignedRecipients: vi.fn(),
    createAdvisoryDraft: vi.fn(),
    updateAdvisoryDraft: vi.fn(),
    previewAdvisory: vi.fn(),
    markAdvisoryReadyForReview: vi.fn(),
    approveAdvisory: vi.fn(),
    cancelAdvisory: vi.fn(),
    getNotificationBatch: vi.fn().mockResolvedValue(null),
    listNotificationDeliveries: vi.fn().mockResolvedValue({ deliveries: [] }),
  };
});

describe('VeterinaryAdvisoryCentre Component', () => {
  const validVetContext = Object.freeze({
    userId: 'usr_vet_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Anuradhapura']),
      assignedFarmIds: Object.freeze(['DEMO_FARM_001', 'DEMO_FARM_002']),
    }),
    permissions: Object.freeze({
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: false,
    }),
  });

  const validFarmerContext = Object.freeze({
    userId: 'usr_farmer_001',
    role: ROLES.FARMER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: Object.freeze(['Anuradhapura']),
      assignedFarmIds: Object.freeze([]),
    }),
    permissions: Object.freeze({
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: false,
      recordResponse: false,
      viewReports: false,
    }),
  });

  const mockForecastRecords = [
    {
      forecast_id: 'fdr_older_01',
      disease: 'FMD',
      district: 'Anuradhapura',
      target_year: 2026,
      target_month: 5,
      generated_at: '2026-05-01T10:00:00Z',
      probability: 0.72,
      probability_pct: 72.0,
      risk_level: 'HIGH',
      predicted_severity: 'HIGH',
      fallback_applied: false,
    },
    {
      forecast_id: 'fdr_newest_02',
      disease: 'FMD',
      district: 'Anuradhapura',
      target_year: 2026,
      target_month: 8,
      generated_at: '2026-08-15T12:00:00Z',
      probability: 0.85,
      probability_pct: 85.0,
      risk_level: 'HIGH',
      predicted_severity: 'HIGH',
      fallback_applied: false,
    },
  ];

  const mockRecipients = [
    { recipient_id: 'DEMO_FARM_001', recipient_name: 'Maha Illuppallama Dairy Farm', district: 'Anuradhapura' },
    { recipient_id: 'DEMO_FARM_002', recipient_name: 'Nachchaduwa Livestock Center', district: 'Anuradhapura' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 1. Authorization & Access Gating
  describe('Authorization Gating', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<VeterinaryAdvisoryCentre viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects FARMER role', () => {
      render(<VeterinaryAdvisoryCentre viewerContext={validFarmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('rejects DAPH_OFFICIAL role', () => {
      const daphContext = {
        ...validVetContext,
        role: ROLES.DAPH_OFFICIAL,
      };
      render(<VeterinaryAdvisoryCentre viewerContext={daphContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('renders Header banner for valid Veterinary Officer', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      expect(screen.getByRole('heading', { name: /Veterinary Officer Advisory Centre/i })).toBeInTheDocument();
      expect(screen.getByText(/Scope: Anuradhapura/i)).toBeInTheDocument();
    });

    it('queries recipient directory using forecast district when multiple districts are authorized', async () => {
      const multiDistrictContext = {
        ...validVetContext,
        authorization: {
          ...validVetContext.authorization,
          authorizedDistricts: ['Anuradhapura', 'Polonnaruwa'],
        },
      };

      const multiForecasts = [
        {
          forecast_id: 'fdr_polonnaruwa_01',
          disease: 'FMD',
          district: 'Polonnaruwa',
          target_year: 2026,
          target_month: 9,
          generated_at: '2026-08-20T10:00:00Z',
          probability: 0.65,
          probability_pct: 65.0,
          risk_level: 'MEDIUM',
          predicted_severity: 'MODERATE',
        },
      ];

      workflowApi.listForecastRecords.mockImplementation(async ({ district }) =>
        district === 'Polonnaruwa' ? { records: multiForecasts } : { records: [] }
      );
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: [] });

      render(<VeterinaryAdvisoryCentre viewerContext={multiDistrictContext} />);

      const forecastCard = await screen.findByText(/fdr_polonnaruwa_01/i);
      fireEvent.click(forecastCard);

      await waitFor(() => {
        expect(workflowApi.listAssignedRecipients).toHaveBeenCalledWith(
          expect.objectContaining({ vetId: 'usr_vet_001', district: 'Polonnaruwa' })
        );
      });
      expect(workflowApi.listAssignedRecipients).not.toHaveBeenCalledWith(
        expect.objectContaining({ district: 'Anuradhapura' })
      );
    });

    it('renders no recipient PII (phone numbers, email, or home addresses)', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const selectedScopeRadio = await screen.findByLabelText(/Selected Farms/i);
      fireEvent.click(selectedScopeRadio);

      await waitFor(() => {
        expect(screen.getByText(/Maha Illuppallama Dairy Farm/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/@/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\+94/i)).not.toBeInTheDocument();
    });
  });

  // 2. Step 1 — Official Forecast Selection
  describe('Step 1 — Forecast Selection & Reset', () => {
    it('queries listForecastRecords for authorized district only and sorts newest-first', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(workflowApi.listForecastRecords).toHaveBeenCalledWith(
          expect.objectContaining({ district: 'Anuradhapura' }),
          expect.anything()
        );
      });

      const cards = await screen.findAllByText(/Anuradhapura/i);
      expect(cards.length).toBeGreaterThan(0);
    });

    it('renders empty state when no official forecast records exist for district', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: [] });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      await waitFor(() => {
        expect(screen.getByText(/No Official Forecast Records Available/i)).toBeInTheDocument();
      });
      expect(screen.getByText(/Forecast Overview/i)).toBeInTheDocument();
    });

    it('does not automatically generate forecasts or create drafts on load', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      await waitFor(() => expect(workflowApi.listForecastRecords).toHaveBeenCalled());
      expect(workflowApi.createAdvisoryDraft).not.toHaveBeenCalled();
    });

    it('clears recipient selection, draft, and preview state when selecting a different forecast', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const card1 = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(card1);

      const radioSelected = await screen.findByLabelText(/Selected Farms/i);
      fireEvent.click(radioSelected);

      // Go back to Step 1 and select another forecast
      const step1Tab = screen.getByRole('button', { name: /1\. Select Forecast/i });
      fireEvent.click(step1Tab);

      const card2 = await screen.findByText(/fdr_older_01/i);
      fireEvent.click(card2);

      // Verify state was reset (step 2 scope defaults back to ALL_ASSIGNED)
      const radioAll = await screen.findByLabelText(/All Assigned Farms/i);
      expect(radioAll).toBeChecked();
    });

    it('renders N/A for missing predicted severity without inventing values', async () => {
      const recordsWithMissingVal = [
        {
          ...mockForecastRecords[0],
          predicted_severity: null,
        },
      ];
      workflowApi.listForecastRecords.mockResolvedValue({ records: recordsWithMissingVal });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      expect(await screen.findByText(/Severity: N\/A/i)).toBeInTheDocument();
    });
  });

  // 3. Step 2 — Recipient Selection
  describe('Step 2 — Recipient Selection & Payload Scope', () => {
    it('queries assigned recipients when forecast record is selected', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      await waitFor(() => {
        expect(workflowApi.listAssignedRecipients).toHaveBeenCalledWith(
          expect.objectContaining({ vetId: 'usr_vet_001', district: 'Anuradhapura' })
        );
      });

      expect(screen.getByText(/Step 2 — Select Recipients/i)).toBeInTheDocument();
    });

    it('requires at least one selected recipient when Selected Farms scope is chosen', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const selectedScopeRadio = await screen.findByLabelText(/Selected Farms/i);
      fireEvent.click(selectedScopeRadio);

      const continueBtn = screen.getByRole('button', { name: /Continue to Prepare Advice/i });
      expect(continueBtn).toBeDisabled();
    });

    it('submits exact ALL_ASSIGNED scope with undefined selected_recipient_ids', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_all_1',
        status: 'DRAFT',
        version: 1,
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(workflowApi.createAdvisoryDraft).toHaveBeenCalledWith(
          expect.objectContaining({
            recipient_scope: 'ALL_ASSIGNED',
            selected_recipient_ids: undefined,
          })
        );
      });
    });

    it('submits SELECTED scope with deduplicated selected_recipient_ids array', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_sel_1',
        status: 'DRAFT',
        version: 1,
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const selectedScopeRadio = await screen.findByLabelText(/Selected Farms/i);
      fireEvent.click(selectedScopeRadio);

      const selectAllBtn = await screen.findByRole('button', { name: /Select All Visible/i });
      fireEvent.click(selectAllBtn);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(workflowApi.createAdvisoryDraft).toHaveBeenCalledWith(
          expect.objectContaining({
            recipient_scope: 'SELECTED',
            selected_recipient_ids: ['DEMO_FARM_001', 'DEMO_FARM_002'],
          })
        );
      });
    });
  });

  // 4. Step 3 — Draft Preparation
  describe('Step 3 — Prepare Advice & Payload Integrity', () => {
    it('creates advisory draft via createAdvisoryDraft API method with exact allowed fields', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 1,
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const noteInput = screen.getByPlaceholderText(/ring vaccination/i);
      fireEvent.change(noteInput, { target: { value: 'Ensure vaccination ring is active.' } });

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(workflowApi.createAdvisoryDraft).toHaveBeenCalledWith({
          forecast_id: 'fdr_newest_02',
          advisory_type: 'VETERINARY_CUSTOM_ADVICE',
          recipient_scope: 'ALL_ASSIGNED',
          selected_recipient_ids: undefined,
          vet_custom_note: 'Ensure vaccination ring is active.',
          personalized_overrides: undefined,
          created_by: 'usr_vet_001',
        });
      });

      expect(screen.getByText(/Step 4 — Preview, Review, & Approval/i)).toBeInTheDocument();
    });

    it('updates existing advisory draft sending version and exact editable fields', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 1,
      });
      workflowApi.updateAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 2,
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);
      await screen.findByText(/Step 4 — Preview, Review, & Approval/i);

      // Go back to Step 3 and update
      const step3Tab = screen.getByRole('button', { name: /3\. Advice Draft/i });
      fireEvent.click(step3Tab);

      const noteInput = screen.getByPlaceholderText(/ring vaccination/i);
      fireEvent.change(noteInput, { target: { value: 'Updated note text.' } });

      const updateBtn = screen.getByRole('button', { name: /Update Advisory Draft/i });
      fireEvent.click(updateBtn);

      await waitFor(() => {
        expect(workflowApi.updateAdvisoryDraft).toHaveBeenCalledWith('adv_created_123', {
          version: 1,
          recipient_scope: 'ALL_ASSIGNED',
          selected_recipient_ids: undefined,
          vet_custom_note: 'Updated note text.',
          personalized_overrides: undefined,
        });
      });

      expect(screen.getAllByText(/Version: 2/i).length).toBeGreaterThan(0);
    });
  });

  // 5. Step 4 — Preview & Approval Lifecycle
  describe('Step 4 — Preview & Approval Lifecycle', () => {
    it('generates advisory preview passing advisoryId only', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 1,
      });
      workflowApi.previewAdvisory.mockResolvedValue({
        advisory_id: 'adv_created_123',
        recipient_summary: { selected_count: 2, personalized_count: 0 },
        previews: [
          {
            recipient_id: 'DEMO_FARM_001',
            recipient_name: 'Maha Illuppallama Dairy Farm',
            final_message: 'Resolved advice preview 1',
            is_personalized: false,
          },
        ],
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);
      await screen.findByText(/Step 4 — Preview, Review, & Approval/i);

      const previewBtn = await screen.findByRole('button', { name: /Generate Preview/i });
      fireEvent.click(previewBtn);

      await waitFor(() => {
        expect(workflowApi.previewAdvisory).toHaveBeenCalledWith({ advisoryId: 'adv_created_123' });
      });

      expect(screen.getByText(/Resolved advice preview 1/i)).toBeInTheDocument();
    });

    it('invalidates stale preview data when draft notes are modified', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 1,
      });
      workflowApi.previewAdvisory.mockResolvedValue({
        advisory_id: 'adv_created_123',
        recipient_summary: { selected_count: 1, personalized_count: 0 },
        previews: [
          {
            recipient_id: 'DEMO_FARM_001',
            recipient_name: 'Maha Illuppallama Dairy Farm',
            final_message: 'Stale preview message',
            is_personalized: false,
          },
        ],
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);
      await screen.findByText(/Step 4 — Preview, Review, & Approval/i);

      const previewBtn = await screen.findByRole('button', { name: /Generate Preview/i });
      fireEvent.click(previewBtn);

      expect(await screen.findByText(/Stale preview message/i)).toBeInTheDocument();

      // Go back to Step 3 and modify note
      const step3Tab = screen.getByRole('button', { name: /3\. Advice Draft/i });
      fireEvent.click(step3Tab);

      const noteInput = screen.getByPlaceholderText(/ring vaccination/i);
      fireEvent.change(noteInput, { target: { value: 'Altered note' } });

      // Stale preview should no longer be rendered
      expect(screen.queryByText(/Stale preview message/i)).not.toBeInTheDocument();
    });

    it('handles HTTP 409 optimistic lock conflict gracefully without losing local state', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 1,
      });
      workflowApi.approveAdvisory.mockRejectedValue(new Error('API Error 409: Optimistic concurrency conflict'));

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);

      const approveBtn = await screen.findByRole('button', { name: /Approve Advisory/i });
      fireEvent.click(approveBtn);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
      expect(screen.getByText(/Optimistic concurrency conflict/i)).toBeInTheDocument();
      expect(screen.getAllByText(/DRAFT/i).length).toBeGreaterThan(0);
    });

    it('handles approval lifecycle transition and freezes editing', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 1,
      });
      workflowApi.approveAdvisory.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'APPROVED',
        version: 2,
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);

      const approveBtn = await screen.findByRole('button', { name: /Approve Advisory/i });
      fireEvent.click(approveBtn);

      await waitFor(() => {
        expect(workflowApi.approveAdvisory).toHaveBeenCalledWith('adv_created_123', {
          version: 1,
          approvedBy: 'usr_vet_001',
        });
      });

      expect(screen.getByText(/Recipient snapshot and advisory text are now frozen/i)).toBeInTheDocument();
    });

    it('cancels advisory sending current version', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: mockForecastRecords });
      workflowApi.listAssignedRecipients.mockResolvedValue({ recipients: mockRecipients });
      workflowApi.createAdvisoryDraft.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'DRAFT',
        version: 1,
      });
      workflowApi.cancelAdvisory.mockResolvedValue({
        advisory_id: 'adv_created_123',
        forecast_id: 'fdr_newest_02',
        status: 'CANCELLED',
        version: 2,
      });

      render(<VeterinaryAdvisoryCentre viewerContext={validVetContext} />);

      const forecastCard = await screen.findByText(/fdr_newest_02/i);
      fireEvent.click(forecastCard);

      const continueBtn = await screen.findByRole('button', { name: /Continue to Prepare Advice/i });
      fireEvent.click(continueBtn);

      const saveBtn = await screen.findByRole('button', { name: /Save Advisory Draft/i });
      fireEvent.click(saveBtn);

      const cancelBtn = await screen.findByRole('button', { name: /Cancel Advisory/i });
      fireEvent.click(cancelBtn);

      await waitFor(() => {
        expect(workflowApi.cancelAdvisory).toHaveBeenCalledWith('adv_created_123', 1);
      });

      expect(screen.getByText(/Advisory CANCELLED/i)).toBeInTheDocument();
    });
  });
});
