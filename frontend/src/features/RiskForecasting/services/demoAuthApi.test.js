import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  isDemoModeEnabled,
  loginDemoUser,
  fetchDemoViewerContext,
  DemoAuthApiError,
} from './demoAuthApi.js';
import {
  readDemoAccessToken,
  writeDemoAccessToken,
  clearDemoAccessToken,
  DEMO_ACCESS_TOKEN_KEY,
} from './demoSessionStorage.js';
import * as demoAuthApiModule from './demoAuthApi.js';

describe('Demo Auth API & Session Storage Unit Tests', () => {
  const originalEnv = import.meta.env;

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // Test 1: Demo flag accepts only exact "true"
  describe('Requirement 1: Demo Feature Flag', () => {
    it('returns true only when VITE_FORECASTING_DEMO_ENABLED is exactly "true"', () => {
      vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
      expect(isDemoModeEnabled()).toBe(true);
    });

    it('returns false for missing, empty, "false", "TRUE", "1", or any other value', () => {
      const invalidValues = [undefined, '', 'false', 'TRUE', '1', 'yes', 'on', 'True', '0'];
      for (const val of invalidValues) {
        vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', val);
        expect(isDemoModeEnabled()).toBe(false);
      }
    });
  });

  // Test 5, 6, 17: Session Storage Safety
  describe('Requirement 5, 6, 17: Session Storage Rules', () => {
    it('stores token in sessionStorage under namespaced key', () => {
      const writeSuccess = writeDemoAccessToken('valid.demo.jwt.token');
      expect(writeSuccess).toBe(true);
      expect(sessionStorage.getItem(DEMO_ACCESS_TOKEN_KEY)).toBe('valid.demo.jwt.token');
      expect(readDemoAccessToken()).toBe('valid.demo.jwt.token');
    });

    it('never stores token or data in localStorage', () => {
      writeDemoAccessToken('valid.demo.jwt.token');
      expect(localStorage.getItem(DEMO_ACCESS_TOKEN_KEY)).toBeNull();
      expect(localStorage.length).toBe(0);
    });

    it('rejects and clears empty, non-string, or whitespace-only tokens', () => {
      sessionStorage.setItem(DEMO_ACCESS_TOKEN_KEY, '   ');
      expect(readDemoAccessToken()).toBeNull();
      expect(sessionStorage.getItem(DEMO_ACCESS_TOKEN_KEY)).toBeNull();

      expect(writeDemoAccessToken('')).toBe(false);
      expect(writeDemoAccessToken(null)).toBe(false);
      expect(writeDemoAccessToken(12345)).toBe(false);
      expect(readDemoAccessToken()).toBeNull();
    });
  });

  // Test 8: JWT is never decoded in frontend code
  describe('Requirement 8: JWT Safety', () => {
    it('fetches /me via HTTP request without decoding JWT in frontend', async () => {
      vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
      const mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';

      const validViewerContext = {
        userId: 'farmer_001',
        role: 'FARMER',
        authorization: {
          scopeLevel: 'FARM',
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

      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => validViewerContext,
      });

      const result = await fetchDemoViewerContext(mockToken);
      expect(result.userId).toBe('farmer_001');
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/demo-auth/me'),
        expect.objectContaining({
          headers: { Authorization: `Bearer ${mockToken}` },
        })
      );
    });
  });

  // Test 11 & 19: Error Sanitization and Secrets Protection
  describe('Requirement 11 & 19: Error Sanitization', () => {
    it('returns generic sanitized error on 401 login without exposing secrets or tokens', async () => {
      vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');

      fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Invalid authentication credentials.' }),
      });

      const secretPassword = 'MySecretPassword123!';
      try {
        await loginDemoUser({ loginName: 'demo_farmer', password: secretPassword });
        expect.unreachable('Should have thrown DemoAuthApiError');
      } catch (err) {
        expect(err).toBeInstanceOf(DemoAuthApiError);
        expect(err.message).toBe('Invalid login name or password.');
        expect(err.message).not.toContain(secretPassword);
        expect(err.message).not.toContain('detail');
      }
    });

    it('sanitizes 503 network errors and hides internal exceptions', async () => {
      vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');

      fetch.mockRejectedValueOnce(new Error('Internal Mongo Connection Error mongodb://admin:pass@cluster.mongodb.net'));

      try {
        await loginDemoUser({ loginName: 'demo_farmer', password: 'password' });
        expect.unreachable('Should have thrown');
      } catch (err) {
        expect(err).toBeInstanceOf(DemoAuthApiError);
        expect(err.message).toBe('Demo authentication is currently unavailable.');
        expect(err.message).not.toContain('mongodb://');
        expect(err.message).not.toContain('cluster');
      }
    });
  });

  // Test 18: No administrative or forbidden functions exist
  describe('Requirement 18: Method Isolation', () => {
    it('exposes only login, fetchViewerContext, and isDemoModeEnabled in the API module', () => {
      const exportedKeys = Object.keys(demoAuthApiModule);
      expect(exportedKeys).toContain('loginDemoUser');
      expect(exportedKeys).toContain('fetchDemoViewerContext');
      expect(exportedKeys).toContain('isDemoModeEnabled');
      expect(exportedKeys).toContain('DemoAuthApiError');

      expect(demoAuthApiModule.registerDemoUser).toBeUndefined();
      expect(demoAuthApiModule.resetPassword).toBeUndefined();
      expect(demoAuthApiModule.refreshToken).toBeUndefined();
      expect(demoAuthApiModule.seedDatabase).toBeUndefined();
      expect(demoAuthApiModule.adminDeleteUser).toBeUndefined();
    });
  });

  // Test 20: Input immutability
  describe('Requirement 20: Object Immutability', () => {
    it('does not mutate deeply frozen input or response ViewerContext objects', async () => {
      vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');

      const frozenInput = Object.freeze({
        userId: 'vet_001',
        role: 'VETERINARY_OFFICER',
        authorization: Object.freeze({
          scopeLevel: 'PROVINCE',
          registeredFarmDistrict: null,
          authorizedDistricts: Object.freeze(['Jaffna', 'Kilinochchi']),
          assignedFarmIds: Object.freeze(['FARM_001']),
        }),
        permissions: Object.freeze({
          viewDataQuality: true,
          viewModelTransparency: false,
          manageAlerts: true,
          recordResponse: true,
          viewReports: true,
        }),
      });

      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => frozenInput,
      });

      const result = await fetchDemoViewerContext('valid_token');
      expect(result.role).toBe('VETERINARY_OFFICER');
      expect(Object.isFrozen(frozenInput)).toBe(true);
    });
  });
});
