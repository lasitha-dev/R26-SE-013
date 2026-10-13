import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DaphSurveillanceOverview } from './DaphSurveillanceOverview';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('DaphSurveillanceOverview Component', () => {
  const validDistrictDaphContext = {
    userId: 'usr_daph_district_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Colombo', 'Gampaha'],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    },
  };

  const validProvinceDaphContext = {
    userId: 'usr_daph_province_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.PROVINCE,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Kandy', 'Matale', 'Nuwara Eliya'],
      assignedFarmIds: [],
    },
    permissions: validDistrictDaphContext.permissions,
  };

  const validNationalDaphContext = {
    userId: 'usr_daph_national_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Colombo', 'Kandy', 'Galle', 'Jaffna'],
      assignedFarmIds: [],
    },
    permissions: validDistrictDaphContext.permissions,
  };

  // 1. Access & Fail-Closed Gating Tests
  describe('Access & Fail-Closed Gating', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<DaphSurveillanceOverview viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewerContext is invalid', () => {
      render(<DaphSurveillanceOverview viewerContext={{ invalid: true }} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects FARMER role', () => {
      const farmerContext = {
        userId: 'usr_farmer_003',
        role: ROLES.FARMER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.FARM,
          registeredFarmDistrict: 'Colombo',
          authorizedDistricts: ['Colombo'],
          assignedFarmIds: ['FARM_COL_01'],
        },
        permissions: {},
      };
      render(<DaphSurveillanceOverview viewerContext={farmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER role', () => {
      const vetContext = {
        userId: 'usr_vet_003',
        role: ROLES.VETERINARY_OFFICER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.DISTRICT,
          registeredFarmDistrict: null,
          authorizedDistricts: ['Colombo'],
          assignedFarmIds: [],
        },
        permissions: {},
      };
      render(<DaphSurveillanceOverview viewerContext={vetContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects DAPH_OFFICIAL with FARM scopeLevel', () => {
      const farmScopeDaph = {
        ...validDistrictDaphContext,
        authorization: {
          ...validDistrictDaphContext.authorization,
          scopeLevel: SCOPE_LEVELS.FARM,
        },
      };
      render(<DaphSurveillanceOverview viewerContext={farmScopeDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is missing or null', () => {
      const noDistrictsDaph = {
        ...validDistrictDaphContext,
        authorization: {
          ...validDistrictDaphContext.authorization,
          authorizedDistricts: null,
        },
      };
      render(<DaphSurveillanceOverview viewerContext={noDistrictsDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is empty array, including for NATIONAL scope', () => {
      const emptyNationalDaph = {
        ...validNationalDaphContext,
        authorization: {
          ...validNationalDaphContext.authorization,
          authorizedDistricts: [],
        },
      };
      render(<DaphSurveillanceOverview viewerContext={emptyNationalDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // 2. Authorized Scope & Workspace Display
  describe('Authorized Scope & Workspace Display', () => {
    it('accepts DISTRICT-scoped DAPH official with explicit districts', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);
      expect(screen.getByText('Departmental Surveillance Overview')).toBeInTheDocument();
      expect(screen.getByText('DISTRICT')).toBeInTheDocument();
      expect(screen.getByText('Colombo District')).toBeInTheDocument();
      expect(screen.getByText('Gampaha District')).toBeInTheDocument();
    });

    it('accepts PROVINCE-scoped DAPH official with explicit districts', () => {
      render(<DaphSurveillanceOverview viewerContext={validProvinceDaphContext} />);
      expect(screen.getByText('Departmental Surveillance Overview')).toBeInTheDocument();
      expect(screen.getByText('PROVINCE')).toBeInTheDocument();
      expect(screen.getByText('Kandy District')).toBeInTheDocument();
    });

    it('accepts NATIONAL-scoped DAPH official with explicit districts', () => {
      render(<DaphSurveillanceOverview viewerContext={validNationalDaphContext} />);
      expect(screen.getByText('Departmental Surveillance Overview')).toBeInTheDocument();
      expect(screen.getByText('NATIONAL')).toBeInTheDocument();
      expect(screen.getByText('Jaffna District')).toBeInTheDocument();
    });

    it('displays only explicit districts from viewerContext without automatic 25-district expansion', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);
      expect(screen.getByText('Colombo District')).toBeInTheDocument();
      expect(screen.getByText('Gampaha District')).toBeInTheDocument();

      // Unauthorized districts must NOT appear
      expect(screen.queryByText('Anuradhapura District')).not.toBeInTheDocument();
      expect(screen.queryByText('Badulla District')).not.toBeInTheDocument();
    });

    it('does NOT render any district, province, scope, or role selectors', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select province/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select scope/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select role/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/All Sri Lanka/i)).not.toBeInTheDocument();
    });
  });

  // 3. UI_READY_API_BLOCKED Overview Modules & Guardrails
  describe('UI_READY_API_BLOCKED Overview Modules & Guardrails', () => {
    it('renders overall blocked-integration notice explaining unavailable verified data', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText('Surveillance overview is awaiting verified data integration')
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /This interface cannot determine current case, alert or response status until verified surveillance services and backend authorization are connected/i
        )
      ).toBeInTheDocument();
    });

    it('renders all 4 required blocked integration cards', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(screen.getByText('Verified Surveillance Records')).toBeInTheDocument();
      expect(screen.getByText('Authorized Alerts')).toBeInTheDocument();
      expect(screen.getByText('Regional Situation Summaries')).toBeInTheDocument();
      expect(screen.getByText('Response Coordination')).toBeInTheDocument();

      const unavailableBadges = screen.getAllByText('Integration unavailable');
      expect(unavailableBadges).toHaveLength(4);
    });

    it('does NOT describe missing data as zero cases, zero alerts, all clear, or safe region', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/^0 active alerts$/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/no active alerts/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/no outbreaks/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/all clear/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/0 cases/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/safe region/i)).not.toBeInTheDocument();
    });

    it('does NOT render case counts, percentages, maps with invented values, or fake dates', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
      expect(screen.queryByText(/FARM_\d+/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Dr\./i)).not.toBeInTheDocument();
    });

    it('renders general coordination principles visibly labelled as general guidelines', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText('General surveillance coordination principles')
      ).toBeInTheDocument();
      expect(
        screen.getByText(/These static reference principles are not active tasks/i)
      ).toBeInTheDocument();
      expect(screen.getByText('Laboratory Validation')).toBeInTheDocument();
      expect(screen.getByText('Evidence Separation')).toBeInTheDocument();
    });

    it('contains no operational action buttons or forecasting outputs (probabilities, risk tiers, prediction forms)', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(screen.queryByText(/Predict District Risk/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/HIGH RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/MEDIUM RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/LOW RISK/i)).not.toBeInTheDocument();
    });

    it('does NOT render Data Quality or Model Transparency content merely because role is DAPH_OFFICIAL', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/Data Quality/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Model Transparency/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
    });

    it('contains no AI Diagnosis CTA', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
    });
  });

  // 4. Accessibility & Zero Network Calls
  describe('Accessibility & Zero Network Calls', () => {
    it('uses role="status" and aria-live="polite" for the overall integration notice, and not role="alert"', () => {
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);

      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute(
        'aria-labelledby',
        'daph-overview-integration-heading'
      );

      // Valid access must NOT render authorization role="alert"
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('hides decorative Material symbols from assistive technology', () => {
      const { container } = render(
        <DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />
      );
      const icons = container.querySelectorAll('.material-symbols-outlined');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('does not mutate input viewerContext prop (deeply frozen object test)', () => {
      const frozenContext = {
        userId: 'usr_daph_frozen_001',
        role: ROLES.DAPH_OFFICIAL,
        authorization: {
          scopeLevel: SCOPE_LEVELS.NATIONAL,
          registeredFarmDistrict: null,
          authorizedDistricts: Object.freeze(['Colombo', 'Gampaha', 'Kalutara']),
          assignedFarmIds: Object.freeze([]),
        },
        permissions: Object.freeze({
          viewDataQuality: false,
          viewModelTransparency: false,
          manageAlerts: true,
          recordResponse: true,
          viewReports: true,
        }),
      };
      Object.freeze(frozenContext.authorization);
      Object.freeze(frozenContext);

      expect(() => {
        render(<DaphSurveillanceOverview viewerContext={frozenContext} />);
      }).not.toThrow();

      expect(frozenContext.role).toBe(ROLES.DAPH_OFFICIAL);
      expect(frozenContext.authorization.authorizedDistricts).toEqual(['Colombo', 'Gampaha', 'Kalutara']);
    });

    it('makes zero network or API fetch calls', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });

  // 5. Visual & Responsive Token Contracts
  describe('Visual & Responsive Layout Contracts', () => {
    it('uses max-w-6xl outer container with flex-wrap district scope badges', () => {
      const { container } = render(
        <DaphSurveillanceOverview viewerContext={validDistrictDaphContext} />
      );

      const outerContainer = container.firstElementChild;
      expect(outerContainer.className).toContain('max-w-6xl');
      expect(outerContainer.className).toContain('text-on-surface');

      const scopeHeading = screen.getByText('Authorized surveillance scope');
      const badgeContainer = scopeHeading.closest('section').querySelector('.flex-wrap');
      expect(badgeContainer).toBeInTheDocument();
    });
  });
});
