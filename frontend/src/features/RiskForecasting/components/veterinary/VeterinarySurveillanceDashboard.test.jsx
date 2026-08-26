import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VeterinarySurveillanceDashboard } from './VeterinarySurveillanceDashboard';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('VeterinarySurveillanceDashboard Component', () => {
  const validDistrictVetContext = {
    userId: 'usr_vet_district_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Jaffna', 'Kilinochchi'],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: true,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    },
  };

  const validProvinceVetContext = {
    userId: 'usr_vet_province_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.PROVINCE,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura', 'Polonnaruwa'],
      assignedFarmIds: [],
    },
    permissions: validDistrictVetContext.permissions,
  };

  // 1. Access & Fail-Closed Gating Tests
  describe('Access & Fail-Closed Gating', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewerContext is invalid', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={{ invalid: true }} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects FARMER role', () => {
      const farmerContext = {
        userId: 'usr_farmer_001',
        role: ROLES.FARMER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.FARM,
          registeredFarmDistrict: 'Jaffna',
          authorizedDistricts: ['Jaffna'],
          assignedFarmIds: ['FARM_01'],
        },
        permissions: {},
      };
      render(<VeterinarySurveillanceDashboard viewerContext={farmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects DAPH_OFFICIAL role', () => {
      const daphContext = {
        userId: 'usr_daph_001',
        role: ROLES.DAPH_OFFICIAL,
        authorization: {
          scopeLevel: SCOPE_LEVELS.NATIONAL,
          registeredFarmDistrict: null,
          authorizedDistricts: [],
          assignedFarmIds: [],
        },
        permissions: {},
      };
      render(<VeterinarySurveillanceDashboard viewerContext={daphContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER with FARM scopeLevel', () => {
      const farmScopeVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          scopeLevel: SCOPE_LEVELS.FARM,
        },
      };
      render(<VeterinarySurveillanceDashboard viewerContext={farmScopeVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER with NATIONAL scopeLevel', () => {
      const nationalScopeVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          scopeLevel: SCOPE_LEVELS.NATIONAL,
        },
      };
      render(<VeterinarySurveillanceDashboard viewerContext={nationalScopeVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is missing or null', () => {
      const noDistrictsVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          authorizedDistricts: null,
        },
      };
      render(<VeterinarySurveillanceDashboard viewerContext={noDistrictsVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is empty array', () => {
      const emptyDistrictsVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          authorizedDistricts: [],
        },
      };
      render(<VeterinarySurveillanceDashboard viewerContext={emptyDistrictsVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // 2. Scope Display & Layout Tests
  describe('Authorized Scope & Layout', () => {
    it('accepts valid DISTRICT-scoped veterinary officer', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.getByText('My Surveillance Dashboard')).toBeInTheDocument();
      expect(screen.getByText('DISTRICT')).toBeInTheDocument();
    });

    it('accepts valid PROVINCE-scoped veterinary officer', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validProvinceVetContext} />);
      expect(screen.getByText('My Surveillance Dashboard')).toBeInTheDocument();
      expect(screen.getByText('PROVINCE')).toBeInTheDocument();
    });

    it('displays only explicitly authorized districts from viewerContext without national expansion', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.getByText('Jaffna District')).toBeInTheDocument();
      expect(screen.getByText('Kilinochchi District')).toBeInTheDocument();

      // Confirm no unauthorized expansion
      expect(screen.queryByText('Colombo District')).not.toBeInTheDocument();
      expect(screen.queryByText('Kandy District')).not.toBeInTheDocument();
    });

    it('does NOT render an editable district selector', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
    });
  });

  // 3. UI_READY_API_BLOCKED Dashboard Cards
  describe('UI_READY_API_BLOCKED Dashboard Cards', () => {
    it('renders all 4 integration-unavailable modules with titles and statuses', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);

      expect(screen.getByText('Assigned Farms')).toBeInTheDocument();
      expect(screen.getByText('Surveillance Records')).toBeInTheDocument();
      expect(screen.getByText('Active Alerts')).toBeInTheDocument();
      expect(screen.getByText('Response Activities')).toBeInTheDocument();

      const unavailableBadges = screen.getAllByText('Integration unavailable');
      expect(unavailableBadges).toHaveLength(4);
    });

    it('does NOT describe missing data as zero cases, zero alerts, or all clear', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.queryByText(/^0 active alerts$/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/no active alerts/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/no outbreaks/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/all clear/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/0 cases/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/safe district/i)).not.toBeInTheDocument();
    });

    it('renders zero farm names, operational counts, percentages, or fake dates', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
      expect(screen.queryByText(/FARM_\d+/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Dr\./i)).not.toBeInTheDocument();
      expect(screen.queryByText(/07\d{8}/)).not.toBeInTheDocument();
    });

    it('renders general surveillance responsibilities clearly labelled as general guidelines', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.getByText('General surveillance responsibilities')).toBeInTheDocument();
      expect(
        screen.getByText(/These static reference procedures are not active tasks/i)
      ).toBeInTheDocument();
      expect(screen.getByText('Symptom Review')).toBeInTheDocument();
      expect(screen.getByText('Outbreak Escalation')).toBeInTheDocument();
    });

    it('contains no non-functional action buttons (Complete, Assign, Resolve, Submit Report)', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.queryByRole('button', { name: /complete/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /assign/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /resolve/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /submit/i })).not.toBeInTheDocument();
    });

    it('contains no AI Diagnosis CTA or navigation link', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Diagnose/i)).not.toBeInTheDocument();
    });

    it('contains no technical model outputs (Stage 2, ECE, log-odds, raw JSON)', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
    });
  });

  // 4. Accessibility & Zero Network Calls
  describe('Accessibility & Zero Network Calls', () => {
    it('uses role="status" and aria-live="polite" for the overall integration notice, and not role="alert"', () => {
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);

      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute(
        'aria-labelledby',
        'vet-dashboard-integration-heading'
      );

      // Valid access must NOT render authorization role="alert"
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('hides decorative Material symbols from assistive technology', () => {
      const { container } = render(
        <VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />
      );
      const icons = container.querySelectorAll('.material-symbols-outlined');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('does not mutate input viewerContext prop (deeply frozen object test)', () => {
      const frozenContext = {
        userId: 'usr_vet_frozen_001',
        role: ROLES.VETERINARY_OFFICER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.DISTRICT,
          registeredFarmDistrict: null,
          authorizedDistricts: Object.freeze(['Jaffna', 'Mannar']),
          assignedFarmIds: Object.freeze([]),
        },
        permissions: Object.freeze({
          viewDataQuality: true,
          viewModelTransparency: false,
          manageAlerts: true,
          recordResponse: true,
          viewReports: true,
        }),
      };
      Object.freeze(frozenContext.authorization);
      Object.freeze(frozenContext);

      expect(() => {
        render(<VeterinarySurveillanceDashboard viewerContext={frozenContext} />);
      }).not.toThrow();

      expect(frozenContext.role).toBe(ROLES.VETERINARY_OFFICER);
      expect(frozenContext.authorization.authorizedDistricts).toEqual(['Jaffna', 'Mannar']);
    });

    it('makes zero network or API fetch calls', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });

  // 5. Visual & Responsive Token Contracts
  describe('Visual & Responsive Layout Contracts', () => {
    it('uses max-w-6xl outer container with flex-wrap district scope badges', () => {
      const { container } = render(
        <VeterinarySurveillanceDashboard viewerContext={validDistrictVetContext} />
      );

      const outerContainer = container.firstElementChild;
      expect(outerContainer.className).toContain('max-w-6xl');
      expect(outerContainer.className).toContain('text-on-surface');

      const scopeHeading = screen.getByText('Authorized surveillance area');
      const badgeContainer = scopeHeading.closest('section').querySelector('.flex-wrap');
      expect(badgeContainer).toBeInTheDocument();
    });
  });
});
