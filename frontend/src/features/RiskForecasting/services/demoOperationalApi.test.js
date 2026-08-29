import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  fetchDemoFarms,
  fetchDemoSurveillanceRecords,
  fetchDemoAlerts,
  fetchDemoResponseTasks,
  DemoOperationalApiError,
  OPERATIONAL_ERROR_CATEGORIES,
} from './demoOperationalApi.js';
import * as demoOperationalApiModule from './demoOperationalApi.js';
import { writeDemoAccessToken, clearDemoAccessToken } from './demoSessionStorage.js';

const mockValidFarm = {
  schemaVersion: '1.0',
  farmId: 'DEMO_FARM_JAFFNA_001',
  displayName: 'Jaffna Cattle Farm 001',
  district: 'Jaffna',
  ownerUserId: 'DEMO_USER_FARMER_JAFFNA',
  assignedVetUserIds: ['DEMO_USER_VET_NORTH'],
  livestockTypes: ['CATTLE'],
  active: true,
  isSynthetic: true,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
  createdAt: '2026-08-19T00:00:00Z',
  updatedAt: '2026-08-19T00:00:00Z',
};

const mockValidFarmEnvelope = {
  items: [mockValidFarm],
  skip: 0,
  limit: 50,
  count: 1,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
};

const mockValidSurvRecord = {
  schemaVersion: '1.0',
  surveillanceRecordId: 'DEMO_SURV_JAFFNA_FMD_001',
  farmId: 'DEMO_FARM_JAFFNA_001',
  district: 'Jaffna',
  diseaseCode: 'FMD',
  observedAt: '2026-08-19T00:00:00Z',
  evidenceType: 'FARMER_REPORT',
  verificationStatus: 'REPORTED',
  sourceModule: 'SYNTHETIC_FARM_REPORTING',
  sourceRecordId: 'DEMO_SOURCE_001',
  summary: 'FMD symptoms observed',
  isSynthetic: true,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
  createdAt: '2026-08-19T00:00:00Z',
  updatedAt: '2026-08-19T00:00:00Z',
};

const mockValidAlert = {
  schemaVersion: '1.0',
  alertId: 'DEMO_ALERT_JAFFNA_FMD_001',
  district: 'Jaffna',
  diseaseCode: 'FMD',
  status: 'OPEN',
  priority: 'HIGH',
  issuedAt: '2026-08-19T00:00:00Z',
  sourceSurveillanceRecordIds: ['DEMO_SURV_JAFFNA_FMD_001'],
  affectedFarmIds: ['DEMO_FARM_JAFFNA_001'],
  title: 'FMD Alert Jaffna',
  message: 'High risk alert for FMD in Jaffna district',
  isSynthetic: true,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
  createdAt: '2026-08-19T00:00:00Z',
  updatedAt: '2026-08-19T00:00:00Z',
};

const mockValidTask = {
  schemaVersion: '1.0',
  responseTaskId: 'DEMO_TASK_JAFFNA_001',
  alertId: 'DEMO_ALERT_JAFFNA_FMD_001',
  assignedOfficerUserId: 'DEMO_USER_VET_NORTH',
  district: 'Jaffna',
  farmId: 'DEMO_FARM_JAFFNA_001',
  taskType: 'FIELD_REVIEW',
  status: 'ASSIGNED',
  dueAt: '2026-08-19T00:00:00Z',
  notes: 'Conduct field inspection',
  isSynthetic: true,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
  createdAt: '2026-08-19T00:00:00Z',
  updatedAt: '2026-08-19T00:00:00Z',
};

