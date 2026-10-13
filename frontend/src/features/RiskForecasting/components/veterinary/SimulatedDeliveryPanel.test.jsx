import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SimulatedDeliveryPanel } from './SimulatedDeliveryPanel';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';

vi.mock('../../services/riskForecastingWorkflowApi', async () => {
  const actual = await vi.importActual('../../services/riskForecastingWorkflowApi');
  return {
    ...actual,
    enqueueNotificationBatch: vi.fn(),
    getNotificationBatch: vi.fn(),
    listNotificationBatches: vi.fn().mockResolvedValue({ batches: [] }),
    listNotificationDeliveries: vi.fn(),
    dispatchNotificationBatch: vi.fn(),
    retryFailedNotificationDeliveries: vi.fn(),
    cancelNotificationBatch: vi.fn(),
  };
});

describe('SimulatedDeliveryPanel Component', () => {
  const validVetContext = Object.freeze({
    userId: 'usr_vet_test_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Anuradhapura']),
      assignedFarmIds: Object.freeze(['DEMO_FARM_001']),
    }),
    permissions: Object.freeze({
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: false,
    }),
  });

  const approvedAdvisory = Object.freeze({
    advisory_id: 'adv_test_001',
    status: 'APPROVED',
  });

  const draftAdvisory = Object.freeze({
    advisory_id: 'adv_test_002',
    status: 'DRAFT',
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders locked panel notice when advisory status is DRAFT', () => {
    render(<SimulatedDeliveryPanel advisory={draftAdvisory} viewerContext={validVetContext} />);
    expect(screen.getByText(/Simulated Delivery Enqueue Locked/i)).toBeInTheDocument();
    expect(screen.getByText(/Notification batches can only be enqueued and simulated/i)).toBeInTheDocument();
  });

  it('renders mandatory simulation clarification disclaimer when advisory is APPROVED', async () => {
    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [] });

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    expect(screen.getByRole('heading', { name: /Embedded Simulated Delivery Panel/i })).toBeInTheDocument();
    expect(screen.getByText(/Standalone simulation only/i)).toBeInTheDocument();
  });

  it('does not automatically enqueue or dispatch batches upon mounting', async () => {
    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [] });

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    await waitFor(() => expect(workflowApi.listNotificationBatches).toHaveBeenCalled());
    expect(workflowApi.enqueueNotificationBatch).not.toHaveBeenCalled();
    expect(workflowApi.dispatchNotificationBatch).not.toHaveBeenCalled();
  });

  it('displays all 6 summary batch counts (Total, Pending, Processing, Simulated Success, Failed, Cancelled)', async () => {
    const mockFullBatch = {
      batch_id: 'batch_counts_123',
      advisory_id: 'adv_test_001',
      recipient_count: 10,
      pending_count: 2,
      processing_count: 1,
      succeeded_count: 5,
      failed_count: 1,
      cancelled_count: 1,
      status: 'PARTIALLY_FAILED',
    };

    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [mockFullBatch] });
    workflowApi.getNotificationBatch.mockResolvedValue(mockFullBatch);
    workflowApi.listNotificationDeliveries.mockResolvedValue({ deliveries: [] });

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    expect(await screen.findByText('10')).toBeInTheDocument(); // Total
    expect(screen.getByText('Simulated Success')).toBeInTheDocument();
    expect(screen.getByText('Cancelled')).toBeInTheDocument();
  });

  it('enqueues a new simulated notification batch when requested', async () => {
    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [] });
    workflowApi.enqueueNotificationBatch.mockResolvedValue({
      batch_id: 'batch_new_123',
      advisory_id: 'adv_test_001',
      recipient_count: 5,
      pending_count: 5,
      processing_count: 0,
      succeeded_count: 0,
      failed_count: 0,
      cancelled_count: 0,
      status: 'QUEUED',
    });
    workflowApi.listNotificationDeliveries.mockResolvedValue({ deliveries: [] });

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    const createBtn = await screen.findByRole('button', { name: /Create Simulated Delivery Batch/i });
    await waitFor(() => expect(createBtn).not.toBeDisabled());
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(workflowApi.enqueueNotificationBatch).toHaveBeenCalledWith('adv_test_001', {
        created_by: 'usr_vet_test_001',
      });
    });

    expect(screen.getByText(/Batch: batch_new_123/i)).toBeInTheDocument();
  });

  it('executes simulated dispatch when Simulate Farmer Notification button is clicked', async () => {
    const mockBatch = {
      batch_id: 'batch_active_123',
      advisory_id: 'adv_test_001',
      recipient_count: 2,
      pending_count: 2,
      processing_count: 0,
      succeeded_count: 0,
      failed_count: 0,
      cancelled_count: 0,
      status: 'QUEUED',
    };

    const mockDispatchedBatch = {
      ...mockBatch,
      pending_count: 0,
      succeeded_count: 2,
      status: 'COMPLETED',
    };

    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [mockBatch] });
    workflowApi.getNotificationBatch.mockResolvedValue(mockBatch);
    workflowApi.listNotificationDeliveries.mockResolvedValue({
      deliveries: [
        {
          delivery_id: 'del_01',
          recipient_id: 'DEMO_FARM_001',
          resolved_message: 'Test resolved advice',
          status: 'SUCCEEDED',
          provider_reference: 'MOCK_REF_001',
        },
      ],
    });
    workflowApi.dispatchNotificationBatch.mockResolvedValue(mockDispatchedBatch);

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    const dispatchBtn = await screen.findByRole('button', { name: /Simulate Farmer Notification/i });
    fireEvent.click(dispatchBtn);

    await waitFor(() => {
      expect(workflowApi.dispatchNotificationBatch).toHaveBeenCalledWith('batch_active_123');
    });

    expect(screen.getAllByText(/SIMULATED SUCCESS/i).length).toBeGreaterThan(0);
  });

  it('handles retry of failed simulated deliveries', async () => {
    const failedBatch = {
      batch_id: 'batch_failed_123',
      advisory_id: 'adv_test_001',
      recipient_count: 2,
      pending_count: 0,
      processing_count: 0,
      succeeded_count: 1,
      failed_count: 1,
      cancelled_count: 0,
      status: 'PARTIALLY_FAILED',
    };

    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [failedBatch] });
    workflowApi.getNotificationBatch.mockResolvedValue(failedBatch);
    workflowApi.listNotificationDeliveries.mockResolvedValue({
      deliveries: [
        {
          delivery_id: 'del_02',
          recipient_id: 'DEMO_FARM_002',
          resolved_message: 'Failed message',
          status: 'FAILED',
          last_error: 'Simulated network timeout',
        },
      ],
    });
    workflowApi.retryFailedNotificationDeliveries.mockResolvedValue({
      ...failedBatch,
      pending_count: 1,
      failed_count: 0,
    });

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    const retryBtn = await screen.findByRole('button', { name: /Retry Failed Simulated Deliveries/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(workflowApi.retryFailedNotificationDeliveries).toHaveBeenCalledWith('batch_failed_123');
    });
  });

  it('cancels pending batch when Cancel Pending Batch button is clicked', async () => {
    const pendingBatch = {
      batch_id: 'batch_pending_999',
      advisory_id: 'adv_test_001',
      recipient_count: 3,
      pending_count: 3,
      processing_count: 0,
      succeeded_count: 0,
      failed_count: 0,
      cancelled_count: 0,
      status: 'QUEUED',
    };

    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [pendingBatch] });
    workflowApi.getNotificationBatch.mockResolvedValue(pendingBatch);
    workflowApi.listNotificationDeliveries.mockResolvedValue({ deliveries: [] });
    workflowApi.cancelNotificationBatch.mockResolvedValue({
      ...pendingBatch,
      status: 'CANCELLED',
      pending_count: 0,
      cancelled_count: 3,
    });

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    const cancelBtn = await screen.findByRole('button', { name: /Cancel Pending Batch/i });
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(workflowApi.cancelNotificationBatch).toHaveBeenCalledWith('batch_pending_999');
    });
  });

  it('sanitizes unexpected runtime errors and prevents forbidden delivery claims', async () => {
    workflowApi.listNotificationBatches.mockResolvedValue({ batches: [] });
    workflowApi.enqueueNotificationBatch.mockRejectedValue(new TypeError('Uncaught TypeError at index.js:12'));

    render(<SimulatedDeliveryPanel advisory={approvedAdvisory} viewerContext={validVetContext} />);

    const createBtn = await screen.findByRole('button', { name: /Create Simulated Delivery Batch/i });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    // Sanitized fallback error message, no JS stack trace
    expect(screen.getByText(/Failed to enqueue notification batch/i)).toBeInTheDocument();
    expect(screen.queryByText(/TypeError at index.js/i)).not.toBeInTheDocument();

    // Wording safety: zero forbidden claims (no claims that a farmer was actually reached)
    expect(screen.queryByText(/Delivered to farmer/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Farmer read the notification/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SMS sent to farmer/i)).not.toBeInTheDocument();
  });
});
