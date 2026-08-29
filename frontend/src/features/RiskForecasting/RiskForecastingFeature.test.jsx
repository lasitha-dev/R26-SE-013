import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RiskForecastingFeature } from './RiskForecastingFeature';
import { ROLES, SCOPE_LEVELS } from './contracts/viewerContext';
import * as forecastingNav from './navigation/forecastingNavigation';

vi.mock('./services/riskForecastingWorkflowApi', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    listForecastDistricts: vi.fn().mockResolvedValue({ districts: ['Anuradhapura', 'Polonnaruwa'], month_names: [] }),
    listForecastRecords: vi.fn().mockResolvedValue({ total: 0, records: [] }),
    listAdvisories: vi.fn().mockResolvedValue({ advisories: [] }),
    listNotificationBatches: vi.fn().mockResolvedValue({ batches: [] }),
    listFollowUps: vi.fn().mockResolvedValue({ follow_ups: [] }),
  };
});

describe('RiskForecastingFeature Component', () => {
  const validFarmerContext = Object.freeze({
    userId: 'usr_farmer_feat_001',
    role: ROLES.FARMER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: Object.freeze(['Anuradhapura']),
      assignedFarmIds: Object.freeze(['FARM_ANU_01']),
    }),
    permissions: Object.freeze({
      viewModelTransparency: false,
    }),
  });

  const validVetContext = Object.freeze({
    userId: 'usr_vet_feat_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Polonnaruwa', 'Anuradhapura']),
      assignedFarmIds: Object.freeze([]),
    }),
    permissions: Object.freeze({
      viewModelTransparency: false,
    }),
  });

  const validDaphContext = Object.freeze({
    userId: 'usr_daph_feat_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Anuradhapura', 'Polonnaruwa', 'Kurunegala']),
      assignedFarmIds: Object.freeze([]),
    }),
    permissions: Object.freeze({
      viewDataQuality: true,
      viewModelTransparency: true,
    }),
  });

  // 1. Invalid Access & Fail-Closed Tests
  describe('Invalid Access & Fail-Closed', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<RiskForecastingFeature viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewerContext is invalid', () => {
      render(<RiskForecastingFeature viewerContext={{ invalid: true }} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when role is unknown or invalid', () => {
      const invalidRoleContext = {
        ...validFarmerContext,
        role: 'ADMINISTRATOR',
      };
      render(<RiskForecastingFeature viewerContext={invalidRoleContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when allowed navigation is empty', () => {
      const navSpy = vi.spyOn(forecastingNav, 'getForecastingNavigation').mockReturnValueOnce([]);
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/No authorized forecasting screens/i)).toBeInTheDocument();
      navSpy.mockRestore();
    });

    it('renders no sub-navigation bar when context is invalid', () => {
      render(<RiskForecastingFeature viewerContext={null} />);
      expect(screen.queryByRole('navigation', { name: /Risk Forecasting sub-navigation/i })).not.toBeInTheDocument();
    });

    it('renders no role-specific child screen when context is invalid', () => {
      render(<RiskForecastingFeature viewerContext={null} />);
      expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();
    });

    it('makes zero network or fetch calls when context is invalid', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<RiskForecastingFeature viewerContext={null} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });

  // 2. FARMER Role Tests
  describe('FARMER Role', () => {
    it('initially renders Disease Risk screen for FARMER', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('navigation', { name: /Risk Forecasting sub-navigation/i })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).toBeInTheDocument();
    });

    it('sub-navigation contains only allowed FARMER items', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('button', { name: /Disease Risk/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Alerts & Guidance/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Data Quality/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Surveillance Dashboard/i })).not.toBeInTheDocument();
    });

    it('activates Alerts & Guidance screen when clicked by FARMER', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      const alertsBtn = screen.getByRole('button', { name: /Alerts & Guidance/i });
      fireEvent.click(alertsBtn);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();
    });

    it('Farmer cannot activate Vet or DAPH screen IDs', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.queryByRole('button', { name: /Surveillance Overview/i })).not.toBeInTheDocument();
    });

    it('Farmer without viewModelTransparency permission cannot see Model Transparency button', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();
    });

    it('Farmer with strict viewModelTransparency permission cannot see Model Transparency button (hidden in demo)', () => {
      const farmerWithTransparency = {
        ...validFarmerContext,
        permissions: { viewModelTransparency: true },
      };
      render(<RiskForecastingFeature viewerContext={farmerWithTransparency} />);
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();
    });

    it('preserves registeredFarmDistrict in child screen', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getAllByText(/Anuradhapura/i).length).toBeGreaterThan(0);
    });
  });

  // 3. VETERINARY OFFICER Role Tests
  describe('VETERINARY OFFICER Role', () => {
    it('initially renders Forecast Overview for VETERINARY_OFFICER', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.getByRole('heading', { name: /Veterinary Forecast Overview/i, level: 1 })).toBeInTheDocument();
    });

    it('cannot activate VeterinaryDistrictForecasts (hidden in demo)', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.queryByRole('button', { name: /District Forecasts/i })).not.toBeInTheDocument();
    });

    it('can activate VeterinaryAdvisoryCentre', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      const advisoryBtn = screen.getByRole('button', { name: /Advisory Centre/i });
      fireEvent.click(advisoryBtn);
      expect(screen.getByRole('heading', { name: /Veterinary Officer Advisory Centre/i, level: 2 })).toBeInTheDocument();
    });

    it('can activate VeterinaryForecastAdvisoryHistory', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      const historyBtn = screen.getByRole('button', { name: /Forecast & Advisory History/i });
      fireEvent.click(historyBtn);
      expect(screen.getByRole('heading', { name: /Forecast & Advisory History/i, level: 2 })).toBeInTheDocument();
    });

    it('can activate VeterinaryAssignedFollowUps', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      const followUpsBtn = screen.getByRole('button', { name: /Assigned Follow-Ups/i });
      fireEvent.click(followUpsBtn);
      expect(screen.getByRole('heading', { name: /Assigned Follow-Ups/i, level: 1 })).toBeInTheDocument();
    });

    it('Vet cannot activate District Forecasts', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.queryByRole('button', { name: /District Forecasts/i })).not.toBeInTheDocument();
    });

    it('Vet cannot activate DAPH Surveillance Overview', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.queryByRole('button', { name: /Surveillance Overview/i })).not.toBeInTheDocument();
    });

    it('Vet cannot activate Data Quality', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.queryByRole('button', { name: /Data Quality/i })).not.toBeInTheDocument();
    });

    it('Vet with NATIONAL context fails closed through ViewerContext validation', () => {
      const invalidVetNational = {
        ...validVetContext,
        authorization: {
          ...validVetContext.authorization,
          scopeLevel: SCOPE_LEVELS.NATIONAL,
        },
      };
      render(<RiskForecastingFeature viewerContext={invalidVetNational} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('Vet Model Transparency does not appear even with strict viewModelTransparency permission (hidden in demo)', () => {
      const vetWithTransparency = {
        ...validVetContext,
        permissions: { viewModelTransparency: true },
      };
      render(<RiskForecastingFeature viewerContext={vetWithTransparency} />);
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();
    });
  });

  // 4. DAPH OFFICIAL Role Tests
  describe('DAPH OFFICIAL Role', () => {
    it('initially renders National Forecast Overview for DAPH_OFFICIAL', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /National Forecast Overview/i, level: 1 })).toBeInTheDocument();
    });

    it('can activate Follow-Up Monitoring for DAPH_OFFICIAL', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      const followUpMonitoringBtn = screen.getByRole('button', { name: /Follow-Up Monitoring/i });
      expect(followUpMonitoringBtn).toBeInTheDocument();
      fireEvent.click(followUpMonitoringBtn);
      expect(screen.getByRole('heading', { name: /Follow-Up Monitoring/i, level: 1 })).toBeInTheDocument();
    });

    it('district-forecasts resolves to DaphDistrictForecasts component for DAPH', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      const forecastsBtn = screen.getByRole('button', { name: /District Forecasts/i });
      fireEvent.click(forecastsBtn);
      expect(screen.getByText(/Risk Forecasting Analytics/i)).toBeInTheDocument();
      expect(screen.queryByText(/Veterinary Decision Support/i)).not.toBeInTheDocument();
    });

    it('Data Quality does not appear even when viewDataQuality permission is true (hidden in demo)', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.queryByRole('button', { name: /Data Quality/i })).not.toBeInTheDocument();
    });

    it('Model Transparency does not appear even when viewModelTransparency permission is true (hidden in demo)', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();
    });

    it('DAPH with both permissions does not see Data Quality or Model Transparency', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.queryByRole('button', { name: /Data Quality/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();
    });

    it('DAPH with empty or invalid authorizedDistricts fails closed', () => {
      const invalidDaphDistricts = {
        ...validDaphContext,
        authorization: {
          ...validDaphContext.authorization,
          authorizedDistricts: null,
        },
      };
      render(<RiskForecastingFeature viewerContext={invalidDaphDistricts} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // 5. Context Transitions & State Reset Tests
  describe('Context Transitions', () => {
    it('resets screen when context changes from Farmer to Vet', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.getByRole('heading', { name: /Veterinary Forecast Overview/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).not.toBeInTheDocument();
    });

    it('resets screen when context changes from Vet to DAPH', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.getByRole('heading', { name: /Veterinary Forecast Overview/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /National Forecast Overview/i, level: 1 })).toBeInTheDocument();
    });

    it('resets screen when context changes from DAPH to Farmer', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /National Forecast Overview/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).toBeInTheDocument();
    });

    it('immediately hides navigation and content when valid context changes to invalid', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('navigation', { name: /Risk Forecasting sub-navigation/i })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={null} />);
      expect(screen.queryByRole('navigation', { name: /Risk Forecasting sub-navigation/i })).not.toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('immediately hides hidden navigation tabs and does not mount them even if requested', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.queryByRole('button', { name: /Data Quality/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();
    });

    it('Sequence B: Model Transparency is completely removed and unmountable for any role', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.queryByRole('button', { name: /Model Transparency/i })).not.toBeInTheDocument();
    });

    it('Sequence C: Farmer Alerts & Guidance securely falls back when role changes to DAPH', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      const alertsBtn = screen.getByRole('button', { name: /Alerts & Guidance/i });
      fireEvent.click(alertsBtn);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /National Forecast Overview/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).not.toBeInTheDocument();
    });

    it('Sequence E: Vet transitioning to DAPH preserves valid shared UI boundaries or safely falls back', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.getByRole('heading', { name: /Veterinary Forecast Overview/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /National Forecast Overview/i, level: 1 })).toBeInTheDocument();
    });

    it('does not reset an authorized active screen on equivalent context rerender', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      const alertsBtn = screen.getByRole('button', { name: /Alerts & Guidance/i });
      fireEvent.click(alertsBtn);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={{ ...validFarmerContext }} />);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();
    });

    it('passes new scope/district to child screen when district changes', () => {
      const farmerAnu = validFarmerContext;
      const farmerJaf = {
        ...validFarmerContext,
        authorization: {
          ...validFarmerContext.authorization,
          registeredFarmDistrict: 'Jaffna',
          authorizedDistricts: ['Jaffna'],
        },
      };

      const { rerender } = render(<RiskForecastingFeature viewerContext={farmerAnu} />);
      expect(screen.getAllByText(/Anuradhapura/i).length).toBeGreaterThan(0);

      rerender(<RiskForecastingFeature viewerContext={farmerJaf} />);
      expect(screen.getAllByText(/Jaffna/i).length).toBeGreaterThan(0);
    });


  });

  // 7. Unknown Selection & Boundary Safety
  describe('Unknown Selection & Boundaries', () => {
    it('does not render unauthorized content when an unknown screen ID is active', () => {
      const navSpy = vi.spyOn(forecastingNav, 'getForecastingNavigation').mockReturnValueOnce([
        { id: 'unknown-screen-xyz', label: 'Unknown Screen' },
      ]);
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Screen implementation unavailable/i)).toBeInTheDocument();
      navSpy.mockRestore();
    });

    it('renders exactly one role screen at a time', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /National Forecast Overview/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).not.toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Veterinary Forecast Overview/i, level: 1 })).not.toBeInTheDocument();
    });

    it('sub-navigation reports effective active item with aria-current="page"', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      const diseaseBtn = screen.getByRole('button', { name: /Disease Risk/i });
      expect(diseaseBtn).toHaveAttribute('aria-current', 'page');

      const alertsBtn = screen.getByRole('button', { name: /Alerts & Guidance/i });
      expect(alertsBtn).not.toHaveAttribute('aria-current');
    });

    it('does not import or render AppShell, SideNavBar, or TopHeader', () => {
      render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.queryByRole('navigation', { name: /Main navigation/i })).not.toBeInTheDocument();
      expect(screen.queryByText(/ADRS Core/i)).not.toBeInTheDocument();
    });

    it('does not mutate deeply frozen input viewerContext prop', () => {
      expect(() => {
        render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      }).not.toThrow();
      expect(validFarmerContext.role).toBe(ROLES.FARMER);
    });

    it('container itself performs zero direct fetch calls on render', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<RiskForecastingFeature viewerContext={null} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });
});
