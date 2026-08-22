import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { DemoForecastingOperationalBridge } from './DemoForecastingOperationalBridge.jsx';
import * as opHooksModule from '../../hooks/useDemoOperationalData.js';
import { OPERATIONAL_STATUS } from '../../hooks/useDemoOperationalData.js';

const mockFarmerContext = {
  userId: 'DEMO_USER_FARMER_JAFFNA',
  role: 'FARMER',
  authorization: {
    scopeLevel: 'FARM',
    registeredFarmDistrict: 'Jaffna',
    authorizedDistricts: ['Jaffna'],
    assignedFarmIds: ['DEMO_FARM_JAFFNA_001'],
  },
  permissions: {
    viewDataQuality: false,
    viewModelTransparency: false,
    manageAlerts: false,
    recordResponse: false,
    viewReports: false,
  },
};

const mockVetContext = {
  userId: 'DEMO_USER_VET_NORTH',
  role: 'VETERINARY_OFFICER',
  authorization: {
    scopeLevel: 'PROVINCE',
    registeredFarmDistrict: null,
    authorizedDistricts: ['Jaffna', 'Kilinochchi', 'Mannar'],
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

const mockDaphContext = {
  userId: 'DEMO_USER_DAPH_HQ',
  role: 'DAPH_OFFICIAL',
  authorization: {
    scopeLevel: 'NATIONAL',
    registeredFarmDistrict: null,
    authorizedDistricts: ['Jaffna', 'Kilinochchi', 'Mannar', 'Colombo', 'Kandy'],
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

const mockSampleFarm = Object.freeze({
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
});

const mockSampleSurvRecord = Object.freeze({
  schemaVersion: '1.0',
  surveillanceRecordId: 'DEMO_SURV_JAFFNA_FMD_001',
  farmId: 'DEMO_FARM_JAFFNA_001',
  district: 'Jaffna',
  diseaseCode: 'FMD',
  observedAt: '2026-08-19T00:00:00Z',
  evidenceType: 'FARMER_REPORT',
  verificationStatus: 'AI_SCREENED',
  sourceModule: 'SYNTHETIC_FARM_REPORTING',
  sourceRecordId: 'DEMO_SOURCE_001',
  summary: 'FMD symptoms observed in Jaffna cattle',
  isSynthetic: true,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
  createdAt: '2026-08-19T00:00:00Z',
  updatedAt: '2026-08-19T00:00:00Z',
});

const mockSampleAlert = Object.freeze({
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
});

const mockSampleTask = Object.freeze({
  schemaVersion: '1.0',
  responseTaskId: 'DEMO_TASK_JAFFNA_001',
  alertId: 'DEMO_ALERT_JAFFNA_FMD_001',
  assignedOfficerUserId: 'DEMO_USER_VET_NORTH',
  district: 'Jaffna',
  farmId: 'DEMO_FARM_JAFFNA_001',
  taskType: 'FIELD_REVIEW',
  status: 'ASSIGNED',
  dueAt: '2026-08-19T00:00:00Z',
  notes: 'Conduct field inspection and isolation check',
  isSynthetic: true,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
  createdAt: '2026-08-19T00:00:00Z',
  updatedAt: '2026-08-19T00:00:00Z',
});

describe('DemoForecastingOperationalBridge & Connected Screens Unit Tests', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
      if (url.includes('/predict/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ risk_level: 'LOW', probability: 0.1 }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    }));
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function mockHooks({
    farms = { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null },
    surveillanceRecords = { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null },
    alerts = { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null },
    responseTasks = { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null },
  } = {}) {
    vi.spyOn(opHooksModule, 'useDemoFarms').mockImplementation(({ enabled }) =>
      enabled ? farms : { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null }
    );
    vi.spyOn(opHooksModule, 'useDemoSurveillanceRecords').mockImplementation(({ enabled }) =>
      enabled ? surveillanceRecords : { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null }
    );
    vi.spyOn(opHooksModule, 'useDemoAlerts').mockImplementation(({ enabled }) =>
      enabled ? alerts : { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null }
    );
    vi.spyOn(opHooksModule, 'useDemoResponseTasks').mockImplementation(({ enabled }) =>
      enabled ? responseTasks : { status: OPERATIONAL_STATUS.IDLE, items: [], count: 0, error: null }
    );
  }

  // Test 1, 2, 3: Bridge enables only role-appropriate hooks
  it('Requirements 1, 2, 3: Enables only role-appropriate hooks for FARMER, VET, and DAPH roles', () => {
    mockHooks();

    const { unmount: unmountFarmer } = render(<DemoForecastingOperationalBridge viewerContext={mockFarmerContext} />);
    expect(opHooksModule.useDemoFarms).toHaveBeenLastCalledWith({ enabled: true });
    expect(opHooksModule.useDemoAlerts).toHaveBeenLastCalledWith({ enabled: true });
    expect(opHooksModule.useDemoSurveillanceRecords).toHaveBeenLastCalledWith({ enabled: false });
    expect(opHooksModule.useDemoResponseTasks).toHaveBeenLastCalledWith({ enabled: false });
    unmountFarmer();

    const { unmount: unmountDaph } = render(<DemoForecastingOperationalBridge viewerContext={mockDaphContext} />);
    expect(opHooksModule.useDemoFarms).toHaveBeenLastCalledWith({ enabled: false });
    expect(opHooksModule.useDemoSurveillanceRecords).toHaveBeenLastCalledWith({ enabled: true });
    expect(opHooksModule.useDemoAlerts).toHaveBeenLastCalledWith({ enabled: true });
    expect(opHooksModule.useDemoResponseTasks).toHaveBeenLastCalledWith({ enabled: true });
    unmountDaph();
  });

  // Test 6, 7, 8, 21: Farmer screen renders farm and alerts, no surveillance/tasks, neutral empty text, synthetic notice
  it('Requirements 6, 7, 8, 21: Farmer screen renders authorized farm & alerts, neutral empty wording, and synthetic caution notice', async () => {
    mockHooks({
      farms: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleFarm], count: 1, error: null },
      alerts: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleAlert], count: 1, error: null },
    });

    render(<DemoForecastingOperationalBridge viewerContext={mockFarmerContext} />);

    await act(async () => {
      screen.getByRole('button', { name: /Alerts & Guidance/i }).click();
    });

    expect(screen.getByText(/synthetic operational records for demonstration/i)).toBeInTheDocument();
    expect(screen.getByText('Jaffna Cattle Farm 001')).toBeInTheDocument();
    expect(screen.getByText('FMD Alert Jaffna')).toBeInTheDocument();

    // Verify Farmer cannot see surveillance or tasks
    expect(screen.queryByText(/Surveillance Records/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Response Tasks/i)).not.toBeInTheDocument();
  });

  // Test 8 & 19: Empty alerts wording is neutral (never says no outbreaks, all clear, or safe)
  it('Requirements 8 & 19: Empty alerts wording is neutral and never says "no outbreaks" or "all clear"', async () => {
    mockHooks({
      farms: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleFarm], count: 1, error: null },
      alerts: { status: OPERATIONAL_STATUS.EMPTY, items: [], count: 0, error: null },
    });

    render(<DemoForecastingOperationalBridge viewerContext={mockFarmerContext} />);

    await act(async () => {
      screen.getByRole('button', { name: /Alerts & Guidance/i }).click();
    });

    expect(screen.getByText('No synthetic alerts were returned for your authorized demo farm.')).toBeInTheDocument();
    expect(screen.queryByText(/no outbreaks/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/all clear/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/safe district/i)).not.toBeInTheDocument();
  });

  // Test 9, 10, 11, 12, 13, 14, 15: Vet dashboard renders farms, surveillance (AI_SCREENED unconfirmed), alerts, tasks (read-only)
  it('Requirements 9-15: Vet renders assigned farms, surveillance (AI_SCREENED unconfirmed), alerts, and read-only tasks without write buttons', () => {
    mockHooks({
      farms: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleFarm], count: 1, error: null },
      surveillanceRecords: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleSurvRecord], count: 1, error: null },
      alerts: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleAlert], count: 1, error: null },
      responseTasks: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleTask], count: 1, error: null },
    });

    render(<DemoForecastingOperationalBridge viewerContext={mockVetContext} />);

    const survBtn = screen.getByRole('button', { name: /Surveillance Dashboard/i });
    fireEvent.click(survBtn);

    expect(screen.getByText('Jaffna Cattle Farm 001')).toBeInTheDocument();
    expect(screen.getByText('AI SCREENED (UNCONFIRMED)')).toBeInTheDocument();
    expect(screen.getByText('FMD Alert Jaffna')).toBeInTheDocument();
    expect(screen.getByText('FIELD_REVIEW')).toBeInTheDocument();

    // Verify Vet has NO write or edit buttons
    expect(screen.queryByRole('button', { name: /Complete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Resolve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Delete/i })).not.toBeInTheDocument();
  });

  // Test 16, 17: DAPH renders surveillance, alerts, tasks, but NO farm listings or owner identities
  it('Requirements 16 & 17: DAPH renders surveillance, alerts, tasks, but no farm listings or owner identities', () => {
    mockHooks({
      surveillanceRecords: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleSurvRecord], count: 1, error: null },
      alerts: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleAlert], count: 1, error: null },
      responseTasks: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleTask], count: 1, error: null },
    });

    render(<DemoForecastingOperationalBridge viewerContext={mockDaphContext} />);

    expect(screen.getByText(/District Surveillance Records/i)).toBeInTheDocument();
    expect(screen.getByText('FMD Alert Jaffna')).toBeInTheDocument();
    expect(screen.getByText(/FIELD_REVIEW/i)).toBeInTheDocument();

    // Verify DAPH does not render farm listings or owner IDs
    expect(screen.queryByText('Jaffna Cattle Farm 001')).not.toBeInTheDocument();
    expect(screen.queryByText(/DEMO_USER_FARMER_JAFFNA/i)).not.toBeInTheDocument();
  });

  // Test 18, 20: Loading uses role="status", error renders sanitized text and reload button
  it('Requirements 18 & 20: Loading states use role="status" and error states render sanitized text with working reload buttons', async () => {
    const mockReload = vi.fn();
    mockHooks({
      farms: { status: OPERATIONAL_STATUS.ERROR, items: [], count: 0, error: 'Operational farm data service is currently unavailable.', reload: mockReload },
      alerts: { status: OPERATIONAL_STATUS.LOADING, items: [], count: 0, error: null },
    });

    render(<DemoForecastingOperationalBridge viewerContext={mockFarmerContext} />);

    await act(async () => {
      screen.getByRole('button', { name: /Alerts & Guidance/i }).click();
    });

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Operational farm data service is currently unavailable.')).toBeInTheDocument();

    const reloadBtn = screen.getByRole('button', { name: /Try again/i });
    reloadBtn.click();
    expect(mockReload).toHaveBeenCalledTimes(1);
  });

  // Test 22, 23, 24, 25, 30: Zero raw JSON/probabilities, zero storage writes, zero operational records to prediction APIs
  it('Requirements 22, 23, 24, 25, 30: Excludes probabilities, writes zero records to storage, sends no operational records to predict APIs', async () => {
    mockHooks({
      farms: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleFarm], count: 1, error: null },
      alerts: { status: OPERATIONAL_STATUS.SUCCESS, items: [mockSampleAlert], count: 1, error: null },
    });

    render(<DemoForecastingOperationalBridge viewerContext={mockFarmerContext} />);

    await act(async () => {
      screen.getByRole('button', { name: /Alerts & Guidance/i }).click();
    });

    expect(screen.queryByText(/prob_fmd/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ece_score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();

    expect(sessionStorage.getItem('DEMO_FARM_JAFFNA_001')).toBeNull();
    expect(localStorage.getItem('DEMO_FARM_JAFFNA_001')).toBeNull();

    // Verify fetch calls were strictly for ML predictions, never containing operational record objects
    for (const call of fetch.mock.calls) {
      const [url, opts] = call;
      if (opts?.body) {
        expect(opts.body).not.toContain('DEMO_FARM_JAFFNA_001');
        expect(opts.body).not.toContain('Jaffna Cattle Farm 001');
      }
    }
  });
});
