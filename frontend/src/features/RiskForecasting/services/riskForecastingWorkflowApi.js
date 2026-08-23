/**
 * Risk Forecasting Workflow API Client.
 *
 * Dedicated frontend API service boundary for the Risk Forecasting workflow endpoints:
 * - Forecast Decision Records (/records)
 * - Assigned Recipients (/recipients)
 * - Veterinary Advisories (/advisories)
 * - Notification Batches & Simulated Deliveries (/notification-batches)
 *
 * Architectural & Delivery Safety Invariants:
 * 1. Base URL uses VITE_API_URL if configured, targeting /api/v1/risk-forecasting/...
 * 2. Strict ID path-encoding using encodeURIComponent to prevent route injection.
 * 3. Safe query parameter serialization: omits null/undefined/empty string, retains numeric 0 and boolean false.
 * 4. Single-pass response body consumption with normalized FastAPI error messages.
 * 5. Supports AbortSignal and Idempotency-Key headers where applicable.
 * 6. Preserves backend status enum REVIEW_READY (not READY_FOR_REVIEW) and provider_status SIMULATED_SUCCESS / FAILED.
 * 7. Mock notification dispatch is simulated; no external network calls or real farmer messages occur.
 */

const API_BASE = import.meta.env?.VITE_API_URL || '';

/**
 * Custom Error class for Risk Forecasting Workflow API failures.
 */
export class RiskForecastingWorkflowApiError extends Error {
  constructor({ message, status = null, endpoint = '', detail = null, cause = null }) {
    super(message);
    this.name = 'RiskForecastingWorkflowApiError';
    this.status = status;
    this.endpoint = endpoint;
    this.detail = detail;
    if (cause) {
      this.cause = cause;
    }
  }
}

/**
 * Authoritative NotificationDelivery status enums as defined by backend contracts.
 */
export const WORKFLOW_DELIVERY_STATUS = Object.freeze({
  SUCCEEDED: 'SUCCEEDED',
  FAILED: 'FAILED',
  PENDING: 'PENDING',
  PROCESSING: 'PROCESSING',
  CANCELLED: 'CANCELLED',
});

/**
 * ProviderDeliveryResult provider_status values returned by MockNotificationProvider.
 * Note: SIMULATED_SUCCESS represents a simulated delivery output; no real farmer receipt occurs.
 * FAILED represents a controlled simulated provider failure.
 */
export const WORKFLOW_PROVIDER_STATUS = Object.freeze({
  SIMULATED_SUCCESS: 'SIMULATED_SUCCESS',
  FAILED: 'FAILED',
});

/**
 * Helper to encode path parameter IDs and prevent path traversal / blank IDs.
 * @param {string} id
 * @param {string} paramName
 * @returns {string}
 */
function encodePathId(id, paramName = 'id') {
  if (id === undefined || id === null || String(id).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: `Invalid identifier: ${paramName} cannot be empty.`,
      endpoint: '',
    });
  }
  return encodeURIComponent(String(id).trim());
}

/**
 * Helper to construct query strings cleanly.
 * Omits undefined, null, and empty string parameters while retaining 0 and false.
 * @param {object} params
 * @returns {string}
 */
function buildQueryString(params = {}) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    searchParams.append(key, String(value));
  }
  const str = searchParams.toString();
  return str ? `?${str}` : '';
}

/**
 * Internal single-pass HTTP fetch wrapper for workflow API endpoints.
 * @param {string} path - Effective path starting with /api/v1/risk-forecasting
 * @param {object} options - Fetch options including method, headers, body, signal, idempotencyKey
 * @returns {Promise<any>}
 */
