import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DaphNationalForecastOverview } from './DaphNationalForecastOverview';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as api from '../../services/riskForecastingWorkflowApi';

// Mock Api module
vi.mock('../../services/riskForecastingWorkflowApi', () => ({
  listForecastDistricts: vi.fn(),
  listForecastRecords: vi.fn(),
  listAdvisories: vi.fn(),
  listNotificationBatches: vi.fn(),
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
        target_year: 2026,
        target_month: 9,
        probability: 0.75,
        probability_pct: 75.0,
        risk_level: 'HIGH',
        predicted_severity: 'HIGH',
        status: 'GENERATED',
        model_variant: 'FMD_HYBRID_V1',
        data_quality: 'EXACT_REQUESTED_PERIOD',
        fallback_applied: false,
        source_year: 2026,
        source_month: 9,
        data_age_months: 0,
        disclaimer: 'Official forecast disclaimer text.',
        created_at: '2026-08-23T00:00:00Z',
      },
      {
        forecast_id: 'fdr_002',
        disease: 'FMD',
        district: 'Polonnaruwa',
        target_year: 2026,
        target_month: 9,
        probability: 0.35,
        probability_pct: 35.0,
        risk_level: 'MEDIUM',
        predicted_severity: 'MODERATE',
        status: 'GENERATED',
        model_variant: 'FMD_HYBRID_V1',
        data_quality: 'HISTORICAL_FALLBACK_1Y',
        fallback_applied: true, // Amendment 1
        source_year: 2025,
        source_month: 9,
        data_age_months: 12,
        disclaimer: 'Official forecast disclaimer text.',
        created_at: '2026-08-23T00:00:00Z',
      },
      {
        forecast_id: 'fdr_003',
        disease: 'LSD',
        district: 'Jaffna',
        target_year: 2026,
        target_month: 9,
        probability: 0.10,
        probability_pct: 10.0,
        risk_level: 'LOW',
        predicted_severity: 'LOW',
        status: 'GENERATED',
        model_variant: 'LSD_XGB_V1',
        data_quality: 'EXACT_REQUESTED_PERIOD',
        fallback_applied: false,
        source_year: 2026,
        source_month: 9,
        data_age_months: 0,
        disclaimer: 'Official forecast disclaimer text.',
        created_at: '2026-08-23T00:00:00Z',
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
    api.listAdvisories.mockReset().mockResolvedValue(mockAdvisoriesData);
    api.listNotificationBatches.mockReset().mockResolvedValue(mockBatchesData);
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

  // 2. Data Fetching & API Interoperability
  describe('Data Fetching & API Roundtrips', () => {
    it('calls listForecastDistricts, listForecastRecords, listAdvisories, listNotificationBatches on mount', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(api.listForecastDistricts).toHaveBeenCalledTimes(1);
        expect(api.listForecastRecords).toHaveBeenCalledTimes(1);
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
    it('correctly identifies fallback_applied = true as Fallback Proxy in UI', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText(/Fallback Proxy/i)).toBeInTheDocument();
      }, { timeout: 4000 });
    });

    it('accurately counts fallback_applied records in summary cards', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText('Fallback Data Applied')).toBeInTheDocument();
      }, { timeout: 4000 });
    });
  });

  // 4. Missing-Record Semantics (Amendment 3)
  describe('Missing-Record Semantics (Amendment 3)', () => {
    it('displays missing slots calculation for ALL diseases (out of 50)', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        // 50 total slots - 3 present records = 47 missing
        expect(screen.getByText(/Missing District–Disease Forecasts \(out of 50\)/i)).toBeInTheDocument();
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
      expect(screen.getByText(/Official forecast disclaimer text/i)).toBeInTheDocument();
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
      expect(screen.queryByRole('button', { name: /Generate/i })).not.toBeInTheDocument();
    });
  });

  // 7. Target Period & Zero Fabrication Policy
  describe('Target Period & Zero Fabrication Policy', () => {
    it('defaults target period to the latest available official record period', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        const yearSelect = screen.getByLabelText(/Target Year/i);
        expect(yearSelect.value).toBe('2026');
        const monthSelect = screen.getByLabelText(/Target Month/i);
        expect(monthSelect.value).toBe('9');
      });
    });

    it('does NOT automatically select 2030 when a newer available record is from another year', async () => {
      api.listForecastRecords.mockResolvedValueOnce({
        total: 1,
        records: [
          {
            forecast_id: 'fdr_2028',
            district: 'Colombo',
            disease: 'FMD',
            target_year: 2028,
            target_month: 6,
            risk_level: 'HIGH',
            probability: 0.8,
            fallback_applied: false,
          },
        ],
      });

      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        const yearSelect = screen.getByLabelText(/Target Year/i);
        expect(yearSelect.value).toBe('2028');
        expect(yearSelect.value).not.toBe('2030');
      });
    });

    it('ensures "Phase 9 Backend Limit Bound" text is absent from the UI', async () => {
      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /National Forecast Overview/i })).toBeInTheDocument();
      });

      expect(screen.queryByText(/Phase 9 Backend Limit Bound/i)).not.toBeInTheDocument();
    });

    it('displays clear empty state and does NOT auto-generate predictions when no records exist', async () => {
      api.listForecastRecords.mockResolvedValueOnce({ total: 0, records: [] });

      render(<DaphNationalForecastOverview viewerContext={validDaphContext} />);

      await waitFor(() => {
        expect(screen.getByText(/No official forecast records found for selected criteria/i)).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /Generate/i })).not.toBeInTheDocument();
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
        expect(screen.getByText(/No official forecast records found for selected criteria/i)).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /Follow-up/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Issue Operational Follow-Up/i })).not.toBeInTheDocument();
    });
  });
});
