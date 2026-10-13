import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  fetchDistricts,
  predictFMD,
  predictLSD,
  fetchForecast,
  fetchRiskForecastingHealth,
  predictDistrictDiseaseRisks,
  fetchCombinedDistrictForecasts,
  RiskForecastingApiError,
} from './api';

global.fetch = vi.fn();

/**
 * Realistic Response factory producing authentic fetch Response objects.
 */
function createMockResponse({ status = 200, body = '', contentType = 'application/json' }) {
  const responseBody = typeof body === 'string' ? body : JSON.stringify(body);
  const headers = new Headers();
  if (contentType) {
    headers.set('content-type', contentType);
  }
  return new Response(responseBody, { status, headers });
}

describe('RiskForecasting API service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // A. Existing public functions & backward compatibility
  it('fetchDistricts returns district list and month_names', async () => {
    const mockData = { districts: ['Anuradhapura', 'Jaffna'], month_names: ['January'], total_districts: 2 };
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 200, body: mockData }));

    const result = await fetchDistricts();
    expect(result).toEqual(mockData);
    expect(result).toHaveProperty('month_names');
    expect(result).toHaveProperty('districts');
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/risk-forecasting/districts'), expect.anything());
  });

  it('predictFMD sends model_variant 30_feature_baseline when use31Features is false', async () => {
    const mockRes = { disease: 'FMD', district: 'Anuradhapura', stage1: { risk_level: 'HIGH' } };
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 200, body: mockRes }));

    const result = await predictFMD({ district: 'Anuradhapura', year: 2024, month: 1, use31Features: false });
    expect(result).toEqual(mockRes);

    const callArgs = global.fetch.mock.calls[0];
    expect(callArgs[0]).toContain('/predict/fmd');
    const sentBody = JSON.parse(callArgs[1].body);

    expect(sentBody).toEqual({
      district: 'Anuradhapura',
      year: 2024,
      month: 1,
      model_variant: '30_feature_baseline',
    });
  });

  it('predictFMD sends model_variant 31_feature_autocorrelation when use31Features is true', async () => {
    const mockRes = { disease: 'FMD', district: 'Anuradhapura', stage1: { risk_level: 'HIGH' } };
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 200, body: mockRes }));

    const result = await predictFMD({ district: 'Anuradhapura', year: 2024, month: 1, use31Features: true });
    expect(result).toEqual(mockRes);

    const callArgs = global.fetch.mock.calls[0];
    expect(callArgs[0]).toContain('/predict/fmd');
    const sentBody = JSON.parse(callArgs[1].body);

    expect(sentBody).toEqual({
      district: 'Anuradhapura',
      year: 2024,
      month: 1,
      model_variant: '31_feature_autocorrelation',
    });
  });

  it('predictLSD converts string year/month and strips arbitrary extra caller properties', async () => {
    const mockRes = { disease: 'LSD', district: 'Jaffna', stage1: { risk_level: 'LOW' } };
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 200, body: mockRes }));

    const payload = { district: 'Jaffna', year: '2020', month: '11', extraProp: 'unauthorized_field', role: 'Farmer' };
    const result = await predictLSD(payload);
    expect(result).toEqual(mockRes);

    const callArgs = global.fetch.mock.calls[0];
    expect(callArgs[0]).toContain('/predict/lsd');
    const sentBody = JSON.parse(callArgs[1].body);

    expect(sentBody).toEqual({
      district: 'Jaffna',
      year: 2020,
      month: 11,
    });
    expect(sentBody).not.toHaveProperty('extraProp');
    expect(sentBody).not.toHaveProperty('role');
  });

  it('fetchForecast sends target_month and year', async () => {
    const mockRes = { disease: 'FMD', target_month: 1, target_year: 2024, districts: [] };
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 200, body: mockRes }));

    const result = await fetchForecast('FMD', { month: 1, year: 2024 });
    expect(result).toEqual(mockRes);

    const callArgs = global.fetch.mock.calls[0];
    expect(callArgs[0]).toContain('/forecast/fmd');
    const sentBody = JSON.parse(callArgs[1].body);
    expect(sentBody).toEqual({
      target_month: 1,
      year: 2024,
    });
  });

  // B. Health Check
  it('fetchRiskForecastingHealth returns health status on success', async () => {
    const mockHealth = { status: 'ok', component: 'risk_forecasting', models_loaded: true, loaded_artifacts: [] };
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 200, body: mockHealth }));

    const res = await fetchRiskForecastingHealth();
    expect(res).toEqual(mockHealth);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/risk-forecasting/health'), expect.anything());
  });

  // C. Error Parsing (Single-pass body consumption)
  it('parses valid JSON string detail', async () => {
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 400, body: { detail: 'Invalid district name specified' } }));

    try {
      await fetchDistricts();
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(400);
      expect(err.message).toBe('API Error 400: Invalid district name specified');
      expect(err.detail).toBe('Invalid district name specified');
    }
  });

  it('parses Pydantic validation-error array', async () => {
    const errorArray = [{ msg: 'field required', loc: ['body', 'district'] }];
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 422, body: { detail: errorArray } }));

    try {
      await predictFMD({ district: '', year: 2024, month: 1 });
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(422);
      expect(err.disease).toBe('FMD');
      expect(err.message).toBe('API Error 422: field required');
      expect(err.detail).toEqual(errorArray);
    }
  });

  it('parses object detail', async () => {
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 500, body: { detail: { message: 'Database connection failed' } } }));

    try {
      await fetchDistricts();
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(500);
      expect(err.message).toBe('API Error 500: Database connection failed');
    }
  });

  it('parses JSON response without detail property', async () => {
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 400, body: { error: 'Bad Request Payload' } }));

    try {
      await fetchDistricts();
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(400);
      expect(err.message).toBe('API Error 400: {"error":"Bad Request Payload"}');
    }
  });

  it('handles malformed JSON carrying application/json content type without crashing', async () => {
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 500, body: '{ malformed json: ', contentType: 'application/json' }));

    try {
      await fetchDistricts();
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(500);
      expect(err.message).toBe('API Error 500: { malformed json:');
      expect(err.detail).toBeNull();
    }
  });

  it('handles HTML carrying application/json incorrectly', async () => {
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 502, body: '<html>502 Bad Gateway</html>', contentType: 'application/json' }));

    try {
      await fetchDistricts();
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(502);
      expect(err.message).toBe('API Error 502: <html>502 Bad Gateway</html>');
    }
  });

  it('parses text/plain response', async () => {
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 503, body: 'Service Maintenance', contentType: 'text/plain' }));

    try {
      await predictLSD({ district: 'Jaffna', year: 2024, month: 1 });
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(503);
      expect(err.disease).toBe('LSD');
      expect(err.message).toBe('API Error 503: Service Maintenance');
    }
  });

  it('handles empty response body gracefully', async () => {
    global.fetch.mockResolvedValueOnce(createMockResponse({ status: 500, body: '', contentType: 'text/plain' }));

    try {
      await fetchDistricts();
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBe(500);
      expect(err.message).toBe('API Error 500');
    }
  });

  // D. Network Rejection Normalization
  it('normalizes health network failure with status = null', async () => {
    global.fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    try {
      await fetchRiskForecastingHealth();
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBeNull();
      expect(err.endpoint).toContain('/health');
      expect(err.disease).toBeNull();
      expect(err.message).toContain('Network request failed');
    }
  });

  it('normalizes FMD network failure and preserves disease = FMD', async () => {
    global.fetch.mockRejectedValueOnce(new TypeError('Network Error'));

    try {
      await predictFMD({ district: 'Anuradhapura', year: 2024, month: 1 });
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBeNull();
      expect(err.endpoint).toContain('/predict/fmd');
      expect(err.disease).toBe('FMD');
      expect(err.message).toContain('Network request failed');
    }
  });

  it('normalizes LSD network failure and preserves disease = LSD', async () => {
    global.fetch.mockRejectedValueOnce(new TypeError('Network Error'));

    try {
      await predictLSD({ district: 'Jaffna', year: 2024, month: 1 });
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBeNull();
      expect(err.endpoint).toContain('/predict/lsd');
      expect(err.disease).toBe('LSD');
    }
  });

  it('normalizes forecast network failure preserving endpoint and disease', async () => {
    global.fetch.mockRejectedValueOnce(new TypeError('Connection refused'));

    try {
      await fetchForecast('LSD', { month: 1, year: 2024 });
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingApiError);
      expect(err.status).toBeNull();
      expect(err.endpoint).toContain('/forecast/lsd');
      expect(err.disease).toBe('LSD');
    }
  });

  it('combined helper returns partial when one request has a network failure', async () => {
    const mockFMD = { disease: 'FMD', district: 'Anuradhapura', stage1: { risk_level: 'HIGH' } };

    global.fetch
      .mockResolvedValueOnce(createMockResponse({ status: 200, body: mockFMD }))
      .mockRejectedValueOnce(new TypeError('Network unreachable for LSD'));

    const result = await predictDistrictDiseaseRisks({ district: 'Anuradhapura', year: 2024, month: 1 });

    expect(result.overallStatus).toBe('partial');
    expect(result.fmd.status).toBe('success');
    expect(result.fmd.data).toEqual(mockFMD);
    expect(result.lsd.status).toBe('error');
    expect(result.lsd.error).toBeInstanceOf(RiskForecastingApiError);
    expect(result.lsd.error.status).toBeNull();
    expect(result.lsd.error.disease).toBe('LSD');
  });

  it('combined helper returns error when both have network failures', async () => {
    global.fetch
      .mockRejectedValueOnce(new TypeError('FMD Network Error'))
      .mockRejectedValueOnce(new TypeError('LSD Network Error'));

    const result = await predictDistrictDiseaseRisks({ district: 'Anuradhapura', year: 2024, month: 1 });

    expect(result.overallStatus).toBe('error');
    expect(result.fmd.status).toBe('error');
    expect(result.fmd.error.status).toBeNull();
    expect(result.lsd.status).toBe('error');
    expect(result.lsd.error.status).toBeNull();
  });

  // E. Parameter Validation
  it('throws TypeError on empty or whitespace district', async () => {
    await expect(predictDistrictDiseaseRisks({ district: '   ', year: 2024, month: 1 })).rejects.toThrow(TypeError);
    await expect(predictDistrictDiseaseRisks({ district: '', year: 2024, month: 1 })).rejects.toThrow(TypeError);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('throws RangeError on NaN, non-integer, or out-of-range year', async () => {
    await expect(predictDistrictDiseaseRisks({ district: 'Jaffna', year: NaN, month: 1 })).rejects.toThrow(RangeError);
    await expect(predictDistrictDiseaseRisks({ district: 'Jaffna', year: 2024.5, month: 1 })).rejects.toThrow(RangeError);
    await expect(predictDistrictDiseaseRisks({ district: 'Jaffna', year: 2016, month: 1 })).rejects.toThrow(RangeError);
    await expect(predictDistrictDiseaseRisks({ district: 'Jaffna', year: 2031, month: 1 })).rejects.toThrow(RangeError);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('throws RangeError on invalid month (below 1, above 12, non-numeric)', async () => {
    await expect(predictDistrictDiseaseRisks({ district: 'Jaffna', year: 2024, month: 0 })).rejects.toThrow(RangeError);
    await expect(predictDistrictDiseaseRisks({ district: 'Jaffna', year: 2024, month: 13 })).rejects.toThrow(RangeError);
    await expect(predictDistrictDiseaseRisks({ district: 'Jaffna', year: 2024, month: 'invalid' })).rejects.toThrow(RangeError);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('fetchCombinedDistrictForecasts validates year and month parameters', async () => {
    await expect(fetchCombinedDistrictForecasts({ year: 2010, targetMonth: 5 })).rejects.toThrow(RangeError);
    await expect(fetchCombinedDistrictForecasts({ year: 2024, targetMonth: 15 })).rejects.toThrow(RangeError);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  // F. Combined Success States
  it('fetchCombinedDistrictForecasts returns overallStatus success when both succeed', async () => {
    const mockFMDForecast = { disease: 'FMD', target_year: 2024, target_month: 1 };
    const mockLSDForecast = { disease: 'LSD', target_year: 2024, target_month: 1 };

    global.fetch
      .mockResolvedValueOnce(createMockResponse({ status: 200, body: mockFMDForecast }))
      .mockResolvedValueOnce(createMockResponse({ status: 200, body: mockLSDForecast }));

    const result = await fetchCombinedDistrictForecasts({ year: 2024, targetMonth: 1 });

    expect(result.overallStatus).toBe('success');
    expect(result.fmd.status).toBe('success');
    expect(result.fmd.data).toEqual(mockFMDForecast);
    expect(result.lsd.status).toBe('success');
    expect(result.lsd.data).toEqual(mockLSDForecast);
  });
});