async function requestWorkflowApi(path, options = {}) {
  const fullUrl = `${API_BASE}${path}`;
  const headers = { ...options.headers };

  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  if (options.idempotencyKey) {
    headers['Idempotency-Key'] = options.idempotencyKey;
  }

  const fetchOptions = {
    method: options.method || 'GET',
    headers,
    signal: options.signal,
  };

  if (options.body) {
    fetchOptions.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
  }

  let res;
  try {
    res = await fetch(fullUrl, fetchOptions);
  } catch (err) {
    throw new RiskForecastingWorkflowApiError({
      message: `Network request failed: ${err.message || 'Unable to connect to backend'}`,
      status: null,
      endpoint: path,
      detail: null,
      cause: err,
    });
  }

  let text = '';
  try {
    text = await res.text();
  } catch (_) {
    // Single-pass text reading fallback
  }

  let detail = null;
  let parsed = null;
  if (text && text.trim() !== '') {
    try {
      parsed = JSON.parse(text);
      detail = parsed?.detail ?? parsed;
    } catch (_) {
      // Non-JSON or raw text
    }
  }

  if (!res.ok) {
    let detailMsg = '';
    if (typeof detail === 'string') {
      detailMsg = detail;
    } else if (Array.isArray(detail)) {
      detailMsg = detail.map((d) => (typeof d === 'string' ? d : d?.msg || JSON.stringify(d))).join('; ');
    } else if (detail && typeof detail === 'object') {
      detailMsg = detail.message || JSON.stringify(detail);
    } else if (text && text.trim() !== '') {
      detailMsg = text.trim();
    }

    const message = detailMsg
      ? `API Error ${res.status}: ${detailMsg}`
      : `API Error ${res.status}`;

    throw new RiskForecastingWorkflowApiError({
      message,
      status: res.status,
      endpoint: path,
      detail,
    });
  }

  if (!text || text.trim() === '') {
    return null;
  }

  return parsed !== null ? parsed : JSON.parse(text);
}

// ─── FORECAST RECORD METHODS ───────────────────────────────────────────────

/**
 * Creates and persists an immutable Forecast Decision Record.
 * POST /api/v1/risk-forecasting/records
 */
export async function createForecastRecord(payload, options = {}) {
  const idempotencyKey = options.idempotencyKey || payload?.idempotency_key || payload?.idempotencyKey;
  return requestWorkflowApi('/api/v1/risk-forecasting/records', {
    method: 'POST',
    body: payload,
    signal: options.signal,
    idempotencyKey,
  });
}

/**
 * Retrieves a Forecast Decision Record by unique forecast_id.
 * GET /api/v1/risk-forecasting/records/{forecast_id}
 */
export async function getForecastRecord(forecastId, options = {}) {
  const safeId = encodePathId(forecastId, 'forecastId');
  return requestWorkflowApi(`/api/v1/risk-forecasting/records/${safeId}`, {
    method: 'GET',
    signal: options.signal,
  });
}

/**
 * Lists Forecast Decision Records with query filtering and pagination.
 * GET /api/v1/risk-forecasting/records
 */
export async function listForecastRecords(filters = {}, options = {}) {
  const queryParams = {
    disease: filters.disease,
    district: filters.district,
    target_year: filters.target_year ?? filters.targetYear,
    target_month: filters.target_month ?? filters.targetMonth,
    status: filters.status,
    limit: filters.limit,
    offset: filters.offset,
  };
  const queryString = buildQueryString(queryParams);
  return requestWorkflowApi(`/api/v1/risk-forecasting/records${queryString}`, {
    method: 'GET',
    signal: options.signal,
  });
}

/**
 * Lists authoritative 25 Sri Lankan administrative districts and month names.
 * GET /api/v1/risk-forecasting/districts
 */
export async function listForecastDistricts(options = {}) {
  return requestWorkflowApi('/api/v1/risk-forecasting/districts', {
    method: 'GET',
    signal: options.signal,
  });
}

// ─── RECIPIENT QUERY METHOD ────────────────────────────────────────────────

/**
 * Lists non-sensitive farm recipients assigned to a Veterinary Officer.
 * GET /api/v1/risk-forecasting/recipients
 */
export async function listAssignedRecipients({ vetId, district, signal } = {}) {
  if (vetId === undefined || vetId === null || String(vetId).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: 'vetId is required and cannot be empty.',
      endpoint: '/api/v1/risk-forecasting/recipients',
    });
  }

  const queryString = buildQueryString({
    vet_id: String(vetId).trim(),
    district: district ? String(district).trim() : undefined,
  });

  return requestWorkflowApi(`/api/v1/risk-forecasting/recipients${queryString}`, {
    method: 'GET',
    signal,
  });
}

// ─── ADVISORY METHODS ──────────────────────────────────────────────────────

/**
 * Creates a new Farmer Advisory Record draft.
 * POST /api/v1/risk-forecasting/advisories
 */
export async function createAdvisoryDraft(payload, options = {}) {
  const idempotencyKey = options.idempotencyKey || payload?.idempotency_key || payload?.idempotencyKey;
  return requestWorkflowApi('/api/v1/risk-forecasting/advisories', {
    method: 'POST',
    body: payload,
    signal: options.signal,
    idempotencyKey,
  });
}

/**
 * Previews advisory recipient resolution and message rendering.
 * POST /api/v1/risk-forecasting/advisories/preview
 * Accepts either { advisoryId } OR { draft }, but not both and not neither.
 */
