import React, { useState } from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DaphFollowUpComposer } from './daph/DaphFollowUpComposer';
import { VeterinaryAssignedFollowUps } from './veterinary/VeterinaryAssignedFollowUps';
import { DaphFollowUpMonitoring } from './daph/DaphFollowUpMonitoring';
import { ROLES, SCOPE_LEVELS } from '../contracts/viewerContext';
import * as workflowApi from '../services/riskForecastingWorkflowApi';

vi.mock('../services/riskForecastingWorkflowApi', async () => {
  const actual = await vi.importActual('../services/riskForecastingWorkflowApi');
  return {
    ...actual,
    listEligibleFollowUpVets: vi.fn(),
    issueFollowUp: vi.fn(),
    listFollowUps: vi.fn(),
    getFollowUp: vi.fn(),
    acknowledgeFollowUp: vi.fn(),
    startFollowUpAction: vi.fn(),
    completeFollowUp: vi.fn(),
    cancelFollowUp: vi.fn(),
    escalateFollowUp: vi.fn(),
  };
});

describe('DaphVetFollowUpWorkflowIntegration (Phase 7 Cross-Role Continuity)', () => {
  // Shared test ViewerContexts
  const daphContext = {
    userId: 'daph_hq_01',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      authorizedDistricts: ['Anuradhapura', 'Colombo'],
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

  const vetContext = {
    userId: 'vet_officer_01',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: ['DEMO_FARM_001'],
    },
    permissions: {
      viewDataQuality: true,
      viewModelTransparency: false,
      manageAlerts: false,
      recordResponse: true,
      viewReports: true,
    },
  };

  const sampleForecastRecord = {
    forecast_id: 'fdr_e2e_integration_001',
    disease: 'FMD',
    district: 'Anuradhapura',
    target_year: 2026,
    target_month: 9,
    risk_level: 'HIGH',
    probability: 0.88,
    probability_pct: 88.0,
    predicted_severity: 'HIGH',
    status: 'GENERATED',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('proves complete cross-role state continuity from DAPH Issuance -> Vet Lifecycle -> DAPH Monitoring', async () => {
    // Shared in-memory mock store for integration lifecycle tracking
    let storedFollowUp = null;

    // 1. Setup mock API implementations to simulate authoritative server state updates
    workflowApi.listEligibleFollowUpVets.mockImplementation(async (district) => {
      return {
        district: district || 'Anuradhapura',
        total_count: 1,
        veterinary_officers: [
          {
            vet_id: 'vet_officer_01',
            display_name: 'Dr. Nimal Perera (District Veterinary Officer)',
            assigned_districts: ['Anuradhapura'],
            active: true,
          },
        ],
      };
    });

    workflowApi.issueFollowUp.mockImplementation(async (payload, options) => {
      storedFollowUp = {
        follow_up_id: 'ffu_e2e_integration_999',
        forecast_id: payload.forecast_id,
        district: 'Anuradhapura',
        disease: 'FMD',
        target_year: 2026,
        target_month: 9,
        forecast_risk_level: 'HIGH',
        operational_priority: 'HIGH',
        instruction_summary: payload.instruction_summary,
        issued_by_daph_id: options?.actorContext?.actor_id || 'daph_hq_01',
        assigned_vet_id: payload.assigned_vet_id,
        status: 'ISSUED',
        version: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        issued_at: new Date().toISOString(),
      };
      return storedFollowUp;
    });

    workflowApi.listFollowUps.mockImplementation(async (filters) => {
      if (!storedFollowUp) return { total_count: 0, limit: 50, offset: 0, follow_ups: [] };
      if (filters.assigned_vet_id && filters.assigned_vet_id !== storedFollowUp.assigned_vet_id) {
        return { total_count: 0, limit: 50, offset: 0, follow_ups: [] };
      }
      return { total_count: 1, limit: 50, offset: 0, follow_ups: [{ ...storedFollowUp }] };
    });

    workflowApi.getFollowUp.mockImplementation(async (id) => {
      if (storedFollowUp && storedFollowUp.follow_up_id === id) {
        return { ...storedFollowUp };
      }
      throw new Error(`Not found: ${id}`);
    });

    workflowApi.acknowledgeFollowUp.mockImplementation(async (id, options) => {
      const ver = options?.ver || options?.version || 1;
      expect(ver).toBe(storedFollowUp.version);
      storedFollowUp.status = 'ACKNOWLEDGED';
      storedFollowUp.version += 1;
      storedFollowUp.acknowledged_at = new Date().toISOString();
      return { ...storedFollowUp };
    });

    workflowApi.startFollowUpAction.mockImplementation(async (id, options) => {
      const ver = options?.ver || options?.version || 2;
      expect(ver).toBe(storedFollowUp.version);
      storedFollowUp.status = 'ACTION_IN_PROGRESS';
      storedFollowUp.version += 1;
      storedFollowUp.action_started_at = new Date().toISOString();
      return { ...storedFollowUp };
    });

    workflowApi.completeFollowUp.mockImplementation(async (id, options) => {
      const ver = options?.ver || options?.version || 3;
      expect(ver).toBe(storedFollowUp.version);
      storedFollowUp.status = 'COMPLETED';
      storedFollowUp.version += 1;
      storedFollowUp.completed_at = new Date().toISOString();
      return { ...storedFollowUp };
    });

    // STEP A: DAPH Official issues follow-up using DaphFollowUpComposer
    const onIssuedMock = vi.fn();
    const { unmount: unmountComposer } = render(
      <DaphFollowUpComposer
        forecastRecord={sampleForecastRecord}
        viewerContext={daphContext}
        onIssued={onIssuedMock}
      />
    );

    // Wait for eligible Vets dropdown to populate
    await waitFor(() => {
      expect(screen.getByText(/Dr. Nimal Perera/i)).toBeInTheDocument();
    });

    // Enter instruction summary in textarea (id="instruction-input")
    const textarea = screen.getByPlaceholderText(/Provide specific operational guidance/i);
    fireEvent.change(textarea, {
      target: { value: 'Conduct high-priority clinical inspection of all dairy herds.' },
    });

    // Step 1: Click "Review & Prepare Issue" button
    const reviewBtn = screen.getByRole('button', { name: /Review & Prepare Issue/i });
    fireEvent.click(reviewBtn);

    // Step 2: Click "Confirm & Issue Follow-Up" button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i })).toBeInTheDocument();
    });
    const confirmBtn = screen.getByRole('button', { name: /Confirm & Issue Follow-Up/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(workflowApi.issueFollowUp).toHaveBeenCalledTimes(1);
    });

    expect(storedFollowUp).not.toBeNull();
    expect(storedFollowUp.follow_up_id).toBe('ffu_e2e_integration_999');
    expect(storedFollowUp.assigned_vet_id).toBe('vet_officer_01');
    expect(storedFollowUp.status).toBe('ISSUED');
    expect(storedFollowUp.version).toBe(1);

    unmountComposer();

    // STEP B: Veterinary Officer views assigned follow-ups in VeterinaryAssignedFollowUps
    const { unmount: unmountVet } = render(
      <VeterinaryAssignedFollowUps viewerContext={vetContext} />
    );

    await waitFor(() => {
      expect(screen.getByText(/ffu_e2e_integration_999/i)).toBeInTheDocument();
    });

    // Verify Scientific snapshot is rendered unchanged
    expect(screen.getAllByText(/Anuradhapura/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/FMD/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/HIGH/i).length).toBeGreaterThan(0);

    // Click View Details on table row
    const viewDetailsBtn = screen.getByRole('button', { name: /View Details/i });
    fireEvent.click(viewDetailsBtn);

    // Vet Acknowledges follow-up (version 1 -> 2)
    // 1. Click "Acknowledge" in detail panel
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Acknowledge$/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /^Acknowledge$/i }));

    // 2. Click "Confirm" in Modal
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Confirm/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

    await waitFor(() => {
      expect(workflowApi.acknowledgeFollowUp).toHaveBeenCalledTimes(1);
    });
    expect(storedFollowUp.status).toBe('ACKNOWLEDGED');
    expect(storedFollowUp.version).toBe(2);

    // Vet Starts Action (version 2 -> 3)
    // 1. Click "Start Action" in detail panel
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Start Action/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Start Action/i }));

    // 2. Click "Confirm" in Modal
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Confirm/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

    await waitFor(() => {
      expect(workflowApi.startFollowUpAction).toHaveBeenCalledTimes(1);
    });
    expect(storedFollowUp.status).toBe('ACTION_IN_PROGRESS');
    expect(storedFollowUp.version).toBe(3);

    // Vet Completes Action (version 3 -> 4)
    // 1. Click "Complete" in detail panel
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Complete$/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /^Complete$/i }));

    // 2. Click "Confirm" in Modal
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Confirm/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));

    await waitFor(() => {
      expect(workflowApi.completeFollowUp).toHaveBeenCalledTimes(1);
    });
    expect(storedFollowUp.status).toBe('COMPLETED');
    expect(storedFollowUp.version).toBe(4);

    unmountVet();

    // STEP C: DAPH Official reloads Monitoring Workspace and observes COMPLETED record
    render(<DaphFollowUpMonitoring viewerContext={daphContext} />);

    await waitFor(() => {
      expect(screen.getByText(/ffu_e2e_integration_999/i)).toBeInTheDocument();
    });

    const monitoringRow = screen.getByText(/ffu_e2e_integration_999/i).closest('tr');
    expect(within(monitoringRow).getByText(/COMPLETED/i)).toBeInTheDocument();

    // Verify DAPH workspace has NO Vet transition buttons (Acknowledge, Start, Complete)
    expect(screen.queryByRole('button', { name: /Acknowledge Receipt/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Start Action/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Complete Action/i })).not.toBeInTheDocument();
  });
});
