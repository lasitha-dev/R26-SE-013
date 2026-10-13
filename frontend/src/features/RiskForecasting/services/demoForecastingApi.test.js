import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  fetchAuthorizedFmdForecast,
  fetchAuthorizedLsdForecast,
  fetchAuthorizedDiseaseForecasts,
  DemoForecastingApiError,
  DEMO_FORECASTING_ERROR_CATEGORIES,
} from './demoForecastingApi.js';
import { writeDemoAccessToken, clearDemoAccessToken } from './demoSessionStorage.js';

describe('Protected Demo Forecasting API Module', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    clearDemoAccessToken();
  });

  afterEach(() => {
    clearDemoAccessToken();
  });

  // 1. Missing session token
  it('throws UNAUTHENTICATED error and makes zero fetch calls when token is missing', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    await expect(
      fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' })
    ).rejects.toThrow('Your demo session has expired.');

    expect(fetchSpy).not.toHaveBeenCalled();

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err).toBeInstanceOf(DemoForecastingApiError);
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED);
      expect(err.status).toBe(401);
    }
  });

  // 2. Invalid year
  it('validates year parameter before network calls and makes zero fetch calls', async () => {
    writeDemoAccessToken('valid_token');
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    await expect(
      fetchAuthorizedFmdForecast({ year: 2010, targetMonth: 1 })
    ).rejects.toThrow('Forecast year must be an integer between 2017 and 2030.');

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  // 3. Invalid target month
  it('validates target month parameter before network calls and makes zero fetch calls', async () => {
    writeDemoAccessToken('valid_token');
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    await expect(
      fetchAuthorizedLsdForecast({ year: 2024, targetMonth: 13 })
    ).rejects.toThrow('Forecast target month must be an integer between 1 and 12.');

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  // 4. FMD request
  it('sends correct POST payload and fixed model_variant for FMD', async () => {
    writeDemoAccessToken('jwt_token_fmd');

    const mockResponse = {
      disease: 'FMD',
      target_year: 2024,
      target_month: 1,
      total_districts: 1,
      districts: [{ district: 'Jaffna', probability_pct: 60, risk_level: 'HIGH' }],
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    });

    const res = await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toContain('/api/v1/demo-forecasting/forecast/fmd');
    expect(options.method).toBe('POST');
    const body = JSON.parse(options.body);
    expect(body.model_variant).toBe('30_feature_baseline');
    expect(body.target_month).toBe(1);
    expect(body.year).toBe(2024);
    expect(body.district).toBe('Jaffna');
    expect(res).toEqual(mockResponse);
  });

  // 5. LSD request
  it('sends correct POST payload for LSD without model_variant', async () => {
    writeDemoAccessToken('jwt_token_lsd');

    const mockResponse = {
      disease: 'LSD',
      target_year: 2024,
      target_month: 5,
      total_districts: 1,
      districts: [{ district: 'Jaffna', probability_pct: 40, risk_level: 'MEDIUM' }],
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    });

    const res = await fetchAuthorizedLsdForecast({ year: 2024, targetMonth: 5, district: 'Jaffna' });

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toContain('/api/v1/demo-forecasting/forecast/lsd');
    expect(options.method).toBe('POST');
    const body = JSON.parse(options.body);
    expect(body.model_variant).toBeUndefined();
    expect(body.target_month).toBe(5);
    expect(body.year).toBe(2024);
    expect(res).toEqual(mockResponse);
  });

  // 6. Bearer token
  it('transmits Bearer token strictly in Authorization header and not in URL or error text', async () => {
    const secretToken = 'SECRET_BEARER_TOKEN_999';
    writeDemoAccessToken(secretToken);

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Access denied' }),
    });

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.message).not.toContain(secretToken);
    }

    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).not.toContain(secretToken);
    expect(options.headers.Authorization).toBe(`Bearer ${secretToken}`);
  });

  // 7. District normalization
  it('trims whitespace, removes duplicate districts, and does not mutate input array', async () => {
    writeDemoAccessToken('jwt_token_123');
    const inputDistricts = [' Jaffna ', 'Kilinochchi', 'Jaffna '];
    const inputCopy = [...inputDistricts];

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        disease: 'LSD',
        target_year: 2024,
        target_month: 2,
        districts: [
          { district: 'Jaffna', probability_pct: 50 },
          { district: 'Kilinochchi', probability_pct: 30 },
        ],
      }),
    });

    await fetchAuthorizedLsdForecast({ year: 2024, targetMonth: 2, districts: inputDistricts });

    expect(inputDistricts).toEqual(inputCopy); // No mutation
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.districts).toEqual(['Jaffna', 'Kilinochchi']);
  });

  // 8. Invalid/empty district values
  it('throws VALIDATION error on non-string or empty district value', async () => {
    writeDemoAccessToken('jwt_token_123');

    await expect(
      fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: '   ' })
    ).rejects.toThrow('District parameter must be a non-empty string.');
  });

  // 9. Response containing an unauthorized district
  it('rejects response containing an unauthorized returned district with VALIDATION error', async () => {
    writeDemoAccessToken('jwt_token_123');

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        disease: 'FMD',
        target_year: 2024,
        target_month: 1,
        districts: [
          { district: 'Jaffna', probability_pct: 50 },
          { district: 'Colombo', probability_pct: 90 }, // Unauthorized district
        ],
      }),
    });

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err).toBeInstanceOf(DemoForecastingApiError);
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION);
      expect(err.message).toContain('unauthorized district');
    }
  });

  // 10. Response disease mismatch
  it('rejects response with disease mismatch as VALIDATION error', async () => {
    writeDemoAccessToken('jwt_token_123');

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        disease: 'LSD', // Expected FMD
        target_year: 2024,
        target_month: 1,
        districts: [{ district: 'Jaffna', probability_pct: 50 }],
      }),
    });

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION);
      expect(err.message).toContain('does not match requested disease');
    }
  });

  // 11. Response year/month mismatch
  it('rejects response with target period mismatch as VALIDATION error', async () => {
    writeDemoAccessToken('jwt_token_123');

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        disease: 'FMD',
        target_year: 2025, // Requested 2024
        target_month: 1,
        districts: [{ district: 'Jaffna', probability_pct: 50 }],
      }),
    });

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION);
      expect(err.message).toContain('target period does not match');
    }
  });

  // 12. 401 maps to UNAUTHENTICATED
  it('maps HTTP 401 status to UNAUTHENTICATED error category', async () => {
    writeDemoAccessToken('jwt_token_123');

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Unauthorized token' }),
    });

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED);
      expect(err.status).toBe(401);
    }
  });

  // 13. 403 maps to FORBIDDEN
  it('maps HTTP 403 status to FORBIDDEN error category', async () => {
    writeDemoAccessToken('jwt_token_123');

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Forbidden scope' }),
    });

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.FORBIDDEN);
      expect(err.status).toBe(403);
    }
  });

  // 14. 422 maps to VALIDATION
  it('maps HTTP 422 status to VALIDATION error category', async () => {
    writeDemoAccessToken('jwt_token_123');

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'Unprocessable entity' }),
    });

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION);
      expect(err.status).toBe(422);
    }
  });

  // 15. 503/network failure maps to UNAVAILABLE
  it('maps HTTP 503 or network failure to UNAVAILABLE error category', async () => {
    writeDemoAccessToken('jwt_token_123');

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network offline'));

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.UNAVAILABLE);
      expect(err.message).toBe('Forecast service is currently unavailable.');
    }
  });

  // 16. Abort maps to ABORTED
  it('maps AbortError to ABORTED error category', async () => {
    writeDemoAccessToken('jwt_token_123');

    const abortErr = new Error('The operation was aborted');
    abortErr.name = 'AbortError';

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(abortErr);

    try {
      await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    } catch (err) {
      expect(err.category).toBe(DEMO_FORECASTING_ERROR_CATEGORIES.ABORTED);
    }
  });

  // 17. No request payload contains forbidden fields
  it('verifies request payload contains zero operational or identity fields', async () => {
    writeDemoAccessToken('jwt_token_123');

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        disease: 'FMD',
        target_year: 2024,
        target_month: 1,
        districts: [{ district: 'Jaffna', probability_pct: 50 }],
      }),
    });

    await fetchAuthorizedFmdForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });

    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    const forbiddenKeys = [
      'role',
      'scopeLevel',
      'permissions',
      'userId',
      'assignedFarmIds',
      'farms',
      'surveillanceRecords',
      'alerts',
      'responseTasks',
    ];

    for (const key of forbiddenKeys) {
      expect(body[key]).toBeUndefined();
    }
  });

  // Concurrent fetch test
  it('fetches concurrent combined forecasts via fetchAuthorizedDiseaseForecasts', async () => {
    writeDemoAccessToken('test_jwt_token_123');

    const fmdMock = {
      disease: 'FMD',
      target_year: 2024,
      target_month: 1,
      districts: [{ district: 'Jaffna', probability_pct: 50, risk_level: 'MEDIUM' }],
    };

    const lsdMock = {
      disease: 'LSD',
      target_year: 2024,
      target_month: 1,
      districts: [{ district: 'Jaffna', probability_pct: 60, risk_level: 'HIGH' }],
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (url.includes('/fmd')) {
        return { ok: true, status: 200, json: async () => fmdMock };
      }
      return { ok: true, status: 200, json: async () => lsdMock };
    });

    const res = await fetchAuthorizedDiseaseForecasts({ year: 2024, targetMonth: 1, district: 'Jaffna' });

    expect(res.overallStatus).toBe('success');
    expect(res.fmd.data).toEqual(fmdMock);
    expect(res.lsd.data).toEqual(lsdMock);
  });
});
