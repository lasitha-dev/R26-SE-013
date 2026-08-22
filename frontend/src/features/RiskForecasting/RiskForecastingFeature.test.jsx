import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RiskForecastingFeature } from './RiskForecastingFeature';
import { ROLES, SCOPE_LEVELS } from './contracts/viewerContext';
import * as forecastingNav from './navigation/forecastingNavigation';

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

    it('Farmer with strict viewModelTransparency permission can activate Model Transparency screen', () => {
      const farmerWithTransparency = {
        ...validFarmerContext,
        permissions: { viewModelTransparency: true },
      };
      render(<RiskForecastingFeature viewerContext={farmerWithTransparency} />);
      const transparencyBtn = screen.getByRole('button', { name: /Model Transparency/i });
      expect(transparencyBtn).toBeInTheDocument();

      fireEvent.click(transparencyBtn);
      expect(screen.getByText(/How to understand your forecast/i)).toBeInTheDocument();
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

    it('can activate VeterinaryDistrictForecasts', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      const forecastsBtn = screen.getByRole('button', { name: /District Forecasts/i });
      fireEvent.click(forecastsBtn);
      expect(screen.getByRole('heading', { name: /District Risk Forecasts/i, level: 1 })).toBeInTheDocument();
      expect(screen.getByText(/Veterinary Decision Support/i)).toBeInTheDocument();
    });

    it('district-forecasts resolves to VeterinaryDistrictForecasts component for Vet', () => {
      render(<RiskForecastingFeature viewerContext={validVetContext} />);
      const forecastsBtn = screen.getByRole('button', { name: /District Forecasts/i });
      fireEvent.click(forecastsBtn);
      expect(screen.getByText(/Veterinary Decision Support/i)).toBeInTheDocument();
      expect(screen.queryByText(/Departmental Decision Support/i)).not.toBeInTheDocument();
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

    it('Vet Model Transparency appears only with strict viewModelTransparency permission', () => {
      const vetWithTransparency = {
        ...validVetContext,
        permissions: { viewModelTransparency: true },
      };
      render(<RiskForecastingFeature viewerContext={vetWithTransparency} />);
      const transparencyBtn = screen.getByRole('button', { name: /Model Transparency/i });
      expect(transparencyBtn).toBeInTheDocument();

      fireEvent.click(transparencyBtn);
      expect(screen.getByText(/Operational model interpretation/i)).toBeInTheDocument();
    });
  });

  // 4. DAPH OFFICIAL Role Tests
  describe('DAPH OFFICIAL Role', () => {
    it('initially renders Surveillance Overview for DAPH_OFFICIAL', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
    });

    it('district-forecasts resolves to DaphDistrictForecasts component for DAPH', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      const forecastsBtn = screen.getByRole('button', { name: /District Forecasts/i });
      fireEvent.click(forecastsBtn);
      expect(screen.getByText(/Departmental Decision Support/i)).toBeInTheDocument();
      expect(screen.queryByText(/Veterinary Decision Support/i)).not.toBeInTheDocument();
    });

    it('Data Quality appears when viewDataQuality permission is true', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      const dqBtn = screen.getByRole('button', { name: /Data Quality/i });
      expect(dqBtn).toBeInTheDocument();

      fireEvent.click(dqBtn);
      expect(screen.getByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).toBeInTheDocument();
    });

    it('Model Transparency appears when viewModelTransparency permission is true', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      const mtBtn = screen.getByRole('button', { name: /Model Transparency/i });
      expect(mtBtn).toBeInTheDocument();

      fireEvent.click(mtBtn);
      expect(screen.getByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).toBeInTheDocument();
    });

    it('DAPH with both permissions sees both capability items in sub-navigation', () => {
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('button', { name: /Data Quality/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Model Transparency/i })).toBeInTheDocument();
    });

    it('DAPH with empty authorizedDistricts fails closed', () => {
      const invalidDaphDistricts = {
        ...validDaphContext,
        authorization: {
          ...validDaphContext.authorization,
          authorizedDistricts: [],
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
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
    });

    it('resets screen when context changes from DAPH to Farmer', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();

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

    it('immediately renders authorized fallback when viewDataQuality permission is removed', () => {
      const daphWithDq = { ...validDaphContext, permissions: { viewDataQuality: true } };
      const daphWithoutDq = { ...validDaphContext, permissions: { viewDataQuality: false } };

      const { rerender } = render(<RiskForecastingFeature viewerContext={daphWithDq} />);
      const dqBtn = screen.getByRole('button', { name: /Data Quality/i });
      fireEvent.click(dqBtn);
      expect(screen.getByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={daphWithoutDq} />);
      expect(screen.queryByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
    });

    it('immediately renders authorized fallback when viewModelTransparency permission is removed', () => {
      const daphWithMt = { ...validDaphContext, permissions: { viewModelTransparency: true } };
      const daphWithoutMt = { ...validDaphContext, permissions: { viewModelTransparency: false } };

      const { rerender } = render(<RiskForecastingFeature viewerContext={daphWithMt} />);
      const mtBtn = screen.getByRole('button', { name: /Model Transparency/i });
      fireEvent.click(mtBtn);
      expect(screen.getByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={daphWithoutMt} />);
      expect(screen.queryByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
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

    it('swaps rendered component when transitioning from Vet district-forecasts to DAPH district-forecasts', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validVetContext} />);
      const vetForecastsBtn = screen.getByRole('button', { name: /District Forecasts/i });
      fireEvent.click(vetForecastsBtn);
      expect(screen.getByText(/Veterinary Decision Support/i)).toBeInTheDocument();

      rerender(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByText(/Departmental Decision Support/i)).toBeInTheDocument();
      expect(screen.queryByText(/Veterinary Decision Support/i)).not.toBeInTheDocument();
    });
  });

  // 6. Stored Selection Synchronization & Regression Sequences
  describe('Stored Selection Synchronization & Regression Sequences', () => {
    it('Sequence A: Data Quality does not return automatically when viewDataQuality is restored', () => {
      const daphWithDq = { ...validDaphContext, permissions: { viewDataQuality: true } };
      const daphWithoutDq = { ...validDaphContext, permissions: { viewDataQuality: false } };

      const { rerender } = render(<RiskForecastingFeature viewerContext={daphWithDq} />);
      const dqBtn = screen.getByRole('button', { name: /Data Quality/i });
      fireEvent.click(dqBtn);
      expect(screen.getByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).toBeInTheDocument();

      // Remove permission
      rerender(<RiskForecastingFeature viewerContext={daphWithoutDq} />);
      expect(screen.queryByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();

      // Restore permission
      rerender(<RiskForecastingFeature viewerContext={daphWithDq} />);
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).not.toBeInTheDocument();
    });

    it('Sequence B (DAPH): Model Transparency does not return automatically when permission is restored', () => {
      const daphWithMt = { ...validDaphContext, permissions: { viewModelTransparency: true } };
      const daphWithoutMt = { ...validDaphContext, permissions: { viewModelTransparency: false } };

      const { rerender } = render(<RiskForecastingFeature viewerContext={daphWithMt} />);
      const mtBtn = screen.getByRole('button', { name: /Model Transparency/i });
      fireEvent.click(mtBtn);
      expect(screen.getByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).toBeInTheDocument();

      // Remove permission
      rerender(<RiskForecastingFeature viewerContext={daphWithoutMt} />);
      expect(screen.queryByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();

      // Restore permission
      rerender(<RiskForecastingFeature viewerContext={daphWithMt} />);
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).not.toBeInTheDocument();
    });

    it('Sequence B (Farmer): Model Transparency does not return automatically when permission is restored', () => {
      const farmerWithMt = { ...validFarmerContext, permissions: { viewModelTransparency: true } };
      const farmerWithoutMt = { ...validFarmerContext, permissions: { viewModelTransparency: false } };

      const { rerender } = render(<RiskForecastingFeature viewerContext={farmerWithMt} />);
      const mtBtn = screen.getByRole('button', { name: /Model Transparency/i });
      fireEvent.click(mtBtn);
      expect(screen.getByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).toBeInTheDocument();

      // Remove permission
      rerender(<RiskForecastingFeature viewerContext={farmerWithoutMt} />);
      expect(screen.queryByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).toBeInTheDocument();

      // Restore permission
      rerender(<RiskForecastingFeature viewerContext={farmerWithMt} />);
      expect(screen.getByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Model Transparency & Explainability/i, level: 1 })).not.toBeInTheDocument();
    });

    it('Sequence C: Farmer Alerts & Guidance does not return after Farmer -> Vet -> Farmer role changes', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      const alertsBtn = screen.getByRole('button', { name: /Alerts & Guidance/i });
      fireEvent.click(alertsBtn);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();

      // Change to Vet
      rerender(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.getByRole('heading', { name: /Veterinary Forecast Overview/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).not.toBeInTheDocument();

      // Change back to Farmer
      rerender(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).not.toBeInTheDocument();
    });

    it('Sequence D: Valid -> Invalid -> Valid context does not resurrect previous non-default selection', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      const alertsBtn = screen.getByRole('button', { name: /Alerts & Guidance/i });
      fireEvent.click(alertsBtn);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();

      // Render invalid context
      rerender(<RiskForecastingFeature viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).not.toBeInTheDocument();

      // Restore valid context
      rerender(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      expect(screen.getByRole('heading', { name: /Disease Risk in My Area/i, level: 1 })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).not.toBeInTheDocument();
    });

    it('Sequence E: Shared district-forecasts ID stays active across Vet -> DAPH -> Vet transitions', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validVetContext} />);
      const vetForecastsBtn = screen.getByRole('button', { name: /District Forecasts/i });
      fireEvent.click(vetForecastsBtn);
      expect(screen.getByText(/Veterinary Decision Support/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /District Forecasts/i })).toHaveAttribute('aria-current', 'page');

      // Change directly to DAPH
      rerender(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(screen.getByText(/Departmental Decision Support/i)).toBeInTheDocument();
      expect(screen.queryByText(/Veterinary Decision Support/i)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /District Forecasts/i })).toHaveAttribute('aria-current', 'page');

      // Change directly back to Vet
      rerender(<RiskForecastingFeature viewerContext={validVetContext} />);
      expect(screen.getByText(/Veterinary Decision Support/i)).toBeInTheDocument();
      expect(screen.queryByText(/Departmental Decision Support/i)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /District Forecasts/i })).toHaveAttribute('aria-current', 'page');
    });

    it('Sequence F: Equivalent context rerender preserves authorized selection without unnecessary reset', () => {
      const { rerender } = render(<RiskForecastingFeature viewerContext={validFarmerContext} />);
      const alertsBtn = screen.getByRole('button', { name: /Alerts & Guidance/i });
      fireEvent.click(alertsBtn);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();

      // Rerender with equivalent context object
      rerender(<RiskForecastingFeature viewerContext={{ ...validFarmerContext }} />);
      expect(screen.getByRole('heading', { name: /Alerts & Guidance/i, level: 1 })).toBeInTheDocument();
    });

    it('Sequence G: Transient safety asserts unauthorized content is immediately absent on rerender', () => {
      const daphWithDq = { ...validDaphContext, permissions: { viewDataQuality: true } };
      const daphWithoutDq = { ...validDaphContext, permissions: { viewDataQuality: false } };

      const { rerender } = render(<RiskForecastingFeature viewerContext={daphWithDq} />);
      fireEvent.click(screen.getByRole('button', { name: /Data Quality/i }));
      expect(screen.getByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).toBeInTheDocument();

      // Synchronous rerender assertion pass without waitFor
      rerender(<RiskForecastingFeature viewerContext={daphWithoutDq} />);
      expect(screen.queryByRole('heading', { name: /Data Quality & Input Provenance/i, level: 1 })).toBeNull();
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
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
      expect(screen.getByRole('heading', { name: /Departmental Surveillance Overview/i, level: 1 })).toBeInTheDocument();
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
      render(<RiskForecastingFeature viewerContext={validDaphContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });
});
