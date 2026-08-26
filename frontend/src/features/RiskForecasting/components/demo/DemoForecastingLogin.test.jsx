import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { DemoForecastingLogin, APPROVED_DEMO_ACCOUNTS } from './DemoForecastingLogin.jsx';
import * as authHookModule from '../../hooks/useDemoForecastingAuth.js';
import { AUTH_STATUS } from '../../context/DemoForecastingAuthContext.jsx';

describe('DemoForecastingLogin Component Unit Tests', () => {
  const mockLogin = vi.fn();

  beforeEach(() => {
    mockLogin.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mockAuthContext(overrides = {}) {
    vi.spyOn(authHookModule, 'useDemoForecastingAuth').mockReturnValue({
      demoEnabled: true,
      status: AUTH_STATUS.UNAUTHENTICATED,
      viewerContext: null,
      error: null,
      login: mockLogin,
      logout: vi.fn(),
      refreshViewerContext: vi.fn(),
      ...overrides,
    });
  }

  // Test 4: Exactly one h1 in login view
  it('Requirement 4: Renders exactly one page-level h1 tag', () => {
    mockAuthContext();
    render(<DemoForecastingLogin />);

    const h1Elements = screen.getAllByRole('heading', { level: 1 });
    expect(h1Elements).toHaveLength(1);
    expect(h1Elements[0]).toHaveTextContent('Disease Forecasting Demonstration');
  });

  // Test 5, 6, 7: Labels, input types, autocomplete, and empty password
  it('Requirement 5, 6, 7: Renders visible associated labels, password type, current-password autocomplete, and unpopulated password', () => {
    mockAuthContext();
    render(<DemoForecastingLogin />);

    const loginInput = screen.getByLabelText('Login Name');
    expect(loginInput).toBeInTheDocument();
    expect(loginInput).toHaveAttribute('autocomplete', 'username');

    const passwordInput = screen.getByLabelText('Password');
    expect(passwordInput).toBeInTheDocument();
    expect(passwordInput).toHaveAttribute('type', 'password');
    expect(passwordInput).toHaveAttribute('autocomplete', 'current-password');
    expect(passwordInput.value).toBe('');
  });

  // Test 8 & 9: Only approved accounts offered, no role/district selector
  it('Requirement 8 & 9: Offers only approved demo login names and no role/district/permission selectors', () => {
    mockAuthContext();
    render(<DemoForecastingLogin />);

    const select = screen.getByLabelText('Select Demo Account');
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
    expect(options).toEqual([
      'demo_farmer_jaffna',
      'demo_vet_north',
      'demo_daph_official',
    ]);

    expect(screen.queryByLabelText(/role/i)).toBeNull();
    expect(screen.queryByLabelText(/district/i)).toBeNull();
    expect(screen.queryByLabelText(/farm/i)).toBeNull();
    expect(screen.queryByLabelText(/permission/i)).toBeNull();
  });

  // Test 10, 11, 12, 13: Form submission, trimming username, unchanged password, duplicate prevention
  it('Requirement 10, 11, 12, 13: Trims login name, passes password unchanged, calls login once, and blocks duplicate submits', async () => {
    mockLogin.mockResolvedValueOnce({ role: 'FARMER' });
    mockAuthContext();

    render(<DemoForecastingLogin />);

    const loginInput = screen.getByLabelText('Login Name');
    const passwordInput = screen.getByLabelText('Password');
    const submitBtn = screen.getByRole('button', { name: /sign in to demo/i });

    fireEvent.change(loginInput, { target: { value: '  demo_vet_north   ' } });
    fireEvent.change(passwordInput, { target: { value: ' ExactPassword123! ' } });

    await act(async () => {
      fireEvent.click(submitBtn);
    });

    expect(mockLogin).toHaveBeenCalledTimes(1);
    expect(mockLogin).toHaveBeenCalledWith('demo_vet_north', ' ExactPassword123! ');
  });

  // Test 14: Password field clears after failed login
  it('Requirement 14: Clears password input after failed login', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid login name or password.'));
    mockAuthContext();

    render(<DemoForecastingLogin />);

    const passwordInput = screen.getByLabelText('Password');
    const submitBtn = screen.getByRole('button', { name: /sign in to demo/i });

    fireEvent.change(passwordInput, { target: { value: 'WrongPassword' } });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(passwordInput.value).toBe('');
    });
  });

  // Test 15 & 16: Error alert accessibility and sanitized text
  it('Requirement 15 & 16: Displays error in role="alert" with sanitized message and no internal text', () => {
    mockAuthContext({ error: 'Invalid login name or password.' });
    render(<DemoForecastingLogin />);

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent('Invalid login name or password.');
    expect(alert).not.toHaveTextContent('JWT');
    expect(alert).not.toHaveTextContent('MongoDB');
  });

  // Test 19: Synthetic data and no model training notices
  it('Requirement 19: Displays visible synthetic data and no model training notices', () => {
    mockAuthContext();
    render(<DemoForecastingLogin />);

    expect(screen.getByText(/Synthetic Demonstration Data/i)).toBeInTheDocument();
    expect(screen.getByText(/must not be used for ML model training/i)).toBeInTheDocument();
  });
});