describe('Demo Operational API Unit Tests', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    sessionStorage.clear();
    writeDemoAccessToken('valid.session.token.123');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // Test 1, 2, 3, 4: Exact GET endpoint, skip/limit query params, Auth header, token not in URL
  it('Requirement 1, 2, 3, 4: Uses exact GET endpoint with skip and limit query params and Bearer header (no token in URL)', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockValidFarmEnvelope,
    });

    await fetchDemoFarms({ skip: 10, limit: 20 });

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, options] = fetch.mock.calls[0];

    expect(url).toContain('/api/v1/demo-operational/farms?skip=10&limit=20');
    expect(url).not.toContain('valid.session.token.123');
    expect(options.method).toBe('GET');
    expect(options.headers.Authorization).toBe('Bearer valid.session.token.123');
  });

  // Test 5: Missing token makes zero network calls
  it('Requirement 5: Missing token throws UNAUTHENTICATED error before sending network request', async () => {
    clearDemoAccessToken();

    try {
      await fetchDemoFarms();
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err).toBeInstanceOf(DemoOperationalApiError);
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.UNAUTHENTICATED);
      expect(fetch).not.toHaveBeenCalled();
    }
  });

  // Test 6: Invalid pagination parameters make zero network calls
  it('Requirement 6: Invalid pagination parameters throw VALIDATION error before network call', async () => {
    try {
      await fetchDemoFarms({ skip: -1, limit: 50 });
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
      expect(fetch).not.toHaveBeenCalled();
    }

    try {
      await fetchDemoFarms({ skip: 0, limit: 200 });
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
      expect(fetch).not.toHaveBeenCalled();
    }
  });

  // Test 7: AbortSignal is forwarded
  it('Requirement 7: Forwards AbortSignal to fetch options', async () => {
    const controller = new AbortController();
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockValidFarmEnvelope,
    });

    await fetchDemoFarms({ signal: controller.signal });

    const [, options] = fetch.mock.calls[0];
    expect(options.signal).toBe(controller.signal);
  });

  // Test 8: Valid envelopes and items accepted
  it('Requirement 8: Accepts valid envelope and item structures for all 4 operational endpoints', async () => {
    fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mockValidFarmEnvelope });
    const farmRes = await fetchDemoFarms();
    expect(farmRes.count).toBe(1);

    fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ items: [mockValidSurvRecord], skip: 0, limit: 50, count: 1, dataOrigin: 'SYNTHETIC_DEMO', scientificUseAllowed: false }) });
    const survRes = await fetchDemoSurveillanceRecords();
    expect(survRes.count).toBe(1);

    fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ items: [mockValidAlert], skip: 0, limit: 50, count: 1, dataOrigin: 'SYNTHETIC_DEMO', scientificUseAllowed: false }) });
    const alertRes = await fetchDemoAlerts();
    expect(alertRes.count).toBe(1);

    fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ items: [mockValidTask], skip: 0, limit: 50, count: 1, dataOrigin: 'SYNTHETIC_DEMO', scientificUseAllowed: false }) });
    const taskRes = await fetchDemoResponseTasks();
    expect(taskRes.count).toBe(1);
  });

  // Test 9: count mismatch rejected
  it('Requirement 9: Rejects response when count mismatch occurs', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ...mockValidFarmEnvelope, count: 99 }),
    });

    try {
      await fetchDemoFarms();
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
    }
  });

  // Test 10: Wrong dataOrigin rejected
  it('Requirement 10: Rejects response with invalid dataOrigin', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ...mockValidFarmEnvelope, dataOrigin: 'PRODUCTION' }),
    });

    try {
      await fetchDemoFarms();
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
    }
  });

  // Test 11: scientificUseAllowed=true rejected
  it('Requirement 11: Rejects response where scientificUseAllowed is true', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ...mockValidFarmEnvelope, scientificUseAllowed: true }),
    });

    try {
      await fetchDemoFarms();
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
    }
  });

  // Test 12 & 13: isSynthetic=false and invalid ID prefixes rejected
  it('Requirement 12 & 13: Rejects items with isSynthetic=false or invalid ID prefixes', async () => {
    const invalidFarm = { ...mockValidFarm, isSynthetic: false };
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ...mockValidFarmEnvelope, items: [invalidFarm] }),
    });

    try {
      await fetchDemoFarms();
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
    }

    const invalidPrefixFarm = { ...mockValidFarm, farmId: 'REAL_FARM_123' };
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ...mockValidFarmEnvelope, items: [invalidPrefixFarm] }),
    });

    try {
      await fetchDemoFarms();
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
    }
  });

  // Test 14: Invalid disease code rejected
  it('Requirement 14: Rejects surveillance records or alerts with invalid diseaseCode', async () => {
    const invalidDiseaseSurv = { ...mockValidSurvRecord, diseaseCode: 'COVID19' };
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ items: [invalidDiseaseSurv], skip: 0, limit: 50, count: 1, dataOrigin: 'SYNTHETIC_DEMO', scientificUseAllowed: false }),
    });

    try {
      await fetchDemoSurveillanceRecords();
      expect.unreachable('Should have thrown');
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.VALIDATION);
    }
  });

  // Test 17, 18, 19, 20: HTTP status error mappings
  it('Requirement 17, 18, 19, 20: Maps 401->UNAUTHENTICATED, 403->FORBIDDEN, 503->UNAVAILABLE, Abort->ABORTED', async () => {
    fetch.mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: 'Expired' }) });
    try {
      await fetchDemoFarms();
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.UNAUTHENTICATED);
    }

    fetch.mockResolvedValueOnce({ ok: false, status: 403, json: async () => ({ detail: 'Forbidden' }) });
    try {
      await fetchDemoFarms();
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.FORBIDDEN);
    }

    fetch.mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({ detail: 'Service Unavailable' }) });
    try {
      await fetchDemoFarms();
    } catch (err) {
      expect(err.category).toBe(OPERATIONAL_ERROR_CATEGORIES.UNAVAILABLE);
    }
  });

  // Test 34: No write/admin methods exist
  it('Requirement 34: Exposes strictly GET operational fetchers and no write or admin methods', () => {
    const exportedKeys = Object.keys(demoOperationalApiModule);
    expect(exportedKeys).toContain('fetchDemoFarms');
    expect(exportedKeys).toContain('fetchDemoSurveillanceRecords');
    expect(exportedKeys).toContain('fetchDemoAlerts');
    expect(exportedKeys).toContain('fetchDemoResponseTasks');

    expect(demoOperationalApiModule.createDemoFarm).toBeUndefined();
    expect(demoOperationalApiModule.updateDemoFarm).toBeUndefined();
    expect(demoOperationalApiModule.deleteDemoFarm).toBeUndefined();
    expect(demoOperationalApiModule.seedOperationalData).toBeUndefined();
  });
});
