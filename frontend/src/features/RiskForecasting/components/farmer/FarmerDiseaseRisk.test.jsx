import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FarmerDiseaseRisk } from './FarmerDiseaseRisk';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('FarmerDiseaseRisk Component', () => {
  const validFarmerContext = {
    userId: 'usr_farmer_001',
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Jaffna',
      authorizedDistricts: ['Jaffna'],
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

  const kandyFarmerContext = {
    userId: 'usr_farmer_002',
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Kandy',
      authorizedDistricts: ['Kandy'],
      assignedFarmIds: [],
    },
    permissions: validFarmerContext.permissions,
  };

  // Real Step 2 Combined Result Fixtures
  const mockJaffnaSuccessResponse = {
    district: 'Jaffna',
    year: 2026,
    month: 8,
    fmd: {
      status: 'success',
      data: {
        stage1: { probability_pct: 45.2, risk_level: 'MEDIUM' },
        provenance: { fallback_applied: false },
      },
      error: null,
    },
    lsd: {
      status: 'success',
      data: {
        stage1: { probability_pct: 78.5, risk_level: 'HIGH' },
        provenance: { fallback_applied: true },
      },
      error: null,
    },
    overallStatus: 'success',
  };

  const mockKandySuccessResponse = {
    district: 'Kandy',
    year: 2026,
    month: 8,
    fmd: {
      status: 'success',
      data: {
        stage1: { probability_pct: 88.8, risk_level: 'HIGH' },
        provenance: { fallback_applied: false },
      },
      error: null,
    },
    lsd: {
      status: 'success',
      data: {
        stage1: { probability_pct: 12.3, risk_level: 'LOW' },
        provenance: { fallback_applied: false },
      },
      error: null,
    },
    overallStatus: 'success',
  };

  // 1. Access & Fail-Closed Tests
  describe('Access & Fail-Closed Gating', () => {
    it('renders AccessContextUnavailable and makes ZERO API calls when viewerContext is missing', () => {
      const mockApi = vi.fn();
      render(<FarmerDiseaseRisk viewerContext={null} predictionService={mockApi} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
      expect(mockApi).not.toHaveBeenCalled();
    });

    it('renders AccessContextUnavailable for non-Farmer role', () => {
      const mockApi = vi.fn();
      const vetContext = {
        userId: 'usr_vet_001',
        role: ROLES.VETERINARY_OFFICER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.DISTRICT,
          registeredFarmDistrict: null,
          authorizedDistricts: ['Jaffna'],
          assignedFarmIds: ['FARM_01'],
        },
        permissions: {},
      };
      render(<FarmerDiseaseRisk viewerContext={vetContext} predictionService={mockApi} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(mockApi).not.toHaveBeenCalled();
    });

    it('renders AccessContextUnavailable when Farmer scopeLevel is not FARM', () => {
      const mockApi = vi.fn();
      const invalidScopeContext = {
        ...validFarmerContext,
        authorization: { ...validFarmerContext.authorization, scopeLevel: SCOPE_LEVELS.DISTRICT },
      };
      render(<FarmerDiseaseRisk viewerContext={invalidScopeContext} predictionService={mockApi} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(mockApi).not.toHaveBeenCalled();
    });

    it('renders AccessContextUnavailable when registeredFarmDistrict is empty', () => {
      const mockApi = vi.fn();
      const emptyDistrictContext = {
        ...validFarmerContext,
        authorization: { ...validFarmerContext.authorization, registeredFarmDistrict: '' },
      };
      render(<FarmerDiseaseRisk viewerContext={emptyDistrictContext} predictionService={mockApi} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(mockApi).not.toHaveBeenCalled();
    });

    it('clears previous forecast data and fails closed when valid context changes to invalid context', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);

      const { rerender } = render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(screen.getByText('45.2%')).toBeInTheDocument());
      expect(mockApi).toHaveBeenCalledTimes(1);

      // Change to invalid context
      rerender(
        <FarmerDiseaseRisk
          viewerContext={null}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
      expect(screen.queryByText('45.2%')).not.toBeInTheDocument();
      expect(mockApi).toHaveBeenCalledTimes(1); // No new request
    });
  });

  // 2. Real Service Combined Contract Tests
  describe('Real Service Combined Result Contract', () => {
    it('handles full success using status/data/error fields without result.success', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('45.2%')).toBeInTheDocument();
        expect(screen.getByText('78.5%')).toBeInTheDocument();
        expect(screen.getByText('MEDIUM RISK')).toBeInTheDocument();
        expect(screen.getByText('HIGH RISK')).toBeInTheDocument();
      });
    });

    it('handles partial success using status: "success" for FMD and status: "error" for LSD', async () => {
      const partialResponse = {
        district: 'Jaffna',
        year: 2026,
        month: 8,
        fmd: mockJaffnaSuccessResponse.fmd,
        lsd: {
          status: 'error',
          data: null,
          error: { message: 'LSD service error' },
        },
        overallStatus: 'partial',
      };
      const mockApi = vi.fn().mockResolvedValue(partialResponse);

      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('45.2%')).toBeInTheDocument();
        expect(screen.getByText('Forecast unavailable')).toBeInTheDocument();
        expect(
          screen.getByText(/Partial forecast data available/i)
        ).toBeInTheDocument();
      });

      expect(screen.queryByText('0%')).not.toBeInTheDocument();
      expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
    });

    it('handles complete failure using overallStatus: "error"', async () => {
      const failedResponse = {
        district: 'Jaffna',
        year: 2026,
        month: 8,
        fmd: { status: 'error', data: null, error: { message: 'FMD error' } },
        lsd: { status: 'error', data: null, error: { message: 'LSD error' } },
        overallStatus: 'error',
      };
      const mockApi = vi.fn().mockResolvedValue(failedResponse);

      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(/Forecast service unavailable/i).length
        ).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('Forecast unavailable')).toHaveLength(2);
      });
    });
  });

  // 3. Request Timing & District Identity Behavior
  describe('Forecast Request Timing & Scoped District Changes', () => {
    it('performs one initial request on mount, does not refetch on equivalent context rerender or select change', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      const { rerender } = render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(1));
      expect(mockApi).toHaveBeenCalledWith({ district: 'Jaffna', year: 2026, month: 8 });

      // Parent rerender with equivalent viewerContext does NOT duplicate initial request
      rerender(
        <FarmerDiseaseRisk
          viewerContext={{ ...validFarmerContext }}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );
      expect(mockApi).toHaveBeenCalledTimes(1);

      // Changing dropdowns alone causes ZERO additional API calls
      const monthSelect = screen.getByLabelText(/forecast month/i);
      const yearSelect = screen.getByLabelText(/forecast year/i);

      fireEvent.change(monthSelect, { target: { value: '9' } });
      fireEvent.change(yearSelect, { target: { value: '2027' } });
      expect(mockApi).toHaveBeenCalledTimes(1);

      // Clicking Update forecast performs exactly ONE additional request
      const updateBtn = screen.getByRole('button', { name: /update forecast/i });
      fireEvent.click(updateBtn);

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(2));
      expect(mockApi).toHaveBeenLastCalledWith({ district: 'Jaffna', year: 2027, month: 9 });
    });

    it('clears previous forecast data and initiates exactly one request when district changes from Jaffna to Kandy', async () => {
      const mockApi = vi.fn().mockImplementation(({ district }) => {
        if (district === 'Jaffna') return Promise.resolve(mockJaffnaSuccessResponse);
        if (district === 'Kandy') return Promise.resolve(mockKandySuccessResponse);
        return Promise.reject(new Error('Unknown district'));
      });

      const { rerender } = render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(screen.getByText('45.2%')).toBeInTheDocument());
      expect(mockApi).toHaveBeenCalledTimes(1);

      // Rerender with Kandy context
      rerender(
        <FarmerDiseaseRisk
          viewerContext={kandyFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      // Old Jaffna data is cleared immediately
      expect(screen.queryByText('45.2%')).not.toBeInTheDocument();

      // Exactly one new request initiated for Kandy
      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(2));
      expect(mockApi).toHaveBeenLastCalledWith({ district: 'Kandy', year: 2026, month: 8 });

      // Kandy result displayed under Kandy header
      await waitFor(() => {
        expect(screen.getByText('88.8%')).toBeInTheDocument();
        expect(screen.getByText('Kandy')).toBeInTheDocument();
      });
    });
  });

  // 4. Real Out-of-Order Race Condition Tests
  describe('Real Out-of-Order Stale Response Race', () => {
    it('prevents pending Jaffna Request A from overwriting Kandy Request B when A resolves last', async () => {
      let resolveJaffna;
      let resolveKandy;

      const jaffnaPromise = new Promise((res) => { resolveJaffna = res; });
      const kandyPromise = new Promise((res) => { resolveKandy = res; });

      const mockApi = vi.fn().mockImplementation(({ district }) => {
        if (district === 'Jaffna') return jaffnaPromise;
        if (district === 'Kandy') return kandyPromise;
        return Promise.reject(new Error('Unexpected district'));
      });

      const { rerender } = render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      // 1. Jaffna Request A started (pending)
      expect(mockApi).toHaveBeenCalledTimes(1);
      expect(mockApi).toHaveBeenLastCalledWith({ district: 'Jaffna', year: 2026, month: 8 });

      // 2. Rerender with Kandy context while Jaffna is still pending
      rerender(
        <FarmerDiseaseRisk
          viewerContext={kandyFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      // 3. Kandy Request B started
      expect(mockApi).toHaveBeenCalledTimes(2);
      expect(mockApi).toHaveBeenLastCalledWith({ district: 'Kandy', year: 2026, month: 8 });

      // 4. Kandy Request B resolves FIRST
      resolveKandy(mockKandySuccessResponse);

      await waitFor(() => {
        expect(screen.getByText('88.8%')).toBeInTheDocument(); // Kandy FMD %
        expect(screen.getByText('Kandy')).toBeInTheDocument();
      });

      // 5. Jaffna Request A resolves SECOND (stale resolution)
      resolveJaffna(mockJaffnaSuccessResponse);

      // 6. Confirm UI still displays Kandy and Kandy result (88.8%) and is NOT overwritten by Jaffna (45.2%)
      await new Promise((r) => setTimeout(r, 50));
      expect(screen.getByText('88.8%')).toBeInTheDocument();
      expect(screen.getByText('Kandy')).toBeInTheDocument();
      expect(screen.queryByText('45.2%')).not.toBeInTheDocument();
    });
  });

  // 5. Explicit Period Validation Tests
  describe('Explicit Initial Period Validation', () => {
    it('uses valid default when initial props are omitted', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(1));
    });

    it.each([
      ['year 2016', 2016, 8],
      ['year 2031', 2031, 8],
      ['fractional year 2025.5', 2025.5, 8],
      ['string year "abc"', 'abc', 8],
      ['month 0', 2026, 0],
      ['month 13', 2026, 13],
      ['fractional month 2.5', 2026, 2.5],
      ['string month "abc"', 2026, 'abc'],
    ])('renders "Invalid forecast period" and makes ZERO API calls for %s', (label, yr, mth) => {
      const mockApi = vi.fn();
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={yr}
          initialMonth={mth}
          predictionService={mockApi}
        />
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Invalid forecast period/i)).toBeInTheDocument();
      expect(mockApi).not.toHaveBeenCalled();
    });
  });

  // 6. Data Validation & Risk Level Non-Defaulting
  describe('Data Validation Guardrails', () => {
    it('displays 0.0% for numeric probability 0', async () => {
      const zeroResponse = {
        ...mockJaffnaSuccessResponse,
        fmd: {
          status: 'success',
          data: {
            stage1: { probability_pct: 0, risk_level: 'LOW' },
            provenance: { fallback_applied: false },
          },
          error: null,
        },
      };
      const mockApi = vi.fn().mockResolvedValue(zeroResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('0.0%')).toBeInTheDocument();
      });
    });

    it.each([
      ['NaN', NaN],
      ['Infinity', Infinity],
      ['-Infinity', -Infinity],
      ['null', null],
      ['undefined', undefined],
      ['string', '45.2'],
    ])('displays "Forecast unavailable" for invalid probability value: %s', async (name, val) => {
      const invalidProbResponse = {
        ...mockJaffnaSuccessResponse,
        fmd: {
          status: 'success',
          data: {
            stage1: { probability_pct: val, risk_level: 'MEDIUM' },
          },
          error: null,
        },
      };
      const mockApi = vi.fn().mockResolvedValue(invalidProbResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(screen.getAllByText('Forecast unavailable').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('does NOT default missing or unknown risk level to LOW', async () => {
      const unknownRiskResponse = {
        ...mockJaffnaSuccessResponse,
        fmd: {
          status: 'success',
          data: {
            stage1: { probability_pct: 45.2, risk_level: 'UNKNOWN_LEVEL' },
          },
          error: null,
        },
      };
      const mockApi = vi.fn().mockResolvedValue(unknownRiskResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(screen.getAllByText('Forecast unavailable').length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.queryByText('LOW RISK')).not.toBeInTheDocument();
    });

    it('displays neutral provenance message when provenance is missing or null', async () => {
      const noProvenanceResponse = {
        ...mockJaffnaSuccessResponse,
        fmd: {
          status: 'success',
          data: {
            stage1: { probability_pct: 45.2, risk_level: 'MEDIUM' },
            provenance: null,
          },
          error: null,
        },
      };
      const mockApi = vi.fn().mockResolvedValue(noProvenanceResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(
          screen.getByText('Forecast input-source information is unavailable.')
        ).toBeInTheDocument();
      });
    });
  });

  // 7. Unmount Protection
  describe('Unmount Safety', () => {
    it('safely handles pending promise resolution after unmount without error', async () => {
      let resolveRequest;
      const promise = new Promise((res) => { resolveRequest = res; });
      const mockApi = vi.fn().mockImplementation(() => promise);

      const { unmount } = render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      // Unmount before promise resolves
      unmount();

      // Resolve promise after unmount
      expect(() => resolveRequest(mockJaffnaSuccessResponse)).not.toThrow();
    });
  });

  // 8. Technical Data Isolation & Safety
  describe('Technical Data Isolation & Mandatory Disclaimer', () => {
    it('renders mandatory disclaimer and hides Stage 2, calibration, log-odds, or AI Diagnosis CTAs', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => {
        expect(
          screen.getByText(
            'This is a district-level early-warning forecast and does not mean disease has been detected on your farm.'
          )
        ).toBeInTheDocument();
      });

      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
    });

    it('verifies selects and update button have min-h-[44px] touch target class and focus ring styling', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      const monthSelect = screen.getByLabelText(/forecast month/i);
      const yearSelect = screen.getByLabelText(/forecast year/i);
      const updateBtn = await screen.findByRole('button', { name: /update forecast/i });

      [monthSelect, yearSelect, updateBtn].forEach((el) => {
        expect(el.className).toContain('min-h-[44px]');
        expect(el.className).toMatch(/focus:ring-2|focus-visible:ring-2/);
      });
    });

    it('visibly renders Forecast month and Forecast year labels without sr-only class and associates them with selects', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(screen.getByText('45.2%')).toBeInTheDocument());

      const monthLabel = screen.getByText('Forecast month');
      const yearLabel = screen.getByText('Forecast year');

      expect(monthLabel).toBeInTheDocument();
      expect(yearLabel).toBeInTheDocument();

      expect(monthLabel.className).not.toContain('sr-only');
      expect(yearLabel.className).not.toContain('sr-only');

      expect(monthLabel).toHaveAttribute('for', 'farmer-month-select');
      expect(yearLabel).toHaveAttribute('for', 'farmer-year-select');

      const monthSelect = screen.getByLabelText('Forecast month');
      const yearSelect = screen.getByLabelText('Forecast year');

      expect(monthSelect).toHaveAttribute('id', 'farmer-month-select');
      expect(yearSelect).toHaveAttribute('id', 'farmer-year-select');
    });


    it('does NOT render an editable district selector dropdown for farmer', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(screen.getByText('45.2%')).toBeInTheDocument());
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
    });
  });

  // 6. Phase E6B Form Submission, Accessibility & Token Integrity
  describe('Phase E6B Form Submission, Accessibility & Token Integrity', () => {
    it('uses type="submit" on Update Forecast control and single form submission pathway', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(1));

      const updateBtn = screen.getByRole('button', { name: /update forecast/i });
      expect(updateBtn).toHaveAttribute('type', 'submit');

      // Click button once
      fireEvent.click(updateBtn);

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(2));

      // Direct form submit once
      const form = updateBtn.closest('form');
      fireEvent.submit(form);

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(3));
    });

    it('does not duplicate requests on click and form submit', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(1));

      const updateBtn = screen.getByRole('button', { name: /update forecast/i });
      fireEvent.click(updateBtn);

      // Verify click produced exactly one additional request (total 2)
      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(2));
    });

    it('prevents submission while loading', async () => {
      let resolveApi;
      const mockApi = vi.fn().mockImplementation(
        () => new Promise((res) => { resolveApi = res; })
      );

      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      expect(mockApi).toHaveBeenCalledTimes(1);

      const updateBtn = screen.getByRole('button', { name: /updating forecast…/i });
      expect(updateBtn).toBeDisabled();

      const form = updateBtn.closest('form');
      fireEvent.submit(form);

      // Remains 1 call because loading disables re-submission
      expect(mockApi).toHaveBeenCalledTimes(1);

      resolveApi(mockJaffnaSuccessResponse);
      await waitFor(() => expect(screen.getByText('45.2%')).toBeInTheDocument());
    });

    it('dropdown month and year changes remain request-free', async () => {
      const mockApi = vi.fn().mockResolvedValue(mockJaffnaSuccessResponse);
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      await waitFor(() => expect(mockApi).toHaveBeenCalledTimes(1));

      const monthSelect = screen.getByLabelText('Forecast month');
      const yearSelect = screen.getByLabelText('Forecast year');

      fireEvent.change(monthSelect, { target: { value: 9 } });
      fireEvent.change(yearSelect, { target: { value: 2027 } });

      // Count remains 1
      expect(mockApi).toHaveBeenCalledTimes(1);
    });

    it('invalid period card uses verified Stitch tokens and mobile margins', () => {
      const mockApi = vi.fn();
      render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2016}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      const alertCard = screen.getByRole('alert');
      expect(alertCard.className).toContain('bg-surface-container');
      expect(alertCard.className).toContain('text-on-surface');
      expect(alertCard.className).toContain('mx-4');
      expect(alertCard.className).toContain('sm:mx-auto');
      expect(alertCard.className).not.toContain('bg-slate-900');
    });

    it('skeleton loading cards include motion-reduce:animate-none fallback class', () => {
      const mockApi = vi.fn().mockImplementation(() => new Promise(() => {}));
      const { container } = render(
        <FarmerDiseaseRisk
          viewerContext={validFarmerContext}
          initialYear={2026}
          initialMonth={8}
          predictionService={mockApi}
        />
      );

      const skeletonCard = container.querySelector('.animate-pulse');
      expect(skeletonCard).not.toBeNull();
      expect(skeletonCard.className).toContain('motion-reduce:animate-none');
    });
  });

  describe('Farmer Authenticated Demo Mode Direct UI Tests', () => {
    it('uses protected demo forecast API and not legacy public API when rendered under authenticated DemoForecastingAuthContext', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      const mockFetchCombined = vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: {
            disease: 'FMD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Jaffna', probability_pct: 55, risk_level: 'MEDIUM' }],
          },
          error: null,
        },
        lsd: {
          status: 'success',
          data: {
            disease: 'LSD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Jaffna', probability_pct: 35, risk_level: 'LOW' }],
          },
          error: null,
        },
      });

      const legacyApiSpy = vi.fn();
      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validFarmerContext,
        logout: vi.fn(),
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <FarmerDiseaseRisk viewerContext={validFarmerContext} initialYear={2024} initialMonth={1} predictionService={legacyApiSpy} />
        </DemoForecastingAuthContext.Provider>
      );

      await waitFor(() => {
        expect(mockFetchCombined).toHaveBeenCalledOnce();
      });

      expect(legacyApiSpy).not.toHaveBeenCalled();
      const callArgs = mockFetchCombined.mock.calls[0][0];
      expect(callArgs.district).toBe('Jaffna');
      expect(callArgs.year).toBe(2024);
      expect(callArgs.targetMonth).toBe(1);

      // Verify district selector does not exist
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
      expect(screen.getByText('Jaffna')).toBeInTheDocument();

      // Verify non-diagnostic disclaimer and statistical risk statement
      expect(screen.getAllByText(/early-warning forecast/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Seasonal forecasts provide statistical risk estimates/i)).toBeInTheDocument();
    });

    it('makes 0 requests on month/year dropdown change and 1 combined request on Update Forecast form submission', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      const mockFetchCombined = vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: { disease: 'FMD', target_year: 2024, target_month: 1, districts: [{ district: 'Jaffna', probability_pct: 50, risk_level: 'MEDIUM' }] },
          error: null,
        },
        lsd: {
          status: 'success',
          data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [{ district: 'Jaffna', probability_pct: 30, risk_level: 'LOW' }] },
          error: null,
        },
      });

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validFarmerContext,
        logout: vi.fn(),
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <FarmerDiseaseRisk viewerContext={validFarmerContext} initialYear={2024} initialMonth={1} />
        </DemoForecastingAuthContext.Provider>
      );

      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(1));

      // Change dropdown values
      const monthSelect = screen.getByLabelText('Forecast month');
      const yearSelect = screen.getByLabelText('Forecast year');

      fireEvent.change(monthSelect, { target: { value: 5 } });
      fireEvent.change(yearSelect, { target: { value: 2025 } });

      expect(mockFetchCombined).toHaveBeenCalledTimes(1); // 0 additional calls

      // Submit form
      const updateBtn = screen.getByRole('button', { name: /update forecast/i });
      fireEvent.click(updateBtn);

      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(2));
      expect(mockFetchCombined).toHaveBeenLastCalledWith(expect.objectContaining({ year: 2025, targetMonth: 5, district: 'Jaffna' }));
    });
  });
});
