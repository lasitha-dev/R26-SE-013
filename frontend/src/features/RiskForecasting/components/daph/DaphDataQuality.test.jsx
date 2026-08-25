import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { DaphDataQuality } from './DaphDataQuality';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('DaphDataQuality Component', () => {
  const validDistrictDaphContext = {
    userId: 'usr_daph_dq_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura', 'Polonnaruwa'],
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

  const validProvinceDaphContext = {
    userId: 'usr_daph_dq_002',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.PROVINCE,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura', 'Polonnaruwa'],
      assignedFarmIds: [],
    },
    permissions: validDistrictDaphContext.permissions,
  };

  const validNationalDaphContext = {
    userId: 'usr_daph_dq_003',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura', 'Polonnaruwa', 'Kegalle'],
      assignedFarmIds: [],
    },
    permissions: validDistrictDaphContext.permissions,
  };

  // 1. Access & Strict Capability Gating Tests
  describe('Access & Strict Capability Gating', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<DaphDataQuality viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewerContext is invalid', () => {
      render(<DaphDataQuality viewerContext={{ invalid: true }} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects FARMER role even when viewDataQuality permission is true', () => {
      const farmerContext = {
        userId: 'usr_farmer_dq',
        role: ROLES.FARMER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.FARM,
          registeredFarmDistrict: 'Anuradhapura',
          authorizedDistricts: ['Anuradhapura'],
          assignedFarmIds: ['FARM_ANU_01'],
        },
        permissions: { viewDataQuality: true },
      };
      render(<DaphDataQuality viewerContext={farmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER role even when viewDataQuality permission is true', () => {
      const vetContext = {
        userId: 'usr_vet_dq',
        role: ROLES.VETERINARY_OFFICER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.DISTRICT,
          registeredFarmDistrict: null,
          authorizedDistricts: ['Anuradhapura'],
          assignedFarmIds: [],
        },
        permissions: { viewDataQuality: true },
      };
      render(<DaphDataQuality viewerContext={vetContext} />);
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
      render(<DaphDataQuality viewerContext={farmScopeDaph} />);
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
      render(<DaphDataQuality viewerContext={noDistrictsDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is an empty array, including under NATIONAL scope', () => {
      const emptyNationalDaph = {
        ...validNationalDaphContext,
        authorization: {
          ...validNationalDaphContext.authorization,
          authorizedDistricts: [],
        },
      };
      render(<DaphDataQuality viewerContext={emptyNationalDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when viewDataQuality permission is false', () => {
      const noPermissionDaph = {
        ...validDistrictDaphContext,
        permissions: {
          ...validDistrictDaphContext.permissions,
          viewDataQuality: false,
        },
      };
      render(<DaphDataQuality viewerContext={noPermissionDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when viewDataQuality permission is absent', () => {
      const missingPermissionDaph = {
        ...validDistrictDaphContext,
        permissions: {},
      };
      render(<DaphDataQuality viewerContext={missingPermissionDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when viewDataQuality is string "true" (strict boolean check)', () => {
      const stringPermissionDaph = {
        ...validDistrictDaphContext,
        permissions: {
          ...validDistrictDaphContext.permissions,
          viewDataQuality: 'true',
        },
      };
      render(<DaphDataQuality viewerContext={stringPermissionDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when viewDataQuality is numeric 1', () => {
      const numberPermissionDaph = {
        ...validDistrictDaphContext,
        permissions: {
          ...validDistrictDaphContext.permissions,
          viewDataQuality: 1,
        },
      };
      render(<DaphDataQuality viewerContext={numberPermissionDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // 2. Authorized Scope & Workspace Display
  describe('Authorized Scope & Workspace Display', () => {
    it('accepts valid DISTRICT-scoped DAPH official with strict true viewDataQuality', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);
      expect(screen.getByText('Data Quality & Input Provenance')).toBeInTheDocument();
      expect(screen.getByText('DISTRICT')).toBeInTheDocument();
      expect(screen.getByText('Anuradhapura District')).toBeInTheDocument();
      expect(screen.getByText('Polonnaruwa District')).toBeInTheDocument();
    });

    it('accepts valid PROVINCE-scoped DAPH official with strict true viewDataQuality', () => {
      render(<DaphDataQuality viewerContext={validProvinceDaphContext} />);
      expect(screen.getByText('Data Quality & Input Provenance')).toBeInTheDocument();
      expect(screen.getByText('PROVINCE')).toBeInTheDocument();
    });

    it('accepts valid NATIONAL-scoped DAPH official with explicit districts and strict true viewDataQuality', () => {
      render(<DaphDataQuality viewerContext={validNationalDaphContext} />);
      expect(screen.getByText('Data Quality & Input Provenance')).toBeInTheDocument();
      expect(screen.getByText('NATIONAL')).toBeInTheDocument();
      expect(screen.getByText('Kegalle District')).toBeInTheDocument();
    });

    it('displays only explicit districts from viewerContext without automatic national expansion', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);
      expect(screen.getByText('Anuradhapura District')).toBeInTheDocument();
      expect(screen.getByText('Polonnaruwa District')).toBeInTheDocument();

      // Unauthorized districts must NOT appear
      expect(screen.queryByText('Colombo District')).not.toBeInTheDocument();
      expect(screen.queryByText('Jaffna District')).not.toBeInTheDocument();
    });

    it('does NOT render any district, province, scope, or role selectors', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select scope/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select role/i)).not.toBeInTheDocument();
    });

    it('renders the scientific boundaries section with health_and_safety and no biomedical identifier', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      const boundariesHeading = screen.getByRole('heading', {
        name: /Scientific Interpretation Boundaries/i,
        level: 2,
      });
      const boundariesSection = boundariesHeading.closest('section');

      expect(within(boundariesSection).getByText('health_and_safety')).toBeInTheDocument();
      expect(within(boundariesSection).queryByText('biomedical')).not.toBeInTheDocument();
    });
  });

  // 3. UI_READY_API_BLOCKED Metrics & Provenance Concepts
  describe('UI_READY_API_BLOCKED Metrics & Provenance Concepts', () => {
    it('renders live-integration notice explaining awaiting metrics', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText('Live data-quality metrics are awaiting secure integration')
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Backend forecasting responses contain provenance and fallback information, but secure scoped retrieval is not connected/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Missing metrics must not be interpreted as complete, current or high-quality data/i
        )
      ).toBeInTheDocument();
    });

    it('renders 4 blocked metric cards with "Live metric unavailable"', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(screen.getByText('Current-Period Input Availability')).toBeInTheDocument();
      expect(screen.getByText('Historical Fallback Usage')).toBeInTheDocument();
      expect(screen.getByText('District Provenance Coverage')).toBeInTheDocument();
      expect(screen.getByText('Data-Quality Review Status')).toBeInTheDocument();

      const unavailableBadges = screen.getAllByText('Live metric unavailable');
      expect(unavailableBadges).toHaveLength(4);
    });

    it('contains zero percentages, counts, progress bars, or fake scores', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      expect(screen.queryByText(/100%/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Score/i)).not.toBeInTheDocument();
    });

    it('displays verified backend provenance concepts (data_quality, fallback_applied, FMDDataProvenance, LSDDataProvenance)', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText(/Input Sourcing Provenance \(data_quality\)/i)
      ).toBeInTheDocument();
      expect(
        screen.getAllByText(/EXACT_REQUESTED_PERIOD/i).length
      ).toBeGreaterThan(0);
      expect(
        screen.getByText(/FMD Provenance Architecture \(FMDDataProvenance\)/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/LSD Target Autocorrelation & Provenance \(LSDDataProvenance\)/i)
      ).toBeInTheDocument();
    });

    it('explains model_fallback_applied generically without feature counts or model-variant transitions', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText(
          /Model fallback metadata records whether the backend used its compatible fallback prediction path when the preferred input configuration was unavailable/i
        )
      ).toBeInTheDocument();

      // Verify exact model-variant feature transition texts are ABSENT
      expect(screen.queryByText(/31-to-30/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/28-to-27/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/31 feature/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/30 feature/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/28 feature/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/27 feature/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/feature variants/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/feature counts/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/RandomForestClassifier/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/ElasticNet/i)).not.toBeInTheDocument();
    });

    it('explains LSD lag1_status meanings (VERIFIED_OBSERVATION or UNAVAILABLE) without displaying a live lag1_value', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText(/VERIFIED_OBSERVATION or UNAVAILABLE/i)
      ).toBeInTheDocument();
      expect(screen.queryByText(/lag1_value/i)).not.toBeInTheDocument();
    });

    it('explains fallback usage without calling fallback an automatic model failure', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText(
          /Fallback is an input sourcing mechanism for missing data and does not automatically represent model failure/i
        )
      ).toBeInTheDocument();
    });

    it('distinguishes data quality from prediction probability and excludes farm-level conclusions', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText(
          /Data provenance describes input sourcing and feature availability, not prediction certainty or outbreak probability/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /nor can any farm-level conclusions be derived/i
        )
      ).toBeInTheDocument();
    });

    it('does NOT render Model Transparency fields (Stage 2, ECE, log_odds, prediction set, etc.)', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/prediction_set/i)).not.toBeInTheDocument();
    });

    it('allows viewer with viewModelTransparency = false to access screen when viewDataQuality = true', () => {
      const transparencyFalseContext = {
        ...validDistrictDaphContext,
        permissions: {
          viewDataQuality: true,
          viewModelTransparency: false,
        },
      };
      render(<DaphDataQuality viewerContext={transparencyFalseContext} />);
      expect(screen.getByText('Data Quality & Input Provenance')).toBeInTheDocument();
    });

    it('contains no AI Diagnosis CTA', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);
      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
    });
  });

  // 4. Accessibility & Zero Network Calls
  describe('Accessibility & Zero Network Calls', () => {
    it('uses role="status" and aria-live="polite" for the overall integration notice, and not role="alert"', () => {
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);

      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute(
        'aria-labelledby',
        'daph-dq-integration-heading'
      );

      // Valid access must NOT render authorization role="alert"
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('hides decorative Material symbols from assistive technology', () => {
      const { container } = render(
        <DaphDataQuality viewerContext={validDistrictDaphContext} />
      );
      const icons = container.querySelectorAll('.material-symbols-outlined');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('does not mutate input viewerContext prop (deeply frozen object test)', () => {
      const frozenContext = {
        userId: 'usr_daph_frozen_dq',
        role: ROLES.DAPH_OFFICIAL,
        authorization: {
          scopeLevel: SCOPE_LEVELS.NATIONAL,
          registeredFarmDistrict: null,
          authorizedDistricts: Object.freeze(['Anuradhapura', 'Polonnaruwa']),
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
        render(<DaphDataQuality viewerContext={frozenContext} />);
      }).not.toThrow();

      expect(frozenContext.role).toBe(ROLES.DAPH_OFFICIAL);
      expect(frozenContext.authorization.authorizedDistricts).toEqual(['Anuradhapura', 'Polonnaruwa']);
    });

    it('makes zero network or API fetch calls', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<DaphDataQuality viewerContext={validDistrictDaphContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });

  // 5. Visual & Responsive Token Contracts
  describe('Visual & Responsive Layout Contracts', () => {
    it('uses max-w-6xl outer container with flex-wrap district scope badges and break-words for provenance text', () => {
      const { container } = render(
        <DaphDataQuality viewerContext={validDistrictDaphContext} />
      );

      const outerContainer = container.firstElementChild;
      expect(outerContainer.className).toContain('max-w-6xl');
      expect(outerContainer.className).toContain('text-on-surface');

      const scopeHeading = screen.getByText('Authorized data-quality scope');
      const badgeContainer = scopeHeading.closest('section').querySelector('.flex-wrap');
      expect(badgeContainer).toBeInTheDocument();

      const breakWordsElements = container.querySelectorAll('.break-words');
      expect(breakWordsElements.length).toBeGreaterThan(0);
    });

    it('contains no action/export buttons or graphical charts/gauges', () => {
      const { container } = render(
        <DaphDataQuality viewerContext={validDistrictDaphContext} />
      );

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(container.querySelector('svg')).not.toBeInTheDocument();
      expect(container.querySelector('canvas')).not.toBeInTheDocument();
    });
  });
});
