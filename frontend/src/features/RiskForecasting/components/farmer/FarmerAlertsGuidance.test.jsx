import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FarmerAlertsGuidance } from './FarmerAlertsGuidance';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('FarmerAlertsGuidance Component', () => {
  const validFarmerContext = {
    userId: 'usr_farmer_101',
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: ['FARM_ANU_01'],
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: false,
      recordResponse: false,
      viewReports: false,
    },
  };

  // 1. Access & Fail-Closed Tests
  describe('Access & Fail-Closed Gating', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<FarmerAlertsGuidance viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewerContext is invalid', () => {
      render(<FarmerAlertsGuidance viewerContext={{ invalid: true }} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('prevents VETERINARY_OFFICER from accessing the farmer screen', () => {
      const vetContext = {
        userId: 'usr_vet_101',
        role: ROLES.VETERINARY_OFFICER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.DISTRICT,
          registeredFarmDistrict: null,
          authorizedDistricts: ['Anuradhapura'],
          assignedFarmIds: [],
        },
        permissions: {},
      };
      render(<FarmerAlertsGuidance viewerContext={vetContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('prevents DAPH_OFFICIAL from accessing the farmer screen', () => {
      const daphContext = {
        userId: 'usr_daph_101',
        role: ROLES.DAPH_OFFICIAL,
        authorization: {
          scopeLevel: SCOPE_LEVELS.NATIONAL,
          registeredFarmDistrict: null,
          authorizedDistricts: [],
          assignedFarmIds: [],
        },
        permissions: {},
      };
      render(<FarmerAlertsGuidance viewerContext={daphContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when Farmer scopeLevel is not FARM', () => {
      const invalidScopeContext = {
        ...validFarmerContext,
        authorization: {
          ...validFarmerContext.authorization,
          scopeLevel: SCOPE_LEVELS.NATIONAL,
        },
      };
      render(<FarmerAlertsGuidance viewerContext={invalidScopeContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when registeredFarmDistrict is missing or empty', () => {
      const emptyDistrictContext = {
        ...validFarmerContext,
        authorization: {
          ...validFarmerContext.authorization,
          registeredFarmDistrict: '',
        },
      };
      render(<FarmerAlertsGuidance viewerContext={emptyDistrictContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // 2. Integration State & Render Tests
  describe('UI_READY_API_BLOCKED Integration State', () => {
    it('displays registered district name for authorized farmer', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.getByText(/Anuradhapura District/i)).toBeInTheDocument();
    });

    it('does NOT render an editable district selector', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
    });

    it('renders the integration-unavailable panel with required title and disclaimer', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(
        screen.getByText('Personalized alerts are not connected yet')
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Verified outbreak alerts are currently unavailable/i)
      ).toBeInTheDocument();
    });

    it('does NOT claim "0 active alerts", "No active alerts", "No outbreaks", "All clear", or "Your farm is safe"', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.queryByText(/^no alerts$/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/0 active alerts/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/no active alerts/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/all clear/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/no outbreaks/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/your farm is safe/i)).not.toBeInTheDocument();
    });

    it('renders general preventive guidance and labels it clearly as general non-personalized guidance', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.getByText('General preventive guidance')).toBeInTheDocument();
      expect(
        screen.getByText(/These general educational guidelines are not personalized/i)
      ).toBeInTheDocument();
      expect(screen.getByText('Animal Isolation')).toBeInTheDocument();
      expect(screen.getByText('Equipment Sanitation')).toBeInTheDocument();
    });

    it('distinguishes forecasting from diagnosis and confirmed alerts', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(
        screen.getByText(
          /Disease forecasting cannot confirm infection in an individual animal/i
        )
      ).toBeInTheDocument();
    });
  });

  // 3. Scientific Guardrails & Data Absence
  describe('Scientific Guardrails & Technical Data Isolation', () => {
    it('contains no fake alert cards, dates, case counts, phone numbers or fabricated identities', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.queryByText(/cases/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/07\d{8}/)).not.toBeInTheDocument();
      expect(screen.queryByText(/hotline/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Dr\./i)).not.toBeInTheDocument();
    });

    it('contains no farm-level risk percentage', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    });

    it('contains no AI Diagnosis CTA or navigation link', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Diagnose/i)).not.toBeInTheDocument();
    });

    it('contains no technical model outputs (Stage 2, ECE, log-odds, raw JSON)', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
    });
  });

  // 4. Zero Network Calls & Accessibility
  describe('Zero Network Calls & Accessibility Compliance', () => {
    it('makes zero network or API fetch calls', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });

    it('renders the integration-unavailable panel as an accessible status region with aria-live="polite" and not role="alert"', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);

      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute('aria-labelledby', 'alerts-integration-heading');

      const heading = screen.getByText('Personalized alerts are not connected yet');
      expect(heading).toHaveAttribute('id', 'alerts-integration-heading');

      // Valid access must NOT render this panel as role="alert"
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('hides decorative Material symbols from assistive technology', () => {
      const { container } = render(
        <FarmerAlertsGuidance viewerContext={validFarmerContext} />
      );
      const icons = container.querySelectorAll('.material-symbols-outlined');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('does not mutate input viewerContext prop when rendering (deeply frozen object test)', () => {
      const originalContext = {
        userId: 'usr_farmer_frozen_001',
        role: ROLES.FARMER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.FARM,
          registeredFarmDistrict: 'Jaffna',
          authorizedDistricts: Object.freeze(['Jaffna']),
          assignedFarmIds: Object.freeze(['FARM_JAF_01']),
        },
        permissions: Object.freeze({
          viewDataQuality: false,
          viewModelTransparency: false,
          manageAlerts: false,
          recordResponse: false,
          viewReports: false,
        }),
      };
      Object.freeze(originalContext.authorization);
      Object.freeze(originalContext);

      expect(() => {
        render(<FarmerAlertsGuidance viewerContext={originalContext} />);
      }).not.toThrow();

      expect(originalContext.role).toBe(ROLES.FARMER);
      expect(originalContext.authorization.registeredFarmDistrict).toBe('Jaffna');
    });

    it('contains no notification settings toggles, channel sliders, or email/SMS checkboxes', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
      expect(screen.queryByRole('slider')).not.toBeInTheDocument();
      expect(screen.queryByText(/SMS/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Email/i)).not.toBeInTheDocument();
    });

    it('retains registered area badge with primary brand highlight', () => {
      render(<FarmerAlertsGuidance viewerContext={validFarmerContext} />);
      const badgeText = screen.getByText(/Anuradhapura District/i);
      expect(badgeText).toBeInTheDocument();
      expect(badgeText.className).toContain('text-primary');
    });
  });
});
