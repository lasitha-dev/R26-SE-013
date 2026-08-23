import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  RiskForecastingWorkflowApiError,
  WORKFLOW_DELIVERY_STATUS,
  WORKFLOW_PROVIDER_STATUS,
  FOLLOW_UP_STATUS,
  OPERATIONAL_PRIORITY,
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
  issueFollowUp,
  listFollowUps,
  getFollowUp,
  acknowledgeFollowUp,
  startFollowUpAction,
  completeFollowUp,
  cancelFollowUp,
  escalateFollowUp,
  linkExternalResourceReference,
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

  // ─── G. PHASE 6B-2A FORECAST FOLLOW-UP CONTRACT TESTS ───────────────────

  describe('Phase 6B-2A Forecast Follow-Up API Client Methods', () => {
    const validDaphActor = { userId: 'daph_hq_01', role: 'DAPH_OFFICIAL' };
    const validVetActor = { actor_id: 'vet_officer_01', actor_role: 'VETERINARY_OFFICER' };
    const sampleRecord = {
      follow_up_id: 'ffu_001',
      forecast_id: 'fdr_001',
      district: 'Anuradhapura',
      disease: 'FMD',
      target_year: 2026,
      target_month: 9,
      forecast_risk_level: 'HIGH',
      operational_priority: 'CRITICAL',
      instruction_summary: 'Deploy emergency ring vaccination',
      issued_by_daph_id: 'daph_hq_01',
      assigned_vet_id: 'vet_officer_01',
      status: 'ISSUED',
      version: 1,
      issued_at: '2026-08-23T10:00:00Z',
      created_at: '2026-08-23T10:00:00Z',
      updated_at: '2026-08-23T10:00:00Z',
    };

    it('validates frozen FOLLOW_UP_STATUS and OPERATIONAL_PRIORITY constants', () => {
      expect(FOLLOW_UP_STATUS.ISSUED).toBe('ISSUED');
      expect(FOLLOW_UP_STATUS.ACKNOWLEDGED).toBe('ACKNOWLEDGED');
      expect(FOLLOW_UP_STATUS.ACTION_IN_PROGRESS).toBe('ACTION_IN_PROGRESS');
      expect(FOLLOW_UP_STATUS.COMPLETED).toBe('COMPLETED');
      expect(FOLLOW_UP_STATUS.CANCELLED).toBe('CANCELLED');
      expect(FOLLOW_UP_STATUS.ESCALATED).toBe('ESCALATED');
      expect(Object.isFrozen(FOLLOW_UP_STATUS)).toBe(true);

      expect(OPERATIONAL_PRIORITY.HIGH).toBe('HIGH');
      expect(OPERATIONAL_PRIORITY.MEDIUM).toBe('MEDIUM');
      expect(OPERATIONAL_PRIORITY.LOW).toBe('LOW');
      expect(OPERATIONAL_PRIORITY.CRITICAL).toBeUndefined();
      expect(Object.keys(OPERATIONAL_PRIORITY)).toEqual(['HIGH', 'MEDIUM', 'LOW']);
      expect(Object.isFrozen(OPERATIONAL_PRIORITY)).toBe(true);
    });

    it('issueFollowUp: sends POST to /api/v1/risk-forecasting/follow-ups with headers and body omitting identity fields', async () => {
      mockFetchJsonResponse(sampleRecord, 201);

      const res = await issueFollowUp(
        {
          forecast_id: 'fdr_001',
          assigned_vet_id: 'vet_officer_01',
          instruction_summary: 'Deploy ring vaccination',
          // Client might attempt to pass identity in payload; test that client strips it
          issued_by_daph_id: 'SPOOFED_DAPH',
          actor_id: 'SPOOFED_ACTOR',
        },
        {
          actorContext: validDaphActor,
          idempotencyKey: 'idem_key_123',
        }
      );

      expect(res).toEqual(sampleRecord);
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);

      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups');
      expect(opts.method).toBe('POST');
      expect(opts.headers['X-Actor-ID']).toBe('daph_hq_01');
      expect(opts.headers['X-Actor-Role']).toBe('DAPH_OFFICIAL');
      expect(opts.headers['Idempotency-Key']).toBe('idem_key_123');

      const parsedBody = JSON.parse(opts.body);
      expect(parsedBody.forecast_id).toBe('fdr_001');
      expect(parsedBody.assigned_vet_id).toBe('vet_officer_01');
      expect(parsedBody.instruction_summary).toBe('Deploy ring vaccination');
      expect(parsedBody.idempotency_key).toBe('idem_key_123');
      // STRICT SECURITY VERIFICATION: No actor identity in JSON body
      expect(parsedBody.issued_by_daph_id).toBeUndefined();
      expect(parsedBody.actor_id).toBeUndefined();
    });

    it('issueFollowUp: handles camelCase idempotencyKey mapping and rejects conflicting idempotency keys', async () => {
      // 1. camelCase in payload maps to snake_case idempotency_key in body and header, stripping camelCase from body
      mockFetchJsonResponse(sampleRecord, 201);
      await issueFollowUp(
        {
          forecast_id: 'fdr_001',
          assigned_vet_id: 'vet_officer_01',
          instruction_summary: 'Ring vaccination',
          idempotencyKey: 'idem_camel_123',
        },
        { actorContext: validDaphActor }
      );
      const [, opts] = globalThis.fetch.mock.calls[0];
      const body = JSON.parse(opts.body);
      expect(body.idempotency_key).toBe('idem_camel_123');
      expect(body.idempotencyKey).toBeUndefined();
      expect(opts.headers['Idempotency-Key']).toBe('idem_camel_123');

      // 2. Conflicting keys in options and payload throws client-side error before fetch
      await expect(
        issueFollowUp(
          {
            forecast_id: 'fdr_001',
            assigned_vet_id: 'vet_officer_01',
            instruction_summary: 'Ring vaccination',
            idempotency_key: 'payload_key',
          },
          {
            actorContext: validDaphActor,
            idempotencyKey: 'option_key',
          }
        )
      ).rejects.toThrow('Conflicting idempotency keys provided in options and payload.');
    });

    it('issueFollowUp: fails client-side when actor context or required payload fields are missing', async () => {
      // Missing actorContext
      await expect(
        issueFollowUp({
          forecast_id: 'fdr_001',
          assigned_vet_id: 'vet_01',
          instruction_summary: 'Summary',
        })
      ).rejects.toThrow(RiskForecastingWorkflowApiError);

      // Blank actorId
      await expect(
        issueFollowUp(
          {
            forecast_id: 'fdr_001',
            assigned_vet_id: 'vet_01',
            instruction_summary: 'Summary',
          },
          { actorContext: { userId: '  ', role: 'DAPH_OFFICIAL' } }
        )
      ).rejects.toThrow('Actor identity (actorId / userId) cannot be missing or blank.');

      // Blank actorRole
      await expect(
        issueFollowUp(
          {
            forecast_id: 'fdr_001',
            assigned_vet_id: 'vet_01',
            instruction_summary: 'Summary',
          },
          { actorContext: { userId: 'daph_01', role: '  ' } }
        )
      ).rejects.toThrow('Actor role (actorRole / role) cannot be missing or blank.');

      // Missing forecast_id
      await expect(
        issueFollowUp(
          { assigned_vet_id: 'vet_01', instruction_summary: 'Summary' },
          { actorContext: validDaphActor }
        )
      ).rejects.toThrow('forecast_id is required');

      expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('listFollowUps: sends GET to /api/v1/risk-forecasting/follow-ups with serialized query string and actor headers', async () => {
      mockFetchJsonResponse({ items: [sampleRecord], total_count: 1, limit: 50, offset: 0 });

      const res = await listFollowUps(
        {
          forecast_id: 'fdr_001',
          district: 'Anuradhapura',
          disease: 'FMD',
          status: 'ISSUED',
          target_year: 2026,
          limit: 10,
          offset: 0,
        },
        { actorContext: validDaphActor }
      );

      expect(res.total_count).toBe(1);
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups?');
      expect(url).toContain('forecast_id=fdr_001');
      expect(url).toContain('district=Anuradhapura');
      expect(url).toContain('disease=FMD');
      expect(url).toContain('status=ISSUED');
      expect(url).toContain('target_year=2026');
      expect(url).toContain('limit=10');
      expect(opts.method).toBe('GET');
      expect(opts.headers['X-Actor-ID']).toBe('daph_hq_01');
      expect(opts.headers['X-Actor-Role']).toBe('DAPH_OFFICIAL');
    });

    it('getFollowUp: retrieves follow-up by path ID with path encoding and actor context', async () => {
      mockFetchJsonResponse(sampleRecord);

      const res = await getFollowUp('ffu/001#test', { actorContext: validVetActor });

      expect(res.follow_up_id).toBe('ffu_001');
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups/ffu%2F001%23test');
      expect(opts.headers['X-Actor-ID']).toBe('vet_officer_01');
      expect(opts.headers['X-Actor-Role']).toBe('VETERINARY_OFFICER');
    });

    it('getFollowUp: throws RiskForecastingWorkflowApiError on empty ID', async () => {
      await expect(getFollowUp('')).rejects.toThrow('followUpId cannot be empty');
      expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('acknowledgeFollowUp: sends POST to /acknowledge with version body and actor headers omitting body identity', async () => {
      const ackRecord = { ...sampleRecord, status: 'ACKNOWLEDGED', version: 2 };
      mockFetchJsonResponse(ackRecord);

      const res = await acknowledgeFollowUp('ffu_001', 1, { actorContext: validVetActor });

      expect(res.status).toBe('ACKNOWLEDGED');
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups/ffu_001/acknowledge');
      expect(opts.method).toBe('POST');
      expect(opts.headers['X-Actor-ID']).toBe('vet_officer_01');
      expect(opts.headers['X-Actor-Role']).toBe('VETERINARY_OFFICER');

      const body = JSON.parse(opts.body);
      expect(body.version).toBe(1);
      expect(body.actor_id).toBeUndefined();
    });

    it('acknowledgeFollowUp: fails client-side when version is invalid or actorContext is missing', async () => {
      await expect(acknowledgeFollowUp('ffu_001', 0, { actorContext: validVetActor })).rejects.toThrow(
        'version is required and must be an integer >= 1.'
      );

      await expect(acknowledgeFollowUp('ffu_001', 1)).rejects.toThrow('Actor context is required for this operation.');

      expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('startFollowUpAction: transitions status to ACTION_IN_PROGRESS', async () => {
      const startRecord = { ...sampleRecord, status: 'ACTION_IN_PROGRESS', version: 3 };
      mockFetchJsonResponse(startRecord);

      const res = await startFollowUpAction('ffu_001', { version: 2, actorContext: validVetActor });

      expect(res.status).toBe('ACTION_IN_PROGRESS');
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups/ffu_001/start');
      expect(opts.headers['X-Actor-ID']).toBe('vet_officer_01');
      expect(JSON.parse(opts.body)).toEqual({ version: 2 });
    });

    it('completeFollowUp: transitions status to COMPLETED', async () => {
      const completeRecord = { ...sampleRecord, status: 'COMPLETED', version: 4 };
      mockFetchJsonResponse(completeRecord);

      const res = await completeFollowUp('ffu_001', { version: 3, actorContext: validVetActor });

      expect(res.status).toBe('COMPLETED');
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups/ffu_001/complete');
      expect(opts.headers['X-Actor-ID']).toBe('vet_officer_01');
      expect(JSON.parse(opts.body)).toEqual({ version: 3 });
    });

    it('cancelFollowUp: transitions status to CANCELLED with reason', async () => {
      const cancelRecord = { ...sampleRecord, status: 'CANCELLED', version: 2, cancellation_reason: 'Resolved by DAPH' };
      mockFetchJsonResponse(cancelRecord);

      const res = await cancelFollowUp('ffu_001', { version: 1, reason: 'Resolved by DAPH', actorContext: validDaphActor });

      expect(res.status).toBe('CANCELLED');
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups/ffu_001/cancel');
      expect(opts.headers['X-Actor-ID']).toBe('daph_hq_01');
      expect(JSON.parse(opts.body)).toEqual({ version: 1, reason: 'Resolved by DAPH' });
    });

    it('escalateFollowUp: requires explicit non-empty reason and sends POST to /escalate', async () => {
      const escRecord = { ...sampleRecord, status: 'ESCALATED', version: 3, escalation_reason: 'Outbreak expanding rapidly' };
      mockFetchJsonResponse(escRecord);

      const res = await escalateFollowUp('ffu_001', { version: 2, reason: 'Outbreak expanding rapidly', actorContext: validVetActor });

      expect(res.status).toBe('ESCALATED');
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups/ffu_001/escalate');
      expect(opts.headers['X-Actor-ID']).toBe('vet_officer_01');
      expect(JSON.parse(opts.body)).toEqual({
        version: 2,
        reason: 'Outbreak expanding rapidly',
      });
    });

    it('escalateFollowUp: rejects empty or blank escalation reason client-side', async () => {
      await expect(
        escalateFollowUp('ffu_001', { version: 2, reason: '   ', actorContext: validVetActor })
      ).rejects.toThrow('Reason is required for escalating a follow-up instruction.');

      expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('linkExternalResourceReference: links opaque resource ID without invented stock/inventory fields', async () => {
      const linkedRecord = { ...sampleRecord, external_resource_request_id: 'err_ref_999', version: 2 };
      mockFetchJsonResponse(linkedRecord);

      const res = await linkExternalResourceReference('ffu_001', {
        version: 1,
        externalResourceRequestId: 'err_ref_999',
        actorContext: validDaphActor,
      });

      expect(res.external_resource_request_id).toBe('err_ref_999');
      const [url, opts] = globalThis.fetch.mock.calls[0];
      expect(url).toContain('/api/v1/risk-forecasting/follow-ups/ffu_001/external-resource-reference');

      const body = JSON.parse(opts.body);
      expect(body).toEqual({ version: 1, external_resource_request_id: 'err_ref_999' });
      // PROVE NO INVENTED STOCK/VACCINE/LOGISTICS FIELDS
      expect(body.quantity).toBeUndefined();
      expect(body.stock).toBeUndefined();
      expect(body.warehouse).toBeUndefined();
      expect(body.vaccine_type).toBeUndefined();
    });

    it('linkExternalResourceReference: rejects empty external resource ID client-side', async () => {
      await expect(
        linkExternalResourceReference('ffu_001', { version: 1, externalResourceRequestId: '', actorContext: validDaphActor })
      ).rejects.toThrow('external_resource_request_id is required for linking resource reference.');

      expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('forwards AbortSignal across follow-up API client methods', async () => {
      mockFetchJsonResponse(sampleRecord);
      const controller = new AbortController();

      await getFollowUp('ffu_001', { actorContext: validVetActor, signal: controller.signal });

      const [, opts] = globalThis.fetch.mock.calls[0];
      expect(opts.signal).toBe(controller.signal);
    });

    it('normalizes HTTP 403 Forbidden authorization errors correctly', async () => {
      mockFetchJsonResponse({ detail: 'Only assigned Veterinary Officer may transition status.' }, 403);

      await expect(acknowledgeFollowUp('ffu_001', 1, { actorContext: validVetActor })).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(RiskForecastingWorkflowApiError);
        expect(err.status).toBe(403);
        expect(err.message).toContain('API Error 403: Only assigned Veterinary Officer may transition status.');
        return true;
      });
    });

    it('normalizes HTTP 404 Not Found errors correctly', async () => {
      mockFetchJsonResponse({ detail: "Follow-up record 'ffu_999' not found." }, 404);

      await expect(getFollowUp('ffu_999', { actorContext: validVetActor })).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(RiskForecastingWorkflowApiError);
        expect(err.status).toBe(404);
        expect(err.message).toContain("API Error 404: Follow-up record 'ffu_999' not found.");
        return true;
      });
    });

    it('normalizes HTTP 409 Optimistic Lock Conflict errors correctly', async () => {
      mockFetchJsonResponse(
        { detail: 'Optimistic lock conflict for follow-up record ffu_001: expected version 1, but current version is 2.' },
        409
      );

      await expect(acknowledgeFollowUp('ffu_001', 1, { actorContext: validVetActor })).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(RiskForecastingWorkflowApiError);
        expect(err.status).toBe(409);
        expect(err.message).toContain('Optimistic lock conflict');
        return true;
      });
    });

    it('normalizes HTTP 422 Validation Error array objects cleanly', async () => {
      mockFetchJsonResponse(
        {
          detail: [
            { loc: ['body', 'extra_field'], msg: 'Extra inputs are not permitted' },
          ],
        },
        422
      );

      await expect(
        issueFollowUp({ forecast_id: 'fdr_01', assigned_vet_id: 'vet_01', instruction_summary: 'Text' }, { actorContext: validDaphActor })
      ).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(RiskForecastingWorkflowApiError);
        expect(err.status).toBe(422);
        expect(err.message).toContain('Extra inputs are not permitted');
        return true;
      });
    });

    it('sanitizes raw network failures cleanly without technical leakage', async () => {
      globalThis.fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      await expect(getFollowUp('ffu_001', { actorContext: validVetActor })).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(RiskForecastingWorkflowApiError);
        expect(err.status).toBeNull();
        expect(err.message).toContain('Network request failed: Failed to fetch');
        return true;
      });
    });
  });
});