export async function previewAdvisory({ advisoryId, draft, signal } = {}) {
  if (advisoryId && draft) {
    throw new RiskForecastingWorkflowApiError({
      message: 'Ambiguous preview request: provide either advisoryId or draft, not both.',
      endpoint: '/api/v1/risk-forecasting/advisories/preview',
    });
  }

  if (!advisoryId && !draft) {
    throw new RiskForecastingWorkflowApiError({
      message: 'Preview request requires either advisoryId or draft.',
      endpoint: '/api/v1/risk-forecasting/advisories/preview',
    });
  }

  if (advisoryId) {
    const queryString = buildQueryString({ advisory_id: String(advisoryId).trim() });
    return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/preview${queryString}`, {
      method: 'POST',
      signal,
    });
  }

  return requestWorkflowApi('/api/v1/risk-forecasting/advisories/preview', {
    method: 'POST',
    body: draft,
    signal,
  });
}

/**
 * Retrieves a Farmer Advisory Record by unique advisory_id.
 * GET /api/v1/risk-forecasting/advisories/{advisory_id}
 */
export async function getAdvisory(advisoryId, options = {}) {
  const safeId = encodePathId(advisoryId, 'advisoryId');
  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/${safeId}`, {
    method: 'GET',
    signal: options.signal,
  });
}

/**
 * Lists Farmer Advisory Records matching query filters.
 * GET /api/v1/risk-forecasting/advisories
 */
export async function listAdvisories(filters = {}, options = {}) {
  const queryParams = {
    forecast_id: filters.forecast_id ?? filters.forecastId,
    disease: filters.disease,
    district: filters.district,
    status: filters.status,
    limit: filters.limit,
    offset: filters.offset,
  };
  const queryString = buildQueryString(queryParams);
  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories${queryString}`, {
    method: 'GET',
    signal: options.signal,
  });
}

/**
 * Updates editable advisory draft content.
 * PUT /api/v1/risk-forecasting/advisories/{advisory_id}
 */
export async function updateAdvisoryDraft(advisoryId, payload, options = {}) {
  const safeId = encodePathId(advisoryId, 'advisoryId');
  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/${safeId}`, {
    method: 'PUT',
    body: payload,
    signal: options.signal,
  });
}

/**
 * Transitions advisory status from DRAFT -> REVIEW_READY.
 * POST /api/v1/risk-forecasting/advisories/{advisory_id}/ready-for-review?version={version}
 */
export async function markAdvisoryReadyForReview(advisoryId, version, options = {}) {
  const safeId = encodePathId(advisoryId, 'advisoryId');
  const ver = typeof version === 'object' && version !== null ? version.version : version;
  const signal = typeof version === 'object' && version !== null ? version.signal : options.signal;

  if (ver === undefined || ver === null || isNaN(Number(ver))) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer.',
      endpoint: `/api/v1/risk-forecasting/advisories/${safeId}/ready-for-review`,
    });
  }

  const queryString = buildQueryString({ version: ver });
  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/${safeId}/ready-for-review${queryString}`, {
    method: 'POST',
    signal,
  });
}

/**
 * Transitions advisory status to APPROVED.
 * POST /api/v1/risk-forecasting/advisories/{advisory_id}/approve?version={version}&approved_by={approvedBy}
 */
export async function approveAdvisory(advisoryId, args = {}, options = {}) {
  const safeId = encodePathId(advisoryId, 'advisoryId');

  let version;
  let approvedBy;
  let signal;

  if (typeof args === 'number' || typeof args === 'string') {
    version = args;
    approvedBy = options.approvedBy || options.approved_by || 'vet_officer_01';
    signal = options.signal;
  } else if (args && typeof args === 'object') {
    version = args.version;
    approvedBy = args.approvedBy || args.approved_by || options.approvedBy || options.approved_by || 'vet_officer_01';
    signal = args.signal || options.signal;
  }

  if (version === undefined || version === null || isNaN(Number(version))) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer.',
      endpoint: `/api/v1/risk-forecasting/advisories/${safeId}/approve`,
    });
  }

  const queryString = buildQueryString({
    version,
    approved_by: approvedBy,
  });

  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/${safeId}/approve${queryString}`, {
    method: 'POST',
    signal,
  });
}

/**
 * Transitions advisory status to CANCELLED.
 * POST /api/v1/risk-forecasting/advisories/{advisory_id}/cancel?version={version}
 */
