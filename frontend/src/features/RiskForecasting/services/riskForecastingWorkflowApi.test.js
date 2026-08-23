import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  RiskForecastingWorkflowApiError,
  WORKFLOW_DELIVERY_STATUS,
  WORKFLOW_PROVIDER_STATUS,
  createForecastRecord,
  getForecastRecord,
  listForecastRecords,
  listForecastDistricts,
  listAssignedRecipients,
  createAdvisoryDraft,
  previewAdvisory,
  getAdvisory,
  listAdvisories,
  updateAdvisoryDraft,
  markAdvisoryReadyForReview,
  approveAdvisory,
  cancelAdvisory,
  enqueueNotificationBatch,
  getNotificationBatch,
  listNotificationBatches,
  listNotificationDeliveries,
  dispatchNotificationBatch,
  retryFailedNotificationDeliveries,
  cancelNotificationBatch,
} from './riskForecastingWorkflowApi';

describe('RiskForecastingWorkflowApi Service Unit Tests', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  function mockFetchJsonResponse(data, status = 200) {
    globalThis.fetch.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      text: async () => (data !== undefined ? JSON.stringify(data) : ''),
      json: async () => data,
    });
  }

  function mockFetchTextResponse(text, status = 200) {
    globalThis.fetch.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      text: async () => text,
      json: async () => {
        try {
          return JSON.parse(text);
        } catch (_) {
          throw new Error('Invalid JSON');
        }
      },
    });
  }

  // ─── A. COMMON BEHAVIOR ──────────────────────────────────────────────────

  it('1 & 2. Uses correct API path without duplicate /api/v1 prefix', async () => {
    mockFetchJsonResponse({ forecast_id: 'fdr_001' });
    await getForecastRecord('fdr_001');

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/records/fdr_001');
    expect(callUrl).not.toContain('/api/v1/api/v1');
  });

  it('3. Encodes path identifier parameters cleanly', async () => {
    mockFetchJsonResponse({ advisory_id: 'adv/123#special' });
    await getAdvisory('adv/123#special');

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/advisories/adv%2F123%23special');
  });

  it('4 & 5. Serializes query strings correctly, omitting empty optional params while retaining numeric 0 and boolean false', async () => {
    mockFetchJsonResponse({ records: [], total: 0 });
    await listForecastRecords({
      disease: 'FMD',
      district: '',
      target_month: 0,
      status: undefined,
      limit: 10,
      offset: 0,
    });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('disease=FMD');
    expect(callUrl).toContain('target_month=0');
    expect(callUrl).toContain('offset=0');
    expect(callUrl).toContain('limit=10');
    expect(callUrl).not.toContain('district=');
    expect(callUrl).not.toContain('status=');
  });

  it('6. Forwards AbortSignal to fetch', async () => {
    mockFetchJsonResponse({ recipients: [] });
    const controller = new AbortController();
    await listAssignedRecipients({ vetId: 'vet_01', signal: controller.signal });

    const options = globalThis.fetch.mock.calls[0][1];
    expect(options.signal).toBe(controller.signal);
  });

  it('7. Sets Content-Type header and JSON stringifies body for POST requests', async () => {
    mockFetchJsonResponse({ forecast_id: 'fdr_100' });
    const payload = { disease: 'FMD', district: 'Anuradhapura', year: 2024, month: 1 };
    await createForecastRecord(payload);

    const options = globalThis.fetch.mock.calls[0][1];
    expect(options.method).toBe('POST');
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(options.body).toBe(JSON.stringify(payload));
  });

  it('8. Handles empty 200/204 response body safely without error', async () => {
    mockFetchTextResponse('', 200);
    const result = await dispatchNotificationBatch('batch_001');
    expect(result).toBeNull();
  });

  it('9. Parses FastAPI string detail error correctly', async () => {
    mockFetchJsonResponse({ detail: 'Record not found in database.' }, 404);

    try {
      await getForecastRecord('missing_001');
      expect.fail('Should have thrown RiskForecastingWorkflowApiError');
    } catch (err) {
      expect(err).toBeInstanceOf(RiskForecastingWorkflowApiError);
      expect(err.status).toBe(404);
      expect(err.endpoint).toBe('/api/v1/risk-forecasting/records/missing_001');
      expect(err.message).toContain('API Error 404: Record not found in database.');
    }
  });

  it('10. Parses FastAPI object and list validation detail errors', async () => {
    const listDetail = [
      { loc: ['body', 'disease'], msg: 'Field required' },
      { loc: ['body', 'month'], msg: 'Must be integer' },
    ];
    mockFetchJsonResponse({ detail: listDetail }, 422);

    try {
      await createForecastRecord({});
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err.status).toBe(422);
      expect(err.message).toContain('Field required');
      expect(err.message).toContain('Must be integer');
    }
  });

  it('11. Retains status and endpoint on RiskForecastingWorkflowApiError instance', async () => {
    mockFetchJsonResponse({ detail: 'Unauthorized' }, 401);

    try {
      await listForecastRecords();
    } catch (err) {
      expect(err.status).toBe(401);
      expect(err.endpoint).toBe('/api/v1/risk-forecasting/records');
    }
  });

  it('12. Does not leak sensitive payload or request body into thrown error message', async () => {
    mockFetchJsonResponse({ detail: 'Validation failed' }, 400);

    const secretPayload = { vet_custom_note: 'SUPER_SECRET_NOTE_CONTENT_12345' };
    try {
      await createAdvisoryDraft(secretPayload);
    } catch (err) {
      expect(err.message).not.toContain('SUPER_SECRET_NOTE_CONTENT_12345');
    }
  });

  // ─── B. FORECAST RECORDS ─────────────────────────────────────────────────

  it('13. createForecastRecord sends POST /records with payload and optional Idempotency-Key header', async () => {
    mockFetchJsonResponse({ forecast_id: 'fdr_001' });
    await createForecastRecord(
      { disease: 'FMD', district: 'Colombo' },
      { idempotencyKey: 'idemp_key_999' }
    );

    const callUrl = globalThis.fetch.mock.calls[0][0];
    const options = globalThis.fetch.mock.calls[0][1];
    expect(callUrl).toContain('/api/v1/risk-forecasting/records');
    expect(options.method).toBe('POST');
    expect(options.headers['Idempotency-Key']).toBe('idemp_key_999');
  });

  it('14. getForecastRecord sends GET /records/{id}', async () => {
    mockFetchJsonResponse({ forecast_id: 'fdr_777' });
    await getForecastRecord('fdr_777');

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/records/fdr_777');
  });

  it('15 & 16. listForecastRecords maps filters to query parameters and NEVER uses /forecast-records', async () => {
    mockFetchJsonResponse({ records: [], total: 0 });
    await listForecastRecords({ disease: 'LSD', district: 'Jaffna', status: 'GENERATED' });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/records?disease=LSD&district=Jaffna&status=GENERATED');
    expect(callUrl).not.toContain('/forecast-records');
  });

  it('16b. listForecastDistricts sends GET /districts and handles AbortSignal correctly', async () => {
    mockFetchJsonResponse({ total_districts: 25, districts: ['Anuradhapura'], month_names: ['January'] });
    const controller = new AbortController();
    const res = await listForecastDistricts({ signal: controller.signal });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    const options = globalThis.fetch.mock.calls[0][1];
    expect(callUrl).toContain('/api/v1/risk-forecasting/districts');
    expect(options.method).toBe('GET');
    expect(options.signal).toBe(controller.signal);
    expect(res.total_districts).toBe(25);
  });

  // ─── C. RECIPIENTS ───────────────────────────────────────────────────────

  it('17, 18, 19. listAssignedRecipients maps vetId and optional district filter', async () => {
    mockFetchJsonResponse({ recipients: [], total_assigned: 5 });
    await listAssignedRecipients({ vetId: 'vet_officer_01', district: 'Anuradhapura' });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/recipients?vet_id=vet_officer_01&district=Anuradhapura');
  });

  it('20. Blank vetId throws validation error client-side without calling fetch', async () => {
    await expect(listAssignedRecipients({ vetId: '   ' })).rejects.toThrow('vetId is required and cannot be empty.');
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('21. Does not use preview route for recipient list discovery', async () => {
    mockFetchJsonResponse({ recipients: [] });
    await listAssignedRecipients({ vetId: 'vet_01' });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).not.toContain('/advisories/preview');
  });

  // ─── D. ADVISORIES ───────────────────────────────────────────────────────

  it('22. createAdvisoryDraft sends POST /advisories', async () => {
    mockFetchJsonResponse({ advisory_id: 'adv_001' });
    await createAdvisoryDraft({ forecast_id: 'fdr_001' });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/advisories');
  });

  it('23. previewAdvisory with existing advisoryId sends POST /advisories/preview with query param and null body', async () => {
    mockFetchJsonResponse({ previews: [] });
    await previewAdvisory({ advisoryId: 'adv_001' });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    const options = globalThis.fetch.mock.calls[0][1];
    expect(callUrl).toContain('/api/v1/risk-forecasting/advisories/preview?advisory_id=adv_001');
    expect(options.body).toBeUndefined();
  });

  it('24. previewAdvisory with unsaved draft sends POST /advisories/preview with draft JSON body and no advisory_id query param', async () => {
    mockFetchJsonResponse({ previews: [] });
    const draft = { forecast_id: 'fdr_001', recipient_scope: 'ALL_ASSIGNED' };
    await previewAdvisory({ draft });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    const options = globalThis.fetch.mock.calls[0][1];
    expect(callUrl).toBe(`${import.meta.env?.VITE_API_URL || ''}/api/v1/risk-forecasting/advisories/preview`);
    expect(callUrl).not.toContain('advisory_id=');
    expect(options.body).toBe(JSON.stringify(draft));
  });

  it('25. previewAdvisory rejects ambiguous call containing both or neither parameter client-side', async () => {
    await expect(previewAdvisory({ advisoryId: 'adv_001', draft: {} })).rejects.toThrow('Ambiguous preview request');
    await expect(previewAdvisory({})).rejects.toThrow('Preview request requires either advisoryId or draft');
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('26. getAdvisory, listAdvisories, and updateAdvisoryDraft work cleanly', async () => {
    mockFetchJsonResponse({ advisory_id: 'adv_001' });
    await getAdvisory('adv_001');
    expect(globalThis.fetch.mock.calls[0][0]).toContain('/advisories/adv_001');

    mockFetchJsonResponse({ advisories: [] });
    await listAdvisories({ status: 'REVIEW_READY' });
    expect(globalThis.fetch.mock.calls[1][0]).toContain('/advisories?status=REVIEW_READY');

    mockFetchJsonResponse({ advisory_id: 'adv_001', version: 2 });
    await updateAdvisoryDraft('adv_001', { vet_custom_note: 'Updated' });
    expect(globalThis.fetch.mock.calls[2][0]).toContain('/advisories/adv_001');
    expect(globalThis.fetch.mock.calls[2][1].method).toBe('PUT');
  });

  it('27. markAdvisoryReadyForReview sends POST /advisories/{id}/ready-for-review?version={version}', async () => {
    mockFetchJsonResponse({ advisory_id: 'adv_001', status: 'REVIEW_READY' });
    await markAdvisoryReadyForReview('adv_001', 1);

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/advisories/adv_001/ready-for-review?version=1');
  });

  it('28. approveAdvisory sends POST /advisories/{id}/approve with version and approved_by query params', async () => {
    mockFetchJsonResponse({ advisory_id: 'adv_001', status: 'APPROVED' });
    await approveAdvisory('adv_001', { version: 2, approvedBy: 'vet_officer_02' });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/advisories/adv_001/approve?version=2&approved_by=vet_officer_02');
  });

  it('29. cancelAdvisory sends POST /advisories/{id}/cancel?version={version}', async () => {
    mockFetchJsonResponse({ advisory_id: 'adv_001', status: 'CANCELLED' });
    await cancelAdvisory('adv_001', 3);

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/advisories/adv_001/cancel?version=3');
  });

  it('30. Preserves REVIEW_READY status value without translating to READY_FOR_REVIEW', async () => {
    mockFetchJsonResponse({ advisories: [{ advisory_id: 'adv_001', status: 'REVIEW_READY' }] });
    const res = await listAdvisories({ status: 'REVIEW_READY' });
    expect(res.advisories[0].status).toBe('REVIEW_READY');
  });

  // ─── E. NOTIFICATION BATCHES & PROVIDER CONTRACT ───────────────────────────

  it('31. enqueueNotificationBatch sends POST /advisories/{id}/notification-batches with optional Idempotency-Key', async () => {
    mockFetchJsonResponse({ batch_id: 'batch_001', status: 'QUEUED' });
    await enqueueNotificationBatch('adv_001', {}, { idempotencyKey: 'idemp_batch_100' });

    const callUrl = globalThis.fetch.mock.calls[0][0];
    const options = globalThis.fetch.mock.calls[0][1];
    expect(callUrl).toContain('/api/v1/risk-forecasting/advisories/adv_001/notification-batches');
    expect(options.headers['Idempotency-Key']).toBe('idemp_batch_100');
  });

  it('32, 33, 34. getNotificationBatch, listNotificationBatches, and listNotificationDeliveries work cleanly', async () => {
    mockFetchJsonResponse({ batch_id: 'batch_001' });
    await getNotificationBatch('batch_001');
    expect(globalThis.fetch.mock.calls[0][0]).toContain('/notification-batches/batch_001');

    mockFetchJsonResponse({ batches: [] });
    await listNotificationBatches({ status: 'COMPLETED' });
    expect(globalThis.fetch.mock.calls[1][0]).toContain('/notification-batches?status=COMPLETED');

    mockFetchJsonResponse({ deliveries: [] });
    await listNotificationDeliveries('batch_001', { status: 'SUCCEEDED' });
    expect(globalThis.fetch.mock.calls[2][0]).toContain('/notification-batches/batch_001/deliveries?status=SUCCEEDED');
  });

  it('35 & 37. retryFailedNotificationDeliveries sends POST /notification-batches/{id}/retry-failed and NEVER uses /retry', async () => {
    mockFetchJsonResponse({ batch_id: 'batch_001', status: 'COMPLETED' });
    await retryFailedNotificationDeliveries('batch_001');

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/notification-batches/batch_001/retry-failed');
    expect(callUrl.endsWith('/retry')).toBe(false);
  });

  it('36. cancelNotificationBatch sends POST /notification-batches/{id}/cancel', async () => {
    mockFetchJsonResponse({ batch_id: 'batch_001', status: 'CANCELLED' });
    await cancelNotificationBatch('batch_001');

    const callUrl = globalThis.fetch.mock.calls[0][0];
    expect(callUrl).toContain('/api/v1/risk-forecasting/notification-batches/batch_001/cancel');
  });

  it('38. Provider status constants match exact backend provider contracts (SIMULATED_SUCCESS and FAILED only)', () => {
    expect(WORKFLOW_PROVIDER_STATUS.SIMULATED_SUCCESS).toBe('SIMULATED_SUCCESS');
    expect(WORKFLOW_PROVIDER_STATUS.FAILED).toBe('FAILED');
    expect(WORKFLOW_PROVIDER_STATUS.SIMULATED_FAILED).toBeUndefined();
    expect(WORKFLOW_DELIVERY_STATUS.SUCCEEDED).toBe('SUCCEEDED');
    expect(WORKFLOW_DELIVERY_STATUS.FAILED).toBe('FAILED');
  });

  it('Contract Test: Successful mock delivery preserves status SUCCEEDED and provider_reference', async () => {
    const successDeliveryFixture = {
      delivery_id: 'del_001',
      batch_id: 'batch_001',
      advisory_id: 'adv_001',
      forecast_id: 'fdr_001',
      recipient_id: 'farm_001',
      resolved_message: 'FMD caution',
      status: 'SUCCEEDED',
      attempt_count: 1,
      provider_reference: 'mock_ref_a1b2c3d4',
      last_error: null,
      created_at: '2026-08-22T10:00:00Z',
      updated_at: '2026-08-22T10:00:01Z',
      version: 2,
    };
    mockFetchJsonResponse({ total_count: 1, limit: 50, offset: 0, deliveries: [successDeliveryFixture] });

    const res = await listNotificationDeliveries('batch_001');
    const item = res.deliveries[0];
    expect(item.status).toBe('SUCCEEDED');
    expect(item.status).not.toBe('DELIVERED');
    expect(item.provider_reference).toBe('mock_ref_a1b2c3d4');
    expect(item.last_error).toBeNull();
  });

  it('Contract Test: Failed mock delivery preserves status FAILED and controlled error message without invented status', async () => {
    const failureDeliveryFixture = {
      delivery_id: 'del_002',
      batch_id: 'batch_001',
      advisory_id: 'adv_001',
      forecast_id: 'fdr_001',
      recipient_id: 'farm_failed_99',
      resolved_message: 'FMD caution',
      status: 'FAILED',
      attempt_count: 1,
      provider_reference: null,
      last_error: 'MOCK_DELIVERY_FAILURE: Mock provider simulated delivery failure for recipient farm_failed_99',
      created_at: '2026-08-22T10:00:00Z',
      updated_at: '2026-08-22T10:00:01Z',
      version: 2,
    };
    mockFetchJsonResponse({ total_count: 1, limit: 50, offset: 0, deliveries: [failureDeliveryFixture] });

    const res = await listNotificationDeliveries('batch_001');
    const item = res.deliveries[0];
    expect(item.status).toBe('FAILED');
    expect(item.status).not.toBe('SUCCEEDED');
    expect(item.status).not.toBe('DELIVERED');
    expect(item.last_error).toContain('MOCK_DELIVERY_FAILURE');
  });

  it('Contract Test: Provider exception preserves status FAILED and PROVIDER_EXCEPTION last_error', async () => {
    const exceptionDeliveryFixture = {
      delivery_id: 'del_003',
      batch_id: 'batch_001',
      advisory_id: 'adv_001',
      forecast_id: 'fdr_001',
      recipient_id: 'farm_exc_88',
      resolved_message: 'FMD caution',
      status: 'FAILED',
      attempt_count: 1,
      provider_reference: null,
      last_error: 'PROVIDER_EXCEPTION: Mock notification provider execution failed.',
      created_at: '2026-08-22T10:00:00Z',
      updated_at: '2026-08-22T10:00:01Z',
      version: 2,
    };
    mockFetchJsonResponse({ total_count: 1, limit: 50, offset: 0, deliveries: [exceptionDeliveryFixture] });

    const res = await listNotificationDeliveries('batch_001');
    const item = res.deliveries[0];
    expect(item.status).toBe('FAILED');
    expect(item.last_error).toContain('PROVIDER_EXCEPTION');
  });

  it('39. Ensures no arbitrary-message send helper is exported from API module', async () => {
    const exports = await import('./riskForecastingWorkflowApi');
    expect(exports.sendMessage).toBeUndefined();
    expect(exports.sendSms).toBeUndefined();
    expect(exports.sendEmail).toBeUndefined();
  });

  // ─── F. SAFETY ───────────────────────────────────────────────────────────

  it('40. Executes zero real network calls when mocked', async () => {
    mockFetchJsonResponse({ status: 'ok' });
    await getForecastRecord('fdr_001');
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it('41. Does not perform automatic retries on write operations', async () => {
    mockFetchJsonResponse({ detail: 'Server Error' }, 500);
    try {
      await createForecastRecord({ disease: 'FMD' });
    } catch (_) {
      // Expected exception
    }
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it('42. Does not log request body or advisory content to console', async () => {
    const spyLog = vi.spyOn(console, 'log');
    const spyError = vi.spyOn(console, 'error');

    mockFetchJsonResponse({ advisory_id: 'adv_001' });
    await createAdvisoryDraft({ vet_custom_note: 'PRIVATE_NOTE' });

    expect(spyLog).not.toHaveBeenCalledWith(expect.stringContaining('PRIVATE_NOTE'));
    expect(spyError).not.toHaveBeenCalledWith(expect.stringContaining('PRIVATE_NOTE'));
  });
});
