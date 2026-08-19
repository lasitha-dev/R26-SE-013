import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModelTransparency } from './ModelTransparency';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('ModelTransparency Component', () => {
  const validFarmerContext = {
    userId: 'usr_farmer_mt_001',
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: ['FARM_ANU_01'],
    },
    permissions: {
      viewModelTransparency: true,
    },
  };

  const validVetContext = {
    userId: 'usr_vet_mt_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Polonnaruwa', 'Anuradhapura'],
      assignedFarmIds: [],
    },
    permissions: {
      viewModelTransparency: true,
    },
  };

  const validDaphContext = {
    userId: 'usr_daph_mt_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura', 'Polonnaruwa', 'Kurunegala'],
      assignedFarmIds: [],
    },
    permissions: {
      viewModelTransparency: true,
      viewDataQuality: false,
    },
  };

  // 1. Access & Strict Capability Gating Tests
  describe('Access & Strict Capability Gating', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<ModelTransparency viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewerContext is invalid', () => {
      render(<ModelTransparency viewerContext={{ invalid: true }} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewModelTransparency permission is missing', () => {
      const missingPermissionContext = {
        ...validDaphContext,
        permissions: {},
      };
      render(<ModelTransparency viewerContext={missingPermissionContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when viewModelTransparency permission is false', () => {
      const falsePermissionContext = {
        ...validDaphContext,
        permissions: { viewModelTransparency: false },
      };
      render(<ModelTransparency viewerContext={falsePermissionContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when viewModelTransparency is string "true" (strict boolean check)', () => {
      const stringPermissionContext = {
        ...validDaphContext,
        permissions: { viewModelTransparency: 'true' },
      };
      render(<ModelTransparency viewerContext={stringPermissionContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when viewModelTransparency is numeric 1', () => {
      const numericPermissionContext = {
        ...validDaphContext,
        permissions: { viewModelTransparency: 1 },
      };
      render(<ModelTransparency viewerContext={numericPermissionContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('accepts valid FARMER with strict boolean true permission', () => {
      render(<ModelTransparency viewerContext={validFarmerContext} />);
      expect(screen.getByText('Model Transparency & Explainability')).toBeInTheDocument();
      expect(screen.getByText('How to understand your forecast')).toBeInTheDocument();
    });

    it('accepts valid VETERINARY_OFFICER with strict boolean true permission', () => {
      render(<ModelTransparency viewerContext={validVetContext} />);
      expect(screen.getByText('Model Transparency & Explainability')).toBeInTheDocument();
      expect(screen.getByText('Operational model interpretation')).toBeInTheDocument();
    });

    it('accepts valid DAPH_OFFICIAL with strict boolean true permission', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(screen.getByText('Model Transparency & Explainability')).toBeInTheDocument();
      expect(screen.getByText('Technical model transparency reference')).toBeInTheDocument();
    });

    it('fails closed when role-specific scope is invalid (e.g. FARMER without registeredFarmDistrict)', () => {
      const invalidFarmer = {
        ...validFarmerContext,
        authorization: {
          ...validFarmerContext.authorization,
          registeredFarmDistrict: null,
        },
      };
      render(<ModelTransparency viewerContext={invalidFarmer} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('displays only registeredFarmDistrict for FARMER view', () => {
      render(<ModelTransparency viewerContext={validFarmerContext} />);
      expect(screen.getByText('Anuradhapura District')).toBeInTheDocument();
      expect(screen.queryByText('Polonnaruwa District')).not.toBeInTheDocument();
    });

    it('displays explicit authorizedDistricts for VET and DAPH views', () => {
      render(<ModelTransparency viewerContext={validVetContext} />);
      expect(screen.getByText('Polonnaruwa District')).toBeInTheDocument();
      expect(screen.getByText('Anuradhapura District')).toBeInTheDocument();
      expect(screen.queryByText('Jaffna District')).not.toBeInTheDocument();
    });

    it('does NOT perform automatic national expansion', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(screen.getByText('Anuradhapura District')).toBeInTheDocument();
      expect(screen.queryByText('Colombo District')).not.toBeInTheDocument();
    });

    it('does NOT render any district, scope, or role selectors', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    });

    it('does not mutate input viewerContext prop (deeply frozen object test)', () => {
      const frozenContext = {
        userId: 'usr_frozen_mt',
        role: ROLES.DAPH_OFFICIAL,
        authorization: {
          scopeLevel: SCOPE_LEVELS.DISTRICT,
          registeredFarmDistrict: null,
          authorizedDistricts: Object.freeze(['Anuradhapura']),
          assignedFarmIds: Object.freeze([]),
        },
        permissions: Object.freeze({
          viewModelTransparency: true,
        }),
      };
      Object.freeze(frozenContext.authorization);
      Object.freeze(frozenContext);

      expect(() => {
        render(<ModelTransparency viewerContext={frozenContext} />);
      }).not.toThrow();

      expect(frozenContext.role).toBe(ROLES.DAPH_OFFICIAL);
    });

    it('makes zero network or API fetch calls', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });

  // 2. Status & Integration Notice Tests
  describe('Status & Integration Notice', () => {
    it('renders reference-only integration notice', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText('Live model outputs are awaiting secure integration')
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Backend responses define transparency and uncertainty fields, but live model output has not been requested for this session/i
        )
      ).toBeInTheDocument();
    });

    it('uses role="status" and aria-live="polite" for the notice', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute(
        'aria-labelledby',
        'model-transparency-integration-heading'
      );
    });

    it('valid access does not render authorization role="alert"', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('indicates reference-only status on cards without implying live model outputs', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      const refBadges = screen.getAllByText('Reference only — no live model output loaded');
      expect(refBadges.length).toBeGreaterThan(0);
    });
  });

  // 3. FARMER Role Presentation Tests
  describe('FARMER Presentation', () => {
    it('displays simplified forecast explanation section for FARMER', () => {
      render(<ModelTransparency viewerContext={validFarmerContext} />);
      expect(screen.getByText('How to understand your forecast')).toBeInTheDocument();
      expect(
        screen.getByText(/Forecasts estimate district-level disease outbreak likelihood/i)
      ).toBeInTheDocument();
    });

    it('excludes technical Stage 2, UQ, ECE, log-odds, model names, and raw fields from FARMER view', () => {
      render(<ModelTransparency viewerContext={validFarmerContext} />);
      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/prediction_set/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/RandomForestClassifier/i)).not.toBeInTheDocument();
    });

    it('does NOT display a fake confidence percentage in FARMER view', () => {
      render(<ModelTransparency viewerContext={validFarmerContext} />);
      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    });

    it('renders district-level non-diagnostic wording in FARMER view', () => {
      render(<ModelTransparency viewerContext={validFarmerContext} />);
      expect(
        screen.getByText(/do not diagnose individual animals or farms/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Clinical diagnosis always requires authorized veterinary field investigation/i)
      ).toBeInTheDocument();
    });
  });

  // 4. VETERINARY OFFICER Role Presentation Tests
  describe('VETERINARY OFFICER Presentation', () => {
    it('displays operational Stage 1 explanation for VETERINARY OFFICER', () => {
      render(<ModelTransparency viewerContext={validVetContext} />);
      expect(screen.getByText('Operational model interpretation')).toBeInTheDocument();
      expect(screen.getByText('Stage 1 Likelihood')).toBeInTheDocument();
    });

    it('explains unreliable or unavailable uncertainty disclosure', () => {
      render(<ModelTransparency viewerContext={validVetContext} />);
      expect(
        screen.getByText(/HEURISTIC, VALIDATED, or UNRELIABLE_INSUFFICIENT_DATA/i)
      ).toBeInTheDocument();
    });

    it('describes Stage 2 as Stage 2 Disease-Specific Output without severity code mappings or calling LSD a validated severity prediction', () => {
      render(<ModelTransparency viewerContext={validVetContext} />);
      expect(screen.getByText('Stage 2 Disease-Specific Output')).toBeInTheDocument();
      expect(screen.queryByText('Stage 2 Severity Assessment')).not.toBeInTheDocument();
      expect(
        screen.getByText(
          /Stage 2 is evaluated under disease-specific backend conditions/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /FMD Stage 2 evaluates active outbreak severity, whereas LSD Stage 2 serves strictly as a quiet-period false-alarm suppressor/i
        )
      ).toBeInTheDocument();
      expect(screen.queryByText(/severity_code/i)).not.toBeInTheDocument();
    });

    it('excludes full technical log-odds table and classifier details from VET view', () => {
      render(<ModelTransparency viewerContext={validVetContext} />);
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/RandomForestClassifier/i)).not.toBeInTheDocument();
    });

    it('contains no farm-level probability wording', () => {
      render(<ModelTransparency viewerContext={validVetContext} />);
      expect(
        screen.getByText(/Forecast probabilities reflect regional risk trends and are not farm-level outbreak predictions/i)
      ).toBeInTheDocument();
    });
  });

  // 5. DAPH OFFICIAL Technical Presentation Tests
  describe('DAPH OFFICIAL Presentation', () => {
    it('displays Technical Stage 1 reference for DAPH OFFICIAL', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(screen.getByText('Technical model transparency reference')).toBeInTheDocument();
      expect(
        screen.getByText(/1\. Stage 1 Binary Outbreak Likelihood \(Stage1Prediction\)/i)
      ).toBeInTheDocument();
    });

    it('accurately documents Stage 2 backend fields under Stage 2 Disease-Specific Output', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText(/2\. Stage 2 Disease-Specific Output \(Stage2Prediction\)/i)
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/2\. Stage 2 Severity Assessment \(Stage2Prediction\)/i)
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(/severity_predicted, model_name, notes, and action_required/i)
      ).toBeInTheDocument();
    });

    it('documents FMD vs LSD Stage 2 distinction and active-wave validation limitation', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText(
          /FMD Stage 2 provides backend-returned severity output when evaluated/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /LSD Stage 2 serves strictly as a quiet-period false-alarm suppressor and is not statistically validated to discriminate severity during active outbreak waves/i
        )
      ).toBeInTheDocument();
    });


    it('accurately documents Calibration and ECE meaning', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText(/3\. Probability Calibration \(CalibrationInfo\)/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Expected Calibration Error \(ECE\) is a statistical calibration metric measuring probability reliability, not outbreak probability itself/i
        )
      ).toBeInTheDocument();
    });

    it('keeps Uncertainty Quantification fields separate', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText(/4\. Uncertainty Quantification \(UncertaintyInfo\)/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /UQ metrics remain separate fields and must not be collapsed into an invented confidence score/i
        )
      ).toBeInTheDocument();
    });

    it('explains log-odds are not percentage feature importance', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText(/5\. Local Feature Explanation \(ExplanationInfo\)/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Log-odds contributions are additive mathematical decision factors, NOT percentage feature importance/i
        )
      ).toBeInTheDocument();
    });

    it('warns positive/negative contributions must not be reinterpreted as causal effects', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText(/must not be reinterpreted as causal field effects/i)
      ).toBeInTheDocument();
    });

    it('states LSD disclaimer rule for live responses', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.getByText(
          /authorized technical views must display response\.disclaimer verbatim/i
        )
      ).toBeInTheDocument();
    });

    it('does NOT fabricate live LSD response disclaimer text as if returned by backend', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.queryByText(/^LSD Stage 2 binary severity predictions serve strictly$/)
      ).not.toBeInTheDocument();
    });

    it('contains no sample model outputs or fake live values', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(screen.queryByText(/0\.684/)).not.toBeInTheDocument();
      expect(screen.queryByText(/68\.4%/)).not.toBeInTheDocument();
    });
  });

  // 6. Separation & Accessibility Tests
  describe('Separation & Accessibility', () => {
    it('contains no AI Diagnosis CTA', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
    });

    it('does not duplicate detailed Data Quality taxonomy', () => {
      render(<ModelTransparency viewerContext={validDaphContext} />);
      expect(
        screen.queryByText(/HISTORICAL_SAME_MONTH_PROXY/i)
      ).not.toBeInTheDocument();
    });

    it('hides decorative Material symbols from assistive technology', () => {
      const { container } = render(
        <ModelTransparency viewerContext={validDaphContext} />
      );
      const icons = container.querySelectorAll('.material-symbols-outlined');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });
  });

  // 7. Visual & Responsive Token Contracts
  describe('Visual & Responsive Layout Contracts', () => {
    it('uses max-w-6xl outer container with flex-wrap scope badges and break-words for DAPH technical text', () => {
      const { container } = render(
        <ModelTransparency viewerContext={validDaphContext} />
      );

      const outerContainer = container.firstElementChild;
      expect(outerContainer.className).toContain('max-w-6xl');
      expect(outerContainer.className).toContain('text-on-surface');

      const scopeHeading = screen.getByText('Authorized transparency scope');
      const badgeContainer = scopeHeading.closest('section').querySelector('.flex-wrap');
      expect(badgeContainer).toBeInTheDocument();

      const breakWordsElements = container.querySelectorAll('.break-words');
      expect(breakWordsElements.length).toBeGreaterThan(0);
    });

    it('contains no action/export buttons, progress bars or graphical charts/gauges', () => {
      const { container } = render(
        <ModelTransparency viewerContext={validDaphContext} />
      );

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(container.querySelector('svg')).not.toBeInTheDocument();
      expect(container.querySelector('canvas')).not.toBeInTheDocument();
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });
  });
});