export async function cancelAdvisory(advisoryId, version, options = {}) {
  const safeId = encodePathId(advisoryId, 'advisoryId');
  const ver = typeof version === 'object' && version !== null ? version.version : version;
  const signal = typeof version === 'object' && version !== null ? version.signal : options.signal;

  if (ver === undefined || ver === null || isNaN(Number(ver))) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer.',
      endpoint: `/api/v1/risk-forecasting/advisories/${safeId}/cancel`,
    });
  }

  const queryString = buildQueryString({ version: ver });
  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/${safeId}/cancel${queryString}`, {
    method: 'POST',
    signal,
  });
}

// ─── NOTIFICATION BATCH METHODS ────────────────────────────────────────────

/**
 * Enqueues an APPROVED advisory into the notification outbox.
 * POST /api/v1/risk-forecasting/advisories/{advisory_id}/notification-batches
 */
export async function enqueueNotificationBatch(advisoryId, payload = {}, options = {}) {
  const safeId = encodePathId(advisoryId, 'advisoryId');
  const idempotencyKey = options.idempotencyKey || payload?.idempotency_key || payload?.idempotencyKey;
  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/${safeId}/notification-batches`, {
    method: 'POST',
    body: payload && Object.keys(payload).length > 0 ? payload : undefined,
    signal: options.signal,
    idempotencyKey,
  });
}

/**
 * Retrieves notification batch summary by batch ID.
 * GET /api/v1/risk-forecasting/notification-batches/{batch_id}
 */
export async function getNotificationBatch(batchId, options = {}) {
  const safeId = encodePathId(batchId, 'batchId');
  return requestWorkflowApi(`/api/v1/risk-forecasting/notification-batches/${safeId}`, {
    method: 'GET',
    signal: options.signal,
  });
}

/**
 * Lists notification batches with query filters.
 * GET /api/v1/risk-forecasting/notification-batches
 */
export async function listNotificationBatches(filters = {}, options = {}) {
  const queryParams = {
    advisory_id: filters.advisory_id ?? filters.advisoryId,
    forecast_id: filters.forecast_id ?? filters.forecastId,
    status: filters.status,
    limit: filters.limit,
    offset: filters.offset,
  };
  const queryString = buildQueryString(queryParams);
  return requestWorkflowApi(`/api/v1/risk-forecasting/notification-batches${queryString}`, {
    method: 'GET',
    signal: options.signal,
  });
}

/**
 * Lists per-recipient delivery items for a specific notification batch.
 * GET /api/v1/risk-forecasting/notification-batches/{batch_id}/deliveries
 */
export async function listNotificationDeliveries(batchId, filters = {}, options = {}) {
  const safeId = encodePathId(batchId, 'batchId');

  let actualFilters = filters;
  let actualOptions = options;
  if (filters && (filters.signal || filters.idempotencyKey)) {
    actualOptions = filters;
    actualFilters = {};
  }

  const queryParams = {
    status: actualFilters.status,
    limit: actualFilters.limit,
    offset: actualFilters.offset,
  };
  const queryString = buildQueryString(queryParams);
  return requestWorkflowApi(`/api/v1/risk-forecasting/notification-batches/${safeId}/deliveries${queryString}`, {
    method: 'GET',
    signal: actualOptions.signal,
  });
}

/**
 * Explicitly dispatches pending delivery items in a batch through mock provider.
 * POST /api/v1/risk-forecasting/notification-batches/{batch_id}/dispatch
 */
export async function dispatchNotificationBatch(batchId, options = {}) {
  const safeId = encodePathId(batchId, 'batchId');
  return requestWorkflowApi(`/api/v1/risk-forecasting/notification-batches/${safeId}/dispatch`, {
    method: 'POST',
    signal: options.signal,
  });
}

/**
 * Retries failed delivery items in a batch.
 * POST /api/v1/risk-forecasting/notification-batches/{batch_id}/retry-failed
 */
export async function retryFailedNotificationDeliveries(batchId, options = {}) {
  const safeId = encodePathId(batchId, 'batchId');
  return requestWorkflowApi(`/api/v1/risk-forecasting/notification-batches/${safeId}/retry-failed`, {
    method: 'POST',
    signal: options.signal,
  });
}

/**
 * Cancels a safe QUEUED notification batch prior to any delivery attempts.
 * POST /api/v1/risk-forecasting/notification-batches/{batch_id}/cancel
 */
export async function cancelNotificationBatch(batchId, options = {}) {
  const safeId = encodePathId(batchId, 'batchId');
  return requestWorkflowApi(`/api/v1/risk-forecasting/notification-batches/${safeId}/cancel`, {
    method: 'POST',
    signal: options.signal,
  });
}
