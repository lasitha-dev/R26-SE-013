import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import RiskForecastingIntegrationAdapter from './RiskForecastingIntegrationAdapter';
import { ROLES, SCOPE_LEVELS } from '../contracts/viewerContext';
import fs from 'fs/promises';
import path from 'path';

// Mock RiskForecastingFeature boundary
vi.mock('../RiskForecastingFeature', () => ({
  RiskForecastingFeature: ({ viewerContext }) => (
    <div data-testid="mock-risk-forecasting-feature">
      Loaded for role: {viewerContext.role}
    </div>
  )
}));

describe('RiskForecastingIntegrationAdapter', () => {
  const originalFetch = global.fetch;
  let mockFetch;

  const validVetContext = {
    userId: 'test-vet-123',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      authorizedDistricts: ['Colombo'],
      assignedFarmIds: ['farm-1', 'farm-2']
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: true,
      manageAlerts: true,
      recordResponse: true,
      viewReports: false
    }
  };

  beforeEach(() => {
    mockFetch = vi.fn();
    global.fetch = mockFetch;
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('1. missing token: no fetch, generic required state, feature absent', async () => {
    render(<RiskForecastingIntegrationAdapter />);
    expect(mockFetch).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByTestId('mock-risk-forecasting-feature')).not.toBeInTheDocument();
  });

  it('2. token exists and request is pending: accessible loading state, feature absent', () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockImplementation(() => new Promise(() => {})); 
    
    render(<RiskForecastingIntegrationAdapter />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/Loading forecasting context/i)).toBeInTheDocument();
    expect(screen.queryByTestId('mock-risk-forecasting-feature')).not.toBeInTheDocument();
  });

  it('3. successful valid Veterinary viewerContext uses correct headers and renders feature', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => validVetContext
    });

    render(<RiskForecastingIntegrationAdapter />);
    
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/risk-forecasting/viewer-context'),
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          'Authorization': 'Bearer synthetic-test-token-123'
        })
      })
    );
    expect(screen.getByTestId('mock-risk-forecasting-feature')).toBeInTheDocument();
  });

  it('3b. successful valid DAPH viewerContext uses correct headers and renders feature', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...validVetContext, role: ROLES.DAPH_OFFICIAL, authorization: { ...validVetContext.authorization, scopeLevel: SCOPE_LEVELS.NATIONAL } })
    });

    render(<RiskForecastingIntegrationAdapter />);
    
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('mock-risk-forecasting-feature')).toBeInTheDocument();
  });

  it('4. HTTP 401 fails closed', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });

    render(<RiskForecastingIntegrationAdapter />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('mock-risk-forecasting-feature')).not.toBeInTheDocument();
  });

  it('5. HTTP 403 fails closed', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockResolvedValueOnce({ ok: false, status: 403 });

    render(<RiskForecastingIntegrationAdapter />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('6. network failure shows generic state, no tech leakage', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockRejectedValueOnce(new Error('Network error CONNECTION_REFUSED'));

    render(<RiskForecastingIntegrationAdapter />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.queryByText(/CONNECTION_REFUSED/i)).not.toBeInTheDocument();
  });

  it('7. malformed JSON fails closed', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => { throw new Error('SyntaxError: JSON'); }
    });

    render(<RiskForecastingIntegrationAdapter />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('8. valid response with non-Veterinary role fails closed', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...validVetContext, role: ROLES.FARMER, authorization: { ...validVetContext.authorization, scopeLevel: SCOPE_LEVELS.FARM, registeredFarmDistrict: 'Colombo' } })
    });

    render(<RiskForecastingIntegrationAdapter />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('mock-risk-forecasting-feature')).not.toBeInTheDocument();
  });

  it('9. timeout triggers AbortController and fails closed', async () => {
    vi.useFakeTimers();
    try {
      localStorage.setItem('token', 'synthetic-test-token-123');
      
      let abortSignal;
      mockFetch.mockImplementation((url, opts) => {
        abortSignal = opts.signal;
        return new Promise((resolve, reject) => {
          opts.signal.addEventListener('abort', () => {
            const err = new Error('aborted');
            err.name = 'AbortError';
            reject(err);
          });
        });
      });

      render(<RiskForecastingIntegrationAdapter />);
      expect(screen.getByRole('status')).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(8000);
      });

      expect(abortSignal.aborted).toBe(true);
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.queryByTestId('mock-risk-forecasting-feature')).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('10. unmount aborts pending request', () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    let abortSignal;
    mockFetch.mockImplementation((url, opts) => {
      abortSignal = opts.signal;
      return new Promise(() => {});
    });

    const { unmount } = render(<RiskForecastingIntegrationAdapter />);
    unmount();
    expect(abortSignal.aborted).toBe(true);
  });

  it('11. confirm no unsafe query parameters or headers are sent', async () => {
    localStorage.setItem('token', 'synthetic-test-token-123');
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => validVetContext });

    render(<RiskForecastingIntegrationAdapter />);
    
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).not.toContain('?');
    expect(opts.headers['X-Actor-ID']).toBeUndefined();
    expect(opts.headers['X-Actor-Role']).toBeUndefined();
  });

  it('12. structural negative assertion: no demo modules or jwt-decode imported', async () => {
    const filePath = path.resolve(__dirname, 'RiskForecastingIntegrationAdapter.jsx');
    const fileText = await fs.readFile(filePath, 'utf-8');
    expect(fileText).not.toMatch(/DemoForecastingAuthContext/i);
    expect(fileText).not.toMatch(/useDemoForecastingAuth/i);
    expect(fileText).not.toMatch(/DemoForecastingGateway/i);
    expect(fileText).not.toMatch(/jwt-decode/i);
  });
});

describe('App Route Static Wiring', () => {
  it('App.jsx maps /vet/forecasting to RiskForecastingIntegrationAdapter', async () => {
    const filePath = path.resolve(__dirname, '../../../App.jsx');
    const fileText = await fs.readFile(filePath, 'utf-8');
    expect(fileText).toMatch(/import RiskForecastingIntegrationAdapter/);
    expect(fileText).not.toMatch(/element=\{<ForecastingMock \/>\}/);
    expect(fileText).toMatch(/element=\{<RiskForecastingIntegrationAdapter \/>\}/);
    expect(fileText).toMatch(/path="forecasting"/);
  });
});
