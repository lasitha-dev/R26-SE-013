import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchDistricts, predictFMD, predictLSD, fetchForecast } from './api';

global.fetch = vi.fn();

describe('RiskForecasting API service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetchDistricts returns district list', async () => {
    const mockData = { districts: ['Anuradhapura', 'Jaffna'], total_districts: 2 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    const result = await fetchDistricts();
    expect(result).toEqual(mockData);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/risk-forecasting/districts'));
  });

  it('predictFMD sends model_variant 30_feature_baseline when use31Features is false', async () => {
    const mockRes = { disease: 'FMD', district: 'Anuradhapura', stage1: { risk_level: 'HIGH' } };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes,
    });

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
    expect(sentBody).toHaveProperty('model_variant');
    expect(sentBody).not.toHaveProperty('use_31_features');
    expect(sentBody).not.toHaveProperty('use31Features');
  });

  it('predictFMD sends model_variant 31_feature_autocorrelation when use31Features is true', async () => {
    const mockRes = { disease: 'FMD', district: 'Anuradhapura', stage1: { risk_level: 'HIGH' } };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes,
    });

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
    expect(sentBody).toHaveProperty('model_variant');
    expect(sentBody).not.toHaveProperty('use_31_features');
    expect(sentBody).not.toHaveProperty('use31Features');
  });

  it('predictLSD sends payload and returns prediction', async () => {
    const mockRes = { disease: 'LSD', district: 'Jaffna', stage1: { risk_level: 'LOW' } };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes,
    });

    const payload = { district: 'Jaffna', year: 2020, month: 11 };
    const result = await predictLSD(payload);
    expect(result).toEqual(mockRes);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/predict/lsd'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('fetchForecast sends payload and returns forecast', async () => {
    const mockRes = { disease: 'FMD', month: 1, forecasts: [] };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes,
    });

    const result = await fetchForecast('FMD', { month: 1, year: 2024 });
    expect(result).toEqual(mockRes);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/forecast/fmd'),
      expect.objectContaining({ method: 'POST' })
    );
  });
});
