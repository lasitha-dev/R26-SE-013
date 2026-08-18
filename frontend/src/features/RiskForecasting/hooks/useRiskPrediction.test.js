import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import useRiskPrediction from './useRiskPrediction';
import * as api from '../services/api';

vi.mock('../services/api');

describe('useRiskPrediction Custom Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchDistricts.mockResolvedValue({
      districts: ['Anuradhapura', 'Jaffna', 'Batticaloa'],
      total_districts: 3,
    });
  });

  it('loads district metadata on mount and initializes default state', async () => {
    const { result } = renderHook(() => useRiskPrediction());

    expect(result.current.viewMode).toBe('form');
    expect(result.current.status).toBe('idle');
    expect(result.current.error).toBeNull();
    expect(result.current.selectedDisease).toBe('FMD');
    expect(result.current.selectedDistrict).toBe('Anuradhapura');

    await waitFor(() => {
      expect(result.current.districts).toEqual(['Anuradhapura', 'Jaffna', 'Batticaloa']);
    });
  });

  it('handles successful FMD prediction and updates viewMode to results', async () => {
    const mockPrediction = { disease: 'FMD', district: 'Anuradhapura', stage1: { risk_level: 'HIGH' } };
    api.predictFMD.mockResolvedValueOnce(mockPrediction);

    const { result } = renderHook(() => useRiskPrediction());

    await act(async () => {
      await result.current.submitPrediction();
    });

    expect(api.predictFMD).toHaveBeenCalledWith({
      district: 'Anuradhapura',
      year: 2024,
      month: 1,
      use31Features: false,
    });
    expect(result.current.status).toBe('success');
    expect(result.current.viewMode).toBe('results');
    expect(result.current.predictionResult).toEqual(mockPrediction);
  });

  it('passes use31Features true to predictFMD when toggle is set to true', async () => {
    const mockPrediction = { disease: 'FMD', district: 'Anuradhapura', stage1: { risk_level: 'HIGH' } };
    api.predictFMD.mockResolvedValueOnce(mockPrediction);

    const { result } = renderHook(() => useRiskPrediction());

    act(() => {
      result.current.setUse31Features(true);
    });

    await act(async () => {
      await result.current.submitPrediction();
    });

    expect(api.predictFMD).toHaveBeenCalledWith({
      district: 'Anuradhapura',
      year: 2024,
      month: 1,
      use31Features: true,
    });
  });

  it('handles prediction API failure and sets status to error', async () => {
    api.predictFMD.mockRejectedValueOnce(new Error('Network Connection Error'));

    const { result } = renderHook(() => useRiskPrediction());

    await act(async () => {
      await result.current.submitPrediction();
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBe('Network Connection Error');
    expect(result.current.viewMode).toBe('form');
  });

  it('handles successful forecast fetch and updates viewMode to dashboard', async () => {
    const mockForecast = { disease: 'FMD', target_month: 1, districts: [] };
    api.fetchForecast.mockResolvedValueOnce(mockForecast);

    const { result } = renderHook(() => useRiskPrediction());

    await act(async () => {
      await result.current.submitForecast('FMD', 1, 2024);
    });

    expect(api.fetchForecast).toHaveBeenCalledWith('FMD', { month: 1, year: 2024 });
    expect(result.current.status).toBe('success');
    expect(result.current.viewMode).toBe('dashboard');
    expect(result.current.forecastResult).toEqual(mockForecast);
  });

  it('resets viewMode to form when resetToForm is called', async () => {
    const mockPrediction = { disease: 'FMD', district: 'Anuradhapura' };
    api.predictFMD.mockResolvedValueOnce(mockPrediction);

    const { result } = renderHook(() => useRiskPrediction());

    await act(async () => {
      await result.current.submitPrediction();
    });

    expect(result.current.viewMode).toBe('results');

    act(() => {
      result.current.resetToForm();
    });

    expect(result.current.viewMode).toBe('form');
    expect(result.current.status).toBe('idle');
    expect(result.current.error).toBeNull();
  });
});
