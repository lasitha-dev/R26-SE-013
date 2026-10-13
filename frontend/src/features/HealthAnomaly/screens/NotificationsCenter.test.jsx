import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import NotificationsCenter from './NotificationsCenter';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('NotificationsCenter Component', () => {
  const mockCattleAlert = {
    id: 'cattle_1',
    identifier: 'C-100',
    breed: 'Holstein',
    health_status: 'Alert',
  };

  const mockForecastAlert = {
    _id: 'forecast_1',
    title: 'FMD Advisory',
    message: 'High risk detected',
    created_at: '2024-05-01T10:00:00Z',
    severity: 'HIGH',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    localStorage.setItem('token', 'test_token');
  });

  const mockFetchResponses = (cattleRes, forecastRes) => {
    global.fetch.mockImplementation((url) => {
      if (url.includes('/api/cattle')) {
        return Promise.resolve(cattleRes);
      }
      if (url.includes('/api/v1/risk-forecasting/notifications')) {
        return Promise.resolve(forecastRes);
      }
      return Promise.reject(new Error('Unknown API'));
    });
  };

  const okRes = (data) => ({ ok: true, json: () => Promise.resolve(data) });
  const failRes = () => ({ ok: false, status: 500 });
  const errorRes = () => Promise.reject(new Error('Network error'));

  it('1. Existing cattle alert renders', async () => {
    mockFetchResponses(okRes([mockCattleAlert]), okRes([]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('C-100')).toBeInTheDocument();
  });

  it('2. Forecasting notification renders', async () => {
    mockFetchResponses(okRes([]), okRes([mockForecastAlert]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('FMD Advisory')).toBeInTheDocument();
    expect(screen.getByText('High risk detected')).toBeInTheDocument();
  });

  it('3. Cattle and Forecasting notifications render together', async () => {
    mockFetchResponses(okRes([mockCattleAlert]), okRes([mockForecastAlert]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('C-100')).toBeInTheDocument();
    expect(screen.getByText('FMD Advisory')).toBeInTheDocument();
  });

  it('4. Cattle-fetch failure still performs Forecasting fetch and displays Forecasting notification', async () => {
    mockFetchResponses(errorRes(), okRes([mockForecastAlert]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('FMD Advisory')).toBeInTheDocument();
    expect(screen.queryByText('C-100')).not.toBeInTheDocument();
  });

  it('5. Forecasting-fetch failure preserves cattle alert', async () => {
    mockFetchResponses(okRes([mockCattleAlert]), errorRes());
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('C-100')).toBeInTheDocument();
    expect(screen.queryByText('FMD Advisory')).not.toBeInTheDocument();
  });

  it('6. Empty Forecasting list preserves existing cattle UI', async () => {
    mockFetchResponses(okRes([mockCattleAlert]), okRes([]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('C-100')).toBeInTheDocument();
    expect(screen.queryByText('FMD Advisory')).not.toBeInTheDocument();
  });

  it('7 & 8. Relative /api/v1/risk-forecasting/notifications URL is used and Bearer token is sent', async () => {
    mockFetchResponses(okRes([]), okRes([]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/risk-forecasting/notifications',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test_token' },
        })
      );
    });
  });

  it('9. Existing cattle click/navigation behavior remains', async () => {
    mockFetchResponses(okRes([mockCattleAlert]), okRes([]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    const btn = await screen.findByRole('button', { name: /View Profile & Triage/i });
    fireEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith('/health/animal-profile/cattle_1');
  });

  it('10. Non-functional Acknowledge button is absent', async () => {
    mockFetchResponses(okRes([]), okRes([mockForecastAlert]));
    render(
      <MemoryRouter>
        <NotificationsCenter />
      </MemoryRouter>
    );
    await screen.findByText('FMD Advisory');
    expect(screen.queryByRole('button', { name: /Acknowledge/i })).not.toBeInTheDocument();
  });
});
