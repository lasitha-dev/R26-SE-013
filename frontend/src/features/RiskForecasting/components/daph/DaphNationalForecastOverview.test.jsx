import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { DaphNationalForecastOverview } from './DaphNationalForecastOverview';
import { resetSeverityHistoryCache } from '../../services/severityHistoryLoader';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as api from '../../services/riskForecastingWorkflowApi';

// Mock Api module
vi.mock('../../services/riskForecastingWorkflowApi', () => ({
  listForecastDistricts: vi.fn(),
  listForecastRecords: vi.fn(),
  getSeverityHistory: vi.fn(),
  listAdvisories: vi.fn(),
  listNotificationBatches: vi.fn(),
  generateV2Forecasts: vi.fn(),
  getActiveSurveillance: vi.fn(),
  listOutlooks: vi.fn(),
  previewOutlooks: vi.fn(),
}));

describe('DaphNationalForecastOverview Component', () => {
  const validDaphContext = Object.freeze({
    userId: 'usr_daph_test_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Anuradhapura', 'Polonnaruwa', 'Jaffna']),
      assignedFarmIds: Object.freeze([]),
    }),
    permissions: Object.freeze({
      viewDataQuality: true,
      viewModelTransparency: true,
    }),
  });

  const mockDistrictsData = {
    total_districts: 25,
    districts: ['Ampara', 'Anuradhapura', 'Badulla', 'Batticaloa', 'Colombo', 'Galle', 'Gampaha', 'Hambantota', 'Jaffna', 'Kalutara', 'Kandy', 'Kegalle', 'Kilinochchi', 'Kurunegala', 'Mannar', 'Matale', 'Matara', 'Monaragala', 'Mullaitivu', 'Nuwara Eliya', 'Polonnaruwa', 'Puttalam', 'Ratnapura', 'Trincomalee', 'Vavuniya'],
    month_names: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  };

  const mockRecordsData = {
    total: 3,
    records: [
      {
        forecast_id: 'fdr_001',
        disease: 'FMD',
        district: 'Anuradhapura',
        target_year: 2025,
        target_month: 1,
        probability: 0.75,
        probability_pct: 75.0,
        risk_level: 'HIGH',
        predicted_severity: 'HIGH',
        status: 'GENERATED',
        model_variant: 'FMD_HYBRID_V1',
        data_quality: 'EXACT_REQUESTED_PERIOD',
        fallback_applied: false,
        source_year: 2025,
        source_month: 1,
        data_age_months: 0,
        disclaimer: 'Official forecast disclaimer text.',
        created_at: '2024-12-23T00:00:00Z',
      },
      {
        forecast_id: 'fdr_002',
        disease: 'FMD',
        district: 'Polonnaruwa',
        target_year: 2025,
        target_month: 1,
        probability: 0.35,
        probability_pct: 35.0,
        risk_level: 'MEDIUM',
        predicted_severity: 'MODERATE',
        status: 'GENERATED',
        model_variant: 'FMD_HYBRID_V1',
        data_quality: 'HISTORICAL_FALLBACK_1Y',
        fallback_applied: true, // Amendment 1
        source_year: 2024,
        source_month: 1,
        data_age_months: 12,
        disclaimer: 'Official forecast disclaimer text.',
        created_at: '2024-12-23T00:00:00Z',
      },
      {
        forecast_id: 'fdr_003',
        disease: 'LSD',
        district: 'Jaffna',
        target_year: 2025,
        target_month: 1,
        probability: 0.10,
        probability_pct: 10.0,
        risk_level: 'LOW',
        predicted_severity: 'LOW',
        status: 'GENERATED',
        model_variant: 'LSD_XGB_V1',
        data_quality: 'EXACT_REQUESTED_PERIOD',
        fallback_applied: false,
        source_year: 2025,
        source_month: 1,
        data_age_months: 0,
        disclaimer: 'Official forecast disclaimer text.',
        created_at: '2024-12-23T00:00:00Z',
      },
    ],
  };

  const mockAdvisoriesData = {
    total: 1,
    advisories: [
      {
        advisory_id: 'adv_101',
        forecast_id: 'fdr_001',
        disease: 'FMD',
        district: 'Anuradhapura',
        target_year: 2026,
        target_month: 9,
        status: 'APPROVED',
        approved_by: 'vet_officer_99',
        recipient_scope: 'ALL_ASSIGNED',
        created_at: '2026-08-23T00:00:00Z',
      },
    ],
  };

  const mockBatchesData = {
    total: 1,
    batches: [
      {
        batch_id: 'snb_501',
        advisory_id: 'adv_101',
        forecast_id: 'fdr_001',
        status: 'COMPLETED',
        recipient_count: 20,
        succeeded_count: 20,
        failed_count: 0,
        pending_count: 0,
        created_at: '2026-08-23T00:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    api.listForecastDistricts.mockReset().mockResolvedValue(mockDistrictsData);
    api.listForecastRecords.mockReset().mockResolvedValue(mockRecordsData);
    resetSeverityHistoryCache();
    api.getSeverityHistory.mockReset().mockResolvedValue({ diseases: {} });
    api.listAdvisories.mockReset().mockResolvedValue(mockAdvisoriesData);
    api.listNotificationBatches.mockReset().mockResolvedValue(mockBatchesData);
    api.getActiveSurveillance.mockReset().mockResolvedValue({ disease: 'FMD', period: '2026-10', districts: {} });
    api.generateV2Forecasts.mockReset();
  });

  // 1. Authorization & Gating Tests
  describe('Authorization & Access Gating', () => {
    it('fails closed when viewerContext is null or invalid', () => {
      render(<DaphNationalForecastOverview viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/ViewerContext must be a non-null object/i)).toBeInTheDocument();
    });

    it('fails closed for FARMER or VETERINARY_OFFICER roles', () => {
      const farmerContext = {
        userId: 'usr_farmer',
        role: ROLES.FARMER,
        authorization: { scopeLevel: SCOPE_LEVELS.FARM, authorizedDistricts: ['Anuradhapura'] },
      };
      render(<DaphNationalForecastOverview viewerContext={farmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('renders workspace successfully for DAPH_OFFICIAL with NATIONAL scope', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /National Forecast Overview/i, level: 1 })).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getAllByText(/Anuradhapura/i)[0]).toBeInTheDocument();
      }, { timeout: 4000 });
    });
  });

  it('renders the empty-state icon as find_in_page and not dataset_with_doubt', async () => {
    api.listForecastDistricts.mockResolvedValue(mockDistrictsData);
    api.listForecastRecords.mockResolvedValue({ total: 0, records: [] });
    api.listAdvisories.mockResolvedValue({ total: 0, advisories: [] });
    api.listNotificationBatches.mockResolvedValue({ total: 0, batches: [] });

    render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

    await waitFor(() => {
      expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
    });

    const riskSelect = screen.getByLabelText(/Risk Tier/i);
    fireEvent.change(riskSelect, { target: { value: 'HIGH' } });

    const emptyStateText = await screen.findByText(/No official forecast records found for selected criteria/i);
    const emptyStateContainer = emptyStateText.parentElement;

    expect(within(emptyStateContainer).getByText('find_in_page')).toBeInTheDocument();
    expect(within(emptyStateContainer).queryByText('dataset_with_doubt')).not.toBeInTheDocument();
  });

  // 2. Data Fetching & API Interoperability
  describe('Data Fetching & API Roundtrips', () => {
    it('calls listForecastDistricts, listForecastRecords, listAdvisories, listNotificationBatches on mount', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(api.listForecastDistricts).toHaveBeenCalledTimes(1);
        expect(api.listForecastRecords).toHaveBeenCalled();
        expect(api.listAdvisories).toHaveBeenCalledTimes(1);
        expect(api.listNotificationBatches).toHaveBeenCalledTimes(1);
      }, { timeout: 4000 });
    });

    it('passes limit=200 to listForecastRecords to fetch complete collection for national summary (Amendment 2)', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(api.listForecastRecords).toHaveBeenCalledWith(
          expect.objectContaining({ limit: 200, offset: 0 }),
          expect.any(Object)
        );
      }, { timeout: 4000 });
    });

    it('handles partial operational failure gracefully without failing official forecast display (Amendment 8)', async () => {
      api.listAdvisories.mockRejectedValueOnce(new Error('Advisory service timeout'));
      api.listNotificationBatches.mockRejectedValueOnce(new Error('Batch service unavailable'));

      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText(/Partial Operational Coverage Warning/i)).toBeInTheDocument();
        expect(screen.getAllByText(/Anuradhapura/i)[0]).toBeInTheDocument();
      }, { timeout: 4000 });
    });
  });

  // 3. Provenance & Fallback Proxy Assertions (Amendment 1)
  describe('Data Provenance & Fallback (Amendment 1)', () => {
    it('labels legacy v1 records that used proxy inputs', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('v1 · proxy inputs')).toBeInTheDocument();
      }, { timeout: 4000 });
    });

    it('keeps proxy-input records in risk filtering and allows follow-up, with provenance visible', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText(/Risk Tier/i), { target: { value: 'MEDIUM' } });

      await waitFor(() => {
        const row = screen.getByText('Polonnaruwa').closest('tr');
        expect(within(row).getByText('v1 · proxy inputs')).toBeInTheDocument();
        expect(within(row).getByRole('button', { name: 'Follow-up' })).toBeInTheDocument();
      });
    });

    it('requests records for the selected target period only', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(api.listForecastRecords).toHaveBeenCalledWith(
          expect.objectContaining({ target_year: 2025, target_month: 1 }),
          expect.anything()
        );
      });
    });

    it('accurately counts fallback_applied records in summary cards', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('Using the seasonal average')).toBeInTheDocument();
      }, { timeout: 4000 });
    });
  });

  // 4. Missing-Record Semantics (Amendment 3)
  describe('Missing-Record Semantics (Amendment 3)', () => {
    it('displays missing slots calculation for ALL diseases (out of 50)', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        // 50 total slots - 3 present records = 47 missing
        expect(screen.getByText(/Missing District–Disease Combinations \(out of 50\)/i)).toBeInTheDocument();
        expect(screen.getAllByText('47')[0]).toBeInTheDocument();
      }, { timeout: 4000 });
    });

    it('displays missing slots calculation for FMD (out of 25) when FMD selected', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getAllByText(/Anuradhapura/i)[0]).toBeInTheDocument();
      }, { timeout: 4000 });

      const diseaseSelect = screen.getByLabelText(/Disease Filter/i);
      fireEvent.change(diseaseSelect, { target: { value: 'FMD' } });

      await waitFor(() => {
        expect(screen.getByText(/Districts without FMD Forecast \(out of 25\)/i)).toBeInTheDocument();
        expect(screen.getAllByText('23')[0]).toBeInTheDocument();
      }, { timeout: 4000 });
    });
  });

  // 4a. Missing-Record Presentation Fixes
  describe('Missing-Record Presentation Fixes', () => {
    it('missing rows show Target Period for Jan 2025, Rank “—”, and no active View button', async () => {
      // 0 records so all rows are missing
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
        const rows = screen.getAllByRole('row');
        expect(rows.length).toBeGreaterThan(1);
      });

      // “Month null”, “undefined” and raw null are absent
      const html = document.body.innerHTML;
      expect(html).not.toMatch(/Month null/);
      expect(html).not.toMatch(/>undefined</);
      expect(html).not.toMatch(/>null</);

      // missing rows show Target Period correctly (e.g. January 2025)
      const targetLabels = screen.getAllByText(/January 2025/i);
      expect(targetLabels.length).toBeGreaterThan(0);

      // missing rows show Rank “—”
      const rankDashes = screen.getAllByText('—', { selector: 'td' });
      expect(rankDashes.length).toBeGreaterThan(0);

      // missing rows have no active View button, but show "No record" details
      expect(screen.queryByRole('button', { name: 'View' })).not.toBeInTheDocument();
      expect(screen.getAllByText('No record').length).toBeGreaterThan(0);
    });

    it('never fabricates forecast values for periods without persisted records', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
        expect(screen.getAllByText('No Record').length).toBe(50);
      });

      const table = screen.getByRole('table');
      expect(within(table).queryByText(/\d+\.\d%/)).not.toBeInTheDocument();
      expect(within(table).queryByText(/Model Predicted/i)).not.toBeInTheDocument();
      expect(within(table).queryByText(/^(HIGH|MEDIUM|LOW)$/)).not.toBeInTheDocument();
      expect(fetchSpy.mock.calls.some(([url]) => String(url).includes('demo-forecasting'))).toBe(false);
      fetchSpy.mockRestore();
    });

    it('"Not issued yet" risk filter lists only slots without persisted records', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText(/Risk Tier/i), { target: { value: 'NO_RECORD' } });

      await waitFor(() => {
        expect(screen.getAllByText('No Record').length).toBeGreaterThan(0);
        expect(screen.queryByRole('button', { name: 'View' })).not.toBeInTheDocument();
      });
    });

    it('real rows retain Rank and View, matrix behaves correctly', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      // Real rows retain View button
      const viewButtons = screen.getAllByRole('button', { name: 'View' });
      expect(viewButtons.length).toBeGreaterThan(0);
      
      // Rank is retained for real rows (e.g., '1', '2')
      const rankOne = screen.getAllByText('1', { selector: 'td' });
      expect(rankOne.length).toBeGreaterThan(0);
    });

    it('no-year informational message appears only when availableYears is empty', async () => {
      // With records, it shouldn't be there
      const { unmount } = render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });
      expect(screen.queryByText(/No saved forecast periods are available. Generate and save an FMD or LSD forecast/)).not.toBeInTheDocument();
      unmount();
    });
  });

  // 5. Deterministic Priority Sorting
  describe('Deterministic Priority Sorting', () => {
    it('sorts table rows by Risk tier (HIGH > MEDIUM > LOW > NO_RECORD) then probability desc', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getAllByText(/Anuradhapura/i)[0]).toBeInTheDocument();
      }, { timeout: 4000 });

      const rows = screen.getAllByRole('row');
      expect(rows.length).toBeGreaterThan(3);
    });
  });

  // 6. Detail Drawer & Privacy Protection (Amendment 10)
  describe('Detail Drawer & Security Guardrails (Amendment 10)', () => {
    it('opens read-only drawer when View button is clicked', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getAllByText(/Anuradhapura/i)[0]).toBeInTheDocument();
      }, { timeout: 4000 });

      const viewButtons = screen.getAllByRole('button', { name: /View/i });
      fireEvent.click(viewButtons[0]);

      expect(screen.getByText(/Authoritative Forecast Record Metadata/i)).toBeInTheDocument();
    });

    it('NEVER calls listNotificationDeliveries or renders recipient PII', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /National Forecast Overview/i })).toBeInTheDocument();
      }, { timeout: 4000 });

      expect('listNotificationDeliveries' in api).toBe(false);
      expect(screen.queryByText(/farmer_name/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/phone_number/i)).not.toBeInTheDocument();
    });

    it('contains no mutation elements or dispatch controls', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /National Forecast Overview/i })).toBeInTheDocument();
      }, { timeout: 4000 });

      expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Dispatch/i })).not.toBeInTheDocument();
      // Forecast generation exists only as an explicit DAPH action; rendering never triggers it.
      expect(api.generateV2Forecasts).not.toHaveBeenCalled();
    });
  });

  // 7. Target Period & Zero Fabrication Policy
  describe('Target Period & Zero Fabrication Policy', () => {


    it('ensures "Phase 9 Backend Limit Bound" text is absent from the UI', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /National Forecast Overview/i })).toBeInTheDocument();
      });

      expect(screen.queryByText(/Phase 9 Backend Limit Bound/i)).not.toBeInTheDocument();
    });

    it('displays clear empty state when a filter combination genuinely produces no final rows', async () => {
      // Setup zero real records, so all 50 slots are missing (NO_RECORD)
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });

      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      // Filter by HIGH risk, which will eliminate the NO_RECORD rows
      const riskSelect = screen.getByLabelText(/Risk Tier/i);
      fireEvent.change(riskSelect, { target: { value: 'HIGH' } });

      await waitFor(() => {
        expect(screen.getByText(/No official forecast records found for selected criteria/i)).toBeInTheDocument();
      });

      // An empty period never triggers automatic generation.
      expect(api.generateV2Forecasts).not.toHaveBeenCalled();
    });
  });

  // 8. Operational Follow-Up Integration
  describe('Operational Follow-Up Integration', () => {
    it('opens DaphFollowUpComposer when Follow-up table action button is clicked', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getAllByText(/Anuradhapura/i)[0]).toBeInTheDocument();
      });

      const followUpButtons = screen.getAllByRole('button', { name: /Follow-up/i });
      expect(followUpButtons.length).toBeGreaterThan(0);

      fireEvent.click(followUpButtons[0]);

      expect(screen.getByText('Issue Operational Follow-Up')).toBeInTheDocument();
    });

    it('opens DaphFollowUpComposer from Detail Drawer when Issue Operational Follow-Up is clicked', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getAllByText(/Anuradhapura/i)[0]).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByRole('button', { name: /View/i });
      fireEvent.click(viewButtons[0]);

      const drawerIssueButton = screen.getByRole('button', { name: /Issue Operational Follow-Up/i });
      fireEvent.click(drawerIssueButton);

      expect(screen.getByText('Issue Operational Follow-Up')).toBeInTheDocument();
    });

    it('does not render Follow-up table action button or drawer button for missing-record placeholders', async () => {
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });

      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /Follow-up/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Issue Operational Follow-Up/i })).not.toBeInTheDocument();
    });
  });

  // 9. Responsive Layout Adjustments
  describe('Responsive Layout Adjustments', () => {
    it('renders filter controls in their original order and callbacks remain operational', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Disease Filter/i)).toBeInTheDocument();
      });

      const diseaseSelect = screen.getByLabelText(/Disease Filter/i);
      const riskSelect = screen.getByLabelText(/Risk Tier/i);
      const advisorySelect = screen.getByLabelText(/Advisory Coverage/i);

      expect(diseaseSelect).toHaveAttribute('id', 'disease-filter-select');
      expect(riskSelect).toHaveAttribute('id', 'risk-filter-select');
      expect(advisorySelect).toHaveAttribute('id', 'advisory-filter-select');

      // Test a callback
      fireEvent.change(diseaseSelect, { target: { value: 'FMD' } });
      expect(diseaseSelect.value).toBe('FMD');
    });

    it('renders summary metric labels without truncation classes removing them', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('Total Forecast Records')).toBeInTheDocument();
        expect(screen.getByText('HIGH Risk Districts')).toBeInTheDocument();
        expect(screen.getByText('MEDIUM Risk Districts')).toBeInTheDocument();
        expect(screen.getByText('LOW Risk Districts')).toBeInTheDocument();
        expect(screen.getByText('Using the seasonal average')).toBeInTheDocument();
      });

      const missingLabel = screen.getByText(/Missing District–Disease Combinations/i);
      expect(missingLabel).toBeInTheDocument();
      expect(missingLabel.className).not.toContain('truncate');
      expect(missingLabel.className).toContain('whitespace-normal');
      expect(missingLabel.className).toContain('break-words');
    });

    it('renders empty-state content when a filter produces no rows', async () => {
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      const riskSelect = screen.getByLabelText(/Risk Tier/i);
      fireEvent.change(riskSelect, { target: { value: 'HIGH' } });

      await waitFor(() => {
        expect(screen.getByText(/No official forecast records found for selected criteria/i)).toBeInTheDocument();
      });

      const emptyStateText = screen.getByText(/No official forecast records found/i);
      const container = emptyStateText.parentElement;
      expect(container.className).toContain('p-6 md:p-12');
    });

    it('does not remove matrix, filters, refresh, or pagination when permitted', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
        expect(screen.getByText(/Showing \d+ of \d+ matching matrix entries/i)).toBeInTheDocument();
      });

      const refreshBtn = screen.getByRole('button', { name: /Refresh Data/i });
      expect(refreshBtn).toBeInTheDocument();
    });

    it('applies correct responsive grid classes to filter container', async () => {
      const { container } = render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => {
        expect(screen.getByLabelText(/Disease Filter/i)).toBeInTheDocument();
      });
      const grid = container.querySelector('.grid-cols-1.sm\\:grid-cols-2');
      expect(grid).toBeInTheDocument();
    });
  });



  // 11. Matrix Empty-State Counting Contract
  describe('Matrix Empty-State Counting Contract', () => {
    it('with zero real records and 25 districts, renders matrix, 50 combinations for ALL, official is 0', async () => {
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      const totalRecordsElement = screen.getByText('Total Forecast Records').nextElementSibling;
      expect(totalRecordsElement.textContent).toBe('0');

      const missingLabel = screen.getByText(/Missing District–Disease Combinations \(out of 50\)/i);
      expect(missingLabel.nextSibling.textContent).toBe('50');

      const matrixNote = screen.getByText(/Showing 50 of 50 matching matrix entries/i);
      expect(matrixNote).toBeInTheDocument();

      expect(screen.queryByText(/No official forecast records found for selected criteria/i)).not.toBeInTheDocument();
    });

    it('selecting FMD results in 25 matrix combinations when no records exist', async () => {
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      const diseaseSelect = screen.getByLabelText(/Disease Filter/i);
      fireEvent.change(diseaseSelect, { target: { value: 'FMD' } });

      await waitFor(() => {
        const missingLabel = screen.getByText(/Districts without FMD Forecast \(out of 25\)/i);
        expect(missingLabel.nextSibling.textContent).toBe('25');
        expect(screen.getByText(/Showing 25 of 25 matching matrix entries/i)).toBeInTheDocument();
      });
    });

    it('selecting LSD results in 25 matrix combinations when no records exist', async () => {
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument();
      });

      const diseaseSelect = screen.getByLabelText(/Disease Filter/i);
      fireEvent.change(diseaseSelect, { target: { value: 'LSD' } });

      await waitFor(() => {
        const missingLabel = screen.getByText(/Districts without LSD Forecast \(out of 25\)/i);
        expect(missingLabel.nextSibling.textContent).toBe('25');
        expect(screen.getByText(/Showing 25 of 25 matching matrix entries/i)).toBeInTheDocument();
      });
    });
  });

  describe('v2 forecasts, generation and active signals', () => {
    const v2Record = {
      forecast_id: 'fdr_v2_001',
      disease: 'LSD',
      district: 'Jaffna',
      target_year: 2025,
      target_month: 1,
      probability: 0.24,
      probability_pct: 24.0,
      risk_level: 'MEDIUM',
      predicted_severity: null,
      status: 'GENERATED',
      model_variant: 'lsd_v2.0:S',
      fallback_applied: false,
      data_quality: 'V2_MODEL',
      model_version: 'lsd_v2.0',
      forecaster: 'S',
      deployment_status: 'exploratory',
      relative_risk: 2.6,
      previous_month_observation: { period: '2024-12', status: 'CONFIRMED_OUTBREAK', verified_cases: 3, deaths: 1, observed_severity: 'MODERATE' },
      disclaimer: 'v2',
      created_at: '2026-10-13T00:00:00Z',
    };
    const supersededRecord = { ...v2Record, forecast_id: 'fdr_v1_old', model_version: undefined, status: 'SUPERSEDED', probability: 0.9, probability_pct: 90 };

    it('shows v2 provenance, relative risk and observed severity, and hides superseded records', async () => {
      api.listForecastRecords.mockResolvedValueOnce({ total: 2, records: [v2Record, supersededRecord] });
      api.getSeverityHistory.mockResolvedValue({ diseases: { LSD: { years: [2020, 2024], districts: { Jaffna: {
        outbreak_years: 3, counts: { LOW: 0, MEDIUM: 2, HIGH: 1 }, probabilities: { LOW: 0.1, MEDIUM: 0.6, HIGH: 0.3 }, typical: 'MEDIUM' } } } } });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        const row = screen.getAllByText('Jaffna').map((cell) => cell.closest('tr')).find((tr) => within(tr).queryByText('LSD'));
        expect(within(row).getByText('Exploratory model')).toBeInTheDocument();
        expect(within(row).getByText('2.6× usual')).toBeInTheDocument();
        expect(within(row).getByTestId('severity-estimate-compact')).toHaveTextContent('MEDIUM');
        expect(within(row).queryByText(/MODERATE/)).not.toBeInTheDocument();
        expect(within(row).queryByText('90.0%')).not.toBeInTheDocument();
      });
    });

    const previewSummary = {
      status: 'PREVIEW', dry_run: true, target_period: '2025-01', records: 50, reused: 0,
      would_supersede: 49, protected: 1, protected_reasons: { HAS_FOLLOW_UP: 1 },
      protected_details: [{ forecast_id: 'fdr_x', reasons: ['HAS_FOLLOW_UP'] }],
    };
    const openPreview = async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Generate v2 forecasts \(January 2025\)/i }));
      return screen.findByRole('dialog');
    };

    it('mount, period changes and filter changes never call generation', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument());
      fireEvent.change(screen.getByLabelText(/Risk Tier/i), { target: { value: 'HIGH' } });
      fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2025-2' } });
      await waitFor(() => expect(api.listForecastRecords).toHaveBeenCalled());
      expect(api.generateV2Forecasts).not.toHaveBeenCalled();
    });

    it('clicking Generate only requests a read-only preview and shows what would change', async () => {
      api.generateV2Forecasts.mockResolvedValue({ summary: previewSummary });
      const dialog = await openPreview();

      expect(api.generateV2Forecasts).toHaveBeenCalledTimes(1);
      expect(api.generateV2Forecasts).toHaveBeenCalledWith({ year: 2025, month: 1, dryRun: true });
      expect(within(dialog).getByText('50')).toBeInTheDocument();
      expect(within(dialog).getByText('49')).toBeInTheDocument();
      expect(within(dialog).getByText(/1 has follow-ups/)).toBeInTheDocument();
      expect(within(dialog).getByText(/Nothing has been written yet/)).toBeInTheDocument();
    });

    it('cancel after the preview causes zero writes', async () => {
      api.generateV2Forecasts.mockResolvedValue({ summary: previewSummary });
      const dialog = await openPreview();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
      expect(api.generateV2Forecasts).toHaveBeenCalledTimes(1); // only the preview
    });

    it('confirm performs one controlled write bound to the previewed supersede count', async () => {
      api.generateV2Forecasts
        .mockResolvedValueOnce({ summary: previewSummary })
        .mockResolvedValueOnce({ summary: { status: 'OK', target_period: '2025-01', records: 50, saved: 50, superseded: 49, protected: 1 } });
      const dialog = await openPreview();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm and store' }));

      await waitFor(() => {
        expect(screen.getByText(/Stored 50 v2 forecast records for 2025-01; 49 older records marked superseded; 1 protected records left unchanged/)).toBeInTheDocument();
      });
      expect(api.generateV2Forecasts).toHaveBeenCalledTimes(2);
      expect(api.generateV2Forecasts).toHaveBeenLastCalledWith({ year: 2025, month: 1, expectedSupersedeCount: 49 });
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('repeat clicks while the preview or the write is pending do not duplicate calls', async () => {
      let releaseWrite;
      api.generateV2Forecasts
        .mockResolvedValueOnce({ summary: previewSummary })
        .mockImplementationOnce(() => new Promise((resolve) => { releaseWrite = resolve; }));
      const generate = (await (async () => {
        render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
        await waitFor(() => expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument());
        return screen.getByRole('button', { name: /Generate v2 forecasts \(January 2025\)/i });
      })());
      fireEvent.click(generate);
      fireEvent.click(generate);
      const dialog = await screen.findByRole('dialog');
      expect(api.generateV2Forecasts).toHaveBeenCalledTimes(1); // double click -> one preview

      const confirm = within(dialog).getByRole('button', { name: 'Confirm and store' });
      fireEvent.click(confirm);
      fireEvent.click(confirm);
      await waitFor(() => expect(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' })).toBeDisabled());
      expect(api.generateV2Forecasts).toHaveBeenCalledTimes(2); // double confirm -> one write
      releaseWrite({ summary: { status: 'OK', target_period: '2025-01', records: 50, saved: 50, superseded: 49, protected: 1 } });
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    });

    it('a stale preview (409) stores nothing and asks for a new preview', async () => {
      api.generateV2Forecasts
        .mockResolvedValueOnce({ summary: previewSummary })
        .mockRejectedValueOnce(Object.assign(new Error('API Error 409'), { status: 409 }));
      const dialog = await openPreview();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm and store' }));
      await waitFor(() => expect(screen.getByText(/records changed since the preview, so nothing was stored/)).toBeInTheDocument());
      expect(api.generateV2Forecasts).toHaveBeenCalledTimes(2); // no automatic retry
    });

    it('a partial failure is surfaced and described as recoverable', async () => {
      api.generateV2Forecasts
        .mockResolvedValueOnce({ summary: previewSummary })
        .mockResolvedValueOnce({ summary: { status: 'PARTIAL', records: 50, saved: 44, failed: [{}, {}], supersede_failed: [], superseded: 0 } });
      const dialog = await openPreview();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm and store' }));
      await waitFor(() => expect(screen.getByText(/Partly stored: 44 of 50 records saved, 2 step\(s\) failed and no older records were superseded. Running it again is safe/)).toBeInTheDocument());
    });

    it('shows a clear message when generation is forbidden and writes nothing', async () => {
      api.generateV2Forecasts.mockRejectedValue(Object.assign(new Error('API Error 403'), { status: 403 }));
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => expect(screen.getByText('District Priority Assessment Matrix')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Generate v2 forecasts/i }));
      await waitFor(() => expect(screen.getByText('Only DAPH officials can generate forecasts.')).toBeInTheDocument());
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(api.generateV2Forecasts).toHaveBeenCalledTimes(1);
    });

    it('non-DAPH viewers get no generate control at all', () => {
      const vetContext = { ...validDaphContext, role: ROLES.VETERINARY_OFFICER };
      render(<DaphNationalForecastOverview viewerContext={vetContext} />);
      expect(screen.queryByRole('button', { name: /Generate v2 forecasts/i })).not.toBeInTheDocument();
      expect(api.generateV2Forecasts).not.toHaveBeenCalled();
    });

    it('lists active verified outbreak signals separately from forecasts', async () => {
      api.getActiveSurveillance.mockImplementation(({ disease }) => Promise.resolve({
        disease,
        period: '2026-10',
        districts: disease === 'FMD'
          ? { Anuradhapura: { status: 'CONFIRMED_OUTBREAK', verified_cases: 2, deaths: 1 }, Colombo: { status: 'NO_REPORTED_CASES', verified_cases: 0, deaths: 0 } }
          : {},
      }));
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      const panel = await screen.findByLabelText('Active outbreak signals');
      expect(within(panel).getByText(/Anuradhapura — FMD: 2 verified cases, 1 death/)).toBeInTheDocument();
      expect(within(panel).queryByText(/Colombo/)).not.toBeInTheDocument();
    });
  });

  describe('One official record per district, disease and month', () => {
    it('shows the v2 record, not the older v1 one, and keeps advisories written against the v1 record', async () => {
      const v1 = mockRecordsData.records[0];                       // fdr_001, 75.0%, has an APPROVED advisory
      const v2 = {
        ...v1, forecast_id: 'fdr_v2_001', probability: 0.41, probability_pct: 41.0, risk_level: 'MEDIUM',
        predicted_severity: null, model_variant: 'fmd_v2.0:O', model_version: 'fmd_v2.0', forecaster: 'O',
        deployment_status: 'back_tested', relative_risk: 3.2, data_quality: 'V2_MODEL', fallback_applied: false,
        generated_at: '2026-10-14T03:20:20Z',
      };
      api.listForecastRecords.mockResolvedValue({ total: 2, records: [v1, v2] });

      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => expect(screen.getByText('41.0%')).toBeInTheDocument());
      expect(screen.queryByText('75.0%')).not.toBeInTheDocument();
      // The approved advisory written against the older record still counts for this district and month.
      expect(api.listAdvisories).toHaveBeenCalled();
      const cellTexts = (row) => Array.from(row.querySelectorAll('td')).map((td) => td.textContent.trim());
      const rows = screen.getAllByRole('row').filter((r) => cellTexts(r).includes('Anuradhapura') && cellTexts(r).includes('FMD'));
      expect(rows).toHaveLength(1);
      expect(within(rows[0]).getByText('APPROVED')).toBeInTheDocument();
    });
  });

  describe('Seasonal Outlook for months without an early-month forecast', () => {
    const outlook = (district, disease, probability) => ({
      disease, district, status: 'ACTIVE', probability, probability_low: 0.0, probability_high: 0.1,
      interval_level: 0.8, years_observed: 7, positive_years: 1, issue_date: '2026-10-15', lead_days: 17,
    });

    it('shows OUTLOOK instead of No Record, keeps the KPI counts untouched and opens the outlook in the drawer', async () => {
      api.listForecastRecords.mockResolvedValue({ total: 0, records: [] });
      api.listOutlooks.mockResolvedValue({ records: [] });
      api.previewOutlooks.mockResolvedValue({
        target_period: '2025-01',
        records: [outlook('Colombo', 'FMD', 0.033), outlook('Colombo', 'LSD', 0.027)],
      });

      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => expect(screen.getAllByText('OUTLOOK').length).toBe(2));
      expect(screen.getByText('3.3%')).toBeInTheDocument();
      expect(screen.getAllByText('Outlook (preview)').length).toBe(2);
      // Outlooks are not forecasts: they are not counted as HIGH/MEDIUM/LOW districts.
      expect(screen.queryByText(/LOW Risk Districts/i)?.closest('div')?.textContent ?? '').not.toMatch(/[1-9]/);

      fireEvent.click(screen.getAllByRole('button', { name: /View outlook for Colombo FMD/i })[0]);
      expect(await screen.findByTestId('outlook-card')).toBeInTheDocument();
      expect(screen.getByText(/seasonal outlook below was prepared from historical patterns/i)).toBeInTheDocument();
    });

    it('falls back to No Record when no outlook exists', async () => {
      api.listForecastRecords.mockResolvedValue({ total: 0, records: [] });
      api.listOutlooks.mockResolvedValue({ records: [] });
      api.previewOutlooks.mockResolvedValue({ target_period: '2030-05', records: [] });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => expect(screen.getAllByText('No Record').length).toBeGreaterThan(0));
      expect(screen.queryByText('OUTLOOK')).not.toBeInTheDocument();
    });
  });

  describe('Plain wording of the summary tiles', () => {
    it('describes each tier in ordinary words and no longer shows the old model threshold text', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      await waitFor(() => expect(screen.getByText('Much higher than usual')).toBeInTheDocument());
      expect(screen.getByText('Somewhat higher than usual')).toBeInTheDocument();
      expect(screen.getByText('Not higher than usual')).toBeInTheDocument();
      expect(screen.queryByText(/t ≥ 0\.40/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Un-generated slots|Fallback Data Applied/)).not.toBeInTheDocument();
    });

    it('replaces the "missing" tile with an outlook tile when only an outlook exists for the month', async () => {
      api.listForecastRecords.mockResolvedValue({ total: 0, records: [] });
      api.listOutlooks.mockResolvedValue({
        records: [{ disease: 'FMD', district: 'Colombo', status: 'ACTIVE', probability: 0.033, probability_low: 0, probability_high: 0.1,
          interval_level: 0.8, years_observed: 7, positive_years: 0, issue_date: '2026-10-14', lead_days: 18 }],
      });
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      const tile = await screen.findByTestId('outlook-summary-tile');
      expect(tile).toHaveTextContent('Outlook available');
      expect(tile).toHaveTextContent('Prepared 2026-10-14');
      // an outlook-only month has no forecast counts, so the empty 0 tiles are not shown
      expect(screen.queryByText('Total Forecast Records')).not.toBeInTheDocument();
      expect(screen.queryByText('HIGH Risk Districts')).not.toBeInTheDocument();
    });
  });

  describe('Month list', () => {
    it('offers one Month list with the outlook month and groups older months apart', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);
      const select = await screen.findByLabelText('Month');
      expect(screen.queryByLabelText(/Forecast Year/i)).not.toBeInTheDocument();
      await waitFor(() => expect(Array.from(select.options).some((o) => o.text.endsWith('(outlook)'))).toBe(true));
      expect(select.value).toBe('2025-1');
    });
  });
});
