import { describe, it, expect } from 'vitest';
import {
  ROLES,
  SCOPE_LEVELS,
  PERMISSIONS,
  SCREEN_CLASSIFICATION,
  validateViewerContext,
  getRegisteredFarmDistrict,
  getAuthorizedDistricts,
  getAssignedFarmIds,
  hasForecastingPermission,
  canAccessForecastingRole,
} from './viewerContext';

describe('ViewerContext Contract and Validation', () => {
  const validFarmerContext = {
    userId: 'usr_farmer_001',
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: ['Anuradhapura'],
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

  const validVetContext = {
    userId: 'usr_vet_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Jaffna', 'Kilinochchi'],
      assignedFarmIds: ['FARM_101', 'FARM_102'],
    },
    permissions: {
      viewDataQuality: true,
      viewModelTransparency: true,
      manageAlerts: true,
      recordResponse: true,
      viewReports: false,
    },
  };

  const validDaphContext = {
    userId: 'usr_daph_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura', 'Jaffna', 'Colombo'],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: true,
      viewModelTransparency: true,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    },
  };

  // 1. Classification & Constant Tests
  describe('SCREEN_CLASSIFICATION Constants', () => {
    it('uses DAPH_OFFICIAL key and has no DAPH or TECHNICAL keys', () => {
      expect(SCREEN_CLASSIFICATION).toHaveProperty('DAPH_OFFICIAL');
      expect(SCREEN_CLASSIFICATION).not.toHaveProperty('DAPH');
      expect(SCREEN_CLASSIFICATION).not.toHaveProperty('TECHNICAL');
      expect(SCREEN_CLASSIFICATION).toHaveProperty('CAPABILITY_GATED');
      expect(SCREEN_CLASSIFICATION.CAPABILITY_GATED).toHaveProperty('modelTransparency');
    });
  });

  // 2. Validation & Role/Scope Matrix Tests
  describe('validateViewerContext Role/Scope Compatibility', () => {
    it('fails closed on null or non-object context', () => {
      expect(validateViewerContext(null)).toEqual({ valid: false, reason: expect.any(String), normalizedContext: null });
      expect(validateViewerContext(undefined)).toEqual({ valid: false, reason: expect.any(String), normalizedContext: null });
    });

    it('Farmer + FARM succeeds', () => {
      const res = validateViewerContext(validFarmerContext);
      expect(res.valid).toBe(true);
      expect(res.normalizedContext.authorization.scopeLevel).toBe(SCOPE_LEVELS.FARM);
    });

    it('Farmer + DISTRICT/PROVINCE/NATIONAL fails closed', () => {
      [SCOPE_LEVELS.DISTRICT, SCOPE_LEVELS.PROVINCE, SCOPE_LEVELS.NATIONAL].forEach((scopeLevel) => {
        const input = {
          ...validFarmerContext,
          authorization: { ...validFarmerContext.authorization, scopeLevel },
        };
        const res = validateViewerContext(input);
        expect(res.valid).toBe(false);
        expect(res.reason).toContain('Incompatible scopeLevel');
      });
    });

    it('Vet + DISTRICT / PROVINCE succeeds', () => {
      [SCOPE_LEVELS.DISTRICT, SCOPE_LEVELS.PROVINCE].forEach((scopeLevel) => {
        const input = {
          ...validVetContext,
          authorization: { ...validVetContext.authorization, scopeLevel },
        };
        const res = validateViewerContext(input);
        expect(res.valid).toBe(true);
      });
    });

    it('Vet + FARM / NATIONAL fails closed', () => {
      [SCOPE_LEVELS.FARM, SCOPE_LEVELS.NATIONAL].forEach((scopeLevel) => {
        const input = {
          ...validVetContext,
          authorization: { ...validVetContext.authorization, scopeLevel },
        };
        const res = validateViewerContext(input);
        expect(res.valid).toBe(false);
        expect(res.reason).toContain('Incompatible scopeLevel');
      });
    });

    it('DAPH + DISTRICT / PROVINCE / NATIONAL succeeds', () => {
      [SCOPE_LEVELS.DISTRICT, SCOPE_LEVELS.PROVINCE, SCOPE_LEVELS.NATIONAL].forEach((scopeLevel) => {
        const input = {
          ...validDaphContext,
          authorization: { ...validDaphContext.authorization, scopeLevel },
        };
        const res = validateViewerContext(input);
        expect(res.valid).toBe(true);
      });
    });

    it('DAPH + FARM fails closed', () => {
      const input = {
        ...validDaphContext,
        authorization: { ...validDaphContext.authorization, scopeLevel: SCOPE_LEVELS.FARM },
      };
      const res = validateViewerContext(input);
      expect(res.valid).toBe(false);
      expect(res.reason).toContain('Incompatible scopeLevel');
    });

    it('normalizes missing permissions to false and ignores string "true"', () => {
      const input = {
        ...validFarmerContext,
        permissions: {
          viewDataQuality: 'true', // string "true" must remain false
          manageAlerts: true,
        },
      };

      const { valid, normalizedContext } = validateViewerContext(input);
      expect(valid).toBe(true);
      expect(normalizedContext.permissions.viewDataQuality).toBe(false);
      expect(normalizedContext.permissions.manageAlerts).toBe(true);
    });

    it('does not mutate the input object', () => {
      const inputCopy = JSON.parse(JSON.stringify(validFarmerContext));
      validateViewerContext(validFarmerContext);
      expect(validFarmerContext).toEqual(inputCopy);
    });
  });

  // 3. Role-Specific Data Isolation Tests
  describe('Role-Specific Authorization Data Normalization', () => {
    it('Farmer cannot gain extra districts through authorizedDistricts', () => {
      const input = {
        ...validFarmerContext,
        authorization: {
          ...validFarmerContext.authorization,
          registeredFarmDistrict: 'Anuradhapura',
          authorizedDistricts: ['Jaffna', 'Colombo', 'Kandy'], // attempt to inject extra districts
        },
      };

      const { valid, normalizedContext } = validateViewerContext(input);
      expect(valid).toBe(true);
      expect(normalizedContext.authorization.authorizedDistricts).toEqual(['Anuradhapura']);
      expect(getAuthorizedDistricts(input)).toEqual(['Anuradhapura']);
    });

    it('Farmer cannot gain assigned farm IDs', () => {
      const input = {
        ...validFarmerContext,
        authorization: {
          ...validFarmerContext.authorization,
          assignedFarmIds: ['FARM_999'],
        },
      };

      const { valid, normalizedContext } = validateViewerContext(input);
      expect(valid).toBe(true);
      expect(normalizedContext.authorization.assignedFarmIds).toEqual([]);
      expect(getAssignedFarmIds(input)).toEqual([]);
    });

    it('DAPH cannot gain assigned farm IDs', () => {
      const input = {
        ...validDaphContext,
        authorization: {
          ...validDaphContext.authorization,
          assignedFarmIds: ['FARM_101'],
        },
      };

      const { valid, normalizedContext } = validateViewerContext(input);
      expect(valid).toBe(true);
      expect(normalizedContext.authorization.assignedFarmIds).toEqual([]);
      expect(getAssignedFarmIds(input)).toEqual([]);
    });

    it('Vet registeredFarmDistrict normalizes to null and is not usable', () => {
      const input = {
        ...validVetContext,
        authorization: {
          ...validVetContext.authorization,
          registeredFarmDistrict: 'Anuradhapura', // attempt to set farm district on Vet
        },
      };

      const { valid, normalizedContext } = validateViewerContext(input);
      expect(valid).toBe(true);
      expect(normalizedContext.authorization.registeredFarmDistrict).toBeNull();
      expect(getRegisteredFarmDistrict(input)).toBeNull();
    });
  });

  // 4. Permissions & Role Check Tests
  describe('Permissions & Role Checks', () => {
    it('hasForecastingPermission requires explicit boolean true', () => {
      expect(hasForecastingPermission(validVetContext, PERMISSIONS.viewModelTransparency)).toBe(true);
      expect(hasForecastingPermission(validFarmerContext, PERMISSIONS.viewModelTransparency)).toBe(false);
      expect(hasForecastingPermission(null, PERMISSIONS.viewModelTransparency)).toBe(false);
      expect(hasForecastingPermission(validDaphContext, 'unknownPermission')).toBe(false);
    });

    it('canAccessForecastingRole verifies exact canonical roles', () => {
      expect(canAccessForecastingRole(validFarmerContext, ROLES.FARMER)).toBe(true);
      expect(canAccessForecastingRole(validVetContext, ROLES.VETERINARY_OFFICER)).toBe(true);
      expect(canAccessForecastingRole(validDaphContext, ROLES.DAPH_OFFICIAL)).toBe(true);
      expect(canAccessForecastingRole(validFarmerContext, 'VET')).toBe(false);
    });
  });
});
