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
 * Authoritative Follow-Up status enums as defined by backend contracts.
 */
export const FOLLOW_UP_STATUS = Object.freeze({
  ISSUED: 'ISSUED',
  ACKNOWLEDGED: 'ACKNOWLEDGED',
  ACTION_IN_PROGRESS: 'ACTION_IN_PROGRESS',
  COMPLETED: 'COMPLETED',
  CANCELLED: 'CANCELLED',
  ESCALATED: 'ESCALATED',
});

/**
 * Authoritative Operational Priority enums as defined by backend contracts.
 */
export const OPERATIONAL_PRIORITY = Object.freeze({
  HIGH: 'HIGH',
  MEDIUM: 'MEDIUM',
  LOW: 'LOW',
});

/**
 * Converts standalone viewer/actor context into Phase 6B-1 backend headers (X-Actor-ID, X-Actor-Role).
 * NOTE: Standalone X-Actor headers represent the request boundary; in production these will be replaced by verified JWT / shared IAM claims.
 *
 * @param {object|null} actorContext - Object containing user identity and role
 * @param {boolean} required - Whether actor identity is strictly required for the operation
 * @returns {object} Headers object containing X-Actor-ID and X-Actor-Role if provided
 */
function buildActorHeaders(actorContext = null, required = false) {
  if (!actorContext) {
    if (required) {
      throw new RiskForecastingWorkflowApiError({
        message: 'Actor context is required for this operation.',
        endpoint: '',
      });
    }
    return {};
  }

  const actorId = actorContext.actor_id || actorContext.actorId || actorContext.userId || actorContext.user_id;
  const actorRole = actorContext.actor_role || actorContext.actorRole || actorContext.role;

  if (required) {
    if (!actorId || String(actorId).trim() === '') {
      throw new RiskForecastingWorkflowApiError({
        message: 'Actor identity (actorId / userId) cannot be missing or blank.',
        endpoint: '',
      });
    }
    if (!actorRole || String(actorRole).trim() === '') {
      throw new RiskForecastingWorkflowApiError({
        message: 'Actor role (actorRole / role) cannot be missing or blank.',
        endpoint: '',
      });
    }
  }

  const headers = {};
  if (actorId && String(actorId).trim() !== '') {
    headers['X-Actor-ID'] = String(actorId).trim();
  }
  if (actorRole && String(actorRole).trim() !== '') {
    headers['X-Actor-Role'] = String(actorRole).trim();
  }

  return headers;
}

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
export async function createForecastRecord(payload = {}, options = {}) {
  const idempotencyKey = options.idempotencyKey || payload?.idempotency_key || payload?.idempotencyKey;

  const normalizedYear = payload.year ?? payload.target_year;
  const normalizedMonth = payload.month ?? payload.target_month;

  const body = {};

  if (payload.disease !== undefined) body.disease = payload.disease;
  if (payload.district !== undefined) body.district = payload.district;
  if (normalizedYear !== undefined) body.year = normalizedYear;
  if (normalizedMonth !== undefined) body.month = normalizedMonth;
  if (payload.model_variant !== undefined) body.model_variant = payload.model_variant;
  if (payload.trigger_type !== undefined) body.trigger_type = payload.trigger_type;
  if (payload.generated_by !== undefined) body.generated_by = payload.generated_by;

  const finalIdempotencyKey = payload.idempotency_key ?? payload.idempotencyKey;
  if (finalIdempotencyKey !== undefined) body.idempotency_key = finalIdempotencyKey;

  return requestWorkflowApi('/api/v1/risk-forecasting/records', {
    method: 'POST',
    body,
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

// ─── FORECAST FOLLOW-UP METHODS (Phase 6B-2A) ─────────────────────────────

/**
 * Issues a new DAPH operational follow-up instruction linked to an official forecast record.
 * POST /api/v1/risk-forecasting/follow-ups
 *
 * NOTE: Scientific snapshots and issuer identity are derived server-side.
 * Identity fields (issued_by_daph_id, actor_id) are strictly excluded from the request body.
 */
export async function issueFollowUp(payload = {}, options = {}) {
  if (!payload || typeof payload !== 'object') {
    throw new RiskForecastingWorkflowApiError({
      message: 'payload is required and must be an object.',
      endpoint: '/api/v1/risk-forecasting/follow-ups',
    });
  }

  const forecastId = payload.forecast_id ?? payload.forecastId;
  const assignedVetId = payload.assigned_vet_id ?? payload.assignedVetId;
  const instructionSummary = payload.instruction_summary ?? payload.instructionSummary;
  const bodyIdempotencyKey = payload.idempotency_key ?? payload.idempotencyKey;
  const optionIdempotencyKey = options.idempotencyKey;
  const actorContext = options.actorContext || options.actor || payload.actorContext || payload.actor;

  if (
    optionIdempotencyKey &&
    bodyIdempotencyKey &&
    String(optionIdempotencyKey).trim() !== String(bodyIdempotencyKey).trim()
  ) {
    throw new RiskForecastingWorkflowApiError({
      message: 'Conflicting idempotency keys provided in options and payload.',
      endpoint: '/api/v1/risk-forecasting/follow-ups',
    });
  }

  const idempotencyKey = optionIdempotencyKey || bodyIdempotencyKey;

  if (!forecastId || String(forecastId).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: 'forecast_id is required for issuing a follow-up.',
      endpoint: '/api/v1/risk-forecasting/follow-ups',
    });
  }

  if (!assignedVetId || String(assignedVetId).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: 'assigned_vet_id is required for issuing a follow-up.',
      endpoint: '/api/v1/risk-forecasting/follow-ups',
    });
  }

  if (!instructionSummary || String(instructionSummary).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: 'instruction_summary is required for issuing a follow-up.',
      endpoint: '/api/v1/risk-forecasting/follow-ups',
    });
  }

  const headers = buildActorHeaders(actorContext, true);

  // Construct body payload ensuring zero identity fields (issued_by_daph_id, actor_id) are serialized
  // and camelCase idempotencyKey is not leaked into JSON
  const body = {
    forecast_id: String(forecastId).trim(),
    assigned_vet_id: String(assignedVetId).trim(),
    instruction_summary: String(instructionSummary).trim(),
  };

  if (idempotencyKey) {
    body.idempotency_key = String(idempotencyKey).trim();
  }

  return requestWorkflowApi('/api/v1/risk-forecasting/follow-ups', {
    method: 'POST',
    body,
    signal: options.signal || payload.signal,
    idempotencyKey: idempotencyKey ? String(idempotencyKey).trim() : undefined,
    headers,
  });
}

/**
 * Lists stored follow-up records matching specified query filters with pagination.
 * GET /api/v1/risk-forecasting/follow-ups
 */
export async function listFollowUps(filters = {}, options = {}) {
  const actorContext = options.actorContext || options.actor || filters.actorContext || filters.actor;
  const headers = buildActorHeaders(actorContext, false);

  const queryParams = {
    forecast_id: filters.forecast_id ?? filters.forecastId,
    district: filters.district,
    disease: filters.disease,
    assigned_vet_id: filters.assigned_vet_id ?? filters.assignedVetId,
    issued_by_daph_id: filters.issued_by_daph_id ?? filters.issuedByDaphId,
    status: filters.status,
    target_year: filters.target_year ?? filters.targetYear,
    target_month: filters.target_month ?? filters.targetMonth,
    limit: filters.limit,
    offset: filters.offset,
  };
  const queryString = buildQueryString(queryParams);

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups${queryString}`, {
    method: 'GET',
    signal: options.signal || filters.signal,
    headers,
  });
}

/**
 * Retrieves a single follow-up record by unique follow_up_id.
 * GET /api/v1/risk-forecasting/follow-ups/{follow_up_id}
 */
export async function getFollowUp(followUpId, options = {}) {
  const safeId = encodePathId(followUpId, 'followUpId');
  const actorContext = options.actorContext || options.actor;
  const headers = buildActorHeaders(actorContext, false);

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups/${safeId}`, {
    method: 'GET',
    signal: options.signal,
    headers,
  });
}

/**
 * Helper to parse transition parameters (version, actorContext, signal).
 */
function parseTransitionArgs(versionOrOptions, options = {}) {
  let ver;
  let actorContext;
  let signal;
  let reason;

  if (typeof versionOrOptions === 'number' || (typeof versionOrOptions === 'string' && versionOrOptions !== '' && !isNaN(Number(versionOrOptions)))) {
    ver = Number(versionOrOptions);
    reason = options.reason;
    actorContext = options.actorContext || options.actor;
    signal = options.signal;
  } else if (versionOrOptions && typeof versionOrOptions === 'object') {
    ver = versionOrOptions.version !== undefined ? Number(versionOrOptions.version) : undefined;
    reason = versionOrOptions.reason ?? options.reason;
    actorContext = versionOrOptions.actorContext || versionOrOptions.actor || options.actorContext || options.actor;
    signal = versionOrOptions.signal || options.signal;
  }

  return { ver, reason, actorContext, signal };
}

/**
 * Transitions status from ISSUED -> ACKNOWLEDGED (Assigned Vet Only).
 * POST /api/v1/risk-forecasting/follow-ups/{follow_up_id}/acknowledge
 */
export async function acknowledgeFollowUp(followUpId, versionOrOptions, options = {}) {
  const safeId = encodePathId(followUpId, 'followUpId');
  const { ver, actorContext, signal } = parseTransitionArgs(versionOrOptions, options);

  if (ver === undefined || ver === null || isNaN(ver) || ver < 1) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer >= 1.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/acknowledge`,
    });
  }

  const headers = buildActorHeaders(actorContext, true);

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups/${safeId}/acknowledge`, {
    method: 'POST',
    body: { version: ver },
    signal,
    headers,
  });
}

/**
 * Transitions status from ACKNOWLEDGED -> ACTION_IN_PROGRESS (Assigned Vet Only).
 * POST /api/v1/risk-forecasting/follow-ups/{follow_up_id}/start
 */
export async function startFollowUpAction(followUpId, versionOrOptions, options = {}) {
  const safeId = encodePathId(followUpId, 'followUpId');
  const { ver, actorContext, signal } = parseTransitionArgs(versionOrOptions, options);

  if (ver === undefined || ver === null || isNaN(ver) || ver < 1) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer >= 1.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/start`,
    });
  }

  const headers = buildActorHeaders(actorContext, true);

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups/${safeId}/start`, {
    method: 'POST',
    body: { version: ver },
    signal,
    headers,
  });
}

/**
 * Transitions status from ACTION_IN_PROGRESS -> COMPLETED (Assigned Vet Only).
 * POST /api/v1/risk-forecasting/follow-ups/{follow_up_id}/complete
 */
export async function completeFollowUp(followUpId, versionOrOptions, options = {}) {
  const safeId = encodePathId(followUpId, 'followUpId');
  const { ver, actorContext, signal } = parseTransitionArgs(versionOrOptions, options);

  if (ver === undefined || ver === null || isNaN(ver) || ver < 1) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer >= 1.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/complete`,
    });
  }

  const headers = buildActorHeaders(actorContext, true);

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups/${safeId}/complete`, {
    method: 'POST',
    body: { version: ver },
    signal,
    headers,
  });
}

/**
 * Transitions status to CANCELLED (DAPH Official Only).
 * POST /api/v1/risk-forecasting/follow-ups/{follow_up_id}/cancel
 */
export async function cancelFollowUp(followUpId, versionOrOptions, options = {}) {
  const safeId = encodePathId(followUpId, 'followUpId');
  const { ver, reason, actorContext, signal } = parseTransitionArgs(versionOrOptions, options);

  if (ver === undefined || ver === null || isNaN(ver) || ver < 1) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer >= 1.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/cancel`,
    });
  }

  const headers = buildActorHeaders(actorContext, true);
  const body = { version: ver };
  if (reason && String(reason).trim() !== '') {
    body.reason = String(reason).trim();
  }

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups/${safeId}/cancel`, {
    method: 'POST',
    body,
    signal,
    headers,
  });
}

/**
 * Transitions status to ESCALATED. Requires explicit controlled reason.
 * POST /api/v1/risk-forecasting/follow-ups/{follow_up_id}/escalate
 */
export async function escalateFollowUp(followUpId, args = {}, options = {}) {
  const safeId = encodePathId(followUpId, 'followUpId');
  const { ver, reason, actorContext, signal } = parseTransitionArgs(args, options);

  if (ver === undefined || ver === null || isNaN(ver) || ver < 1) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer >= 1.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/escalate`,
    });
  }

  if (!reason || String(reason).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: 'Reason is required for escalating a follow-up instruction.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/escalate`,
    });
  }

  const headers = buildActorHeaders(actorContext, true);
  const body = {
    version: ver,
    reason: String(reason).trim(),
  };

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups/${safeId}/escalate`, {
    method: 'POST',
    body,
    signal,
    headers,
  });
}

/**
 * Links an opaque external supply-chain resource request reference ID.
 * POST /api/v1/risk-forecasting/follow-ups/{follow_up_id}/external-resource-reference
 */
export async function linkExternalResourceReference(followUpId, args = {}, options = {}) {
  const safeId = encodePathId(followUpId, 'followUpId');

  let ver;
  let externalResourceId;
  let actorContext;
  let signal;

  if (typeof args === 'number' || (typeof args === 'string' && !isNaN(Number(args)))) {
    ver = Number(args);
    externalResourceId = options.externalResourceRequestId || options.external_resource_request_id || options.externalResourceId;
    actorContext = options.actorContext || options.actor;
    signal = options.signal;
  } else if (args && typeof args === 'object') {
    ver = args.version !== undefined ? Number(args.version) : undefined;
    externalResourceId = args.externalResourceRequestId ?? args.external_resource_request_id ?? args.externalResourceId ?? options.externalResourceRequestId;
    actorContext = args.actorContext || args.actor || options.actorContext || options.actor;
    signal = args.signal || options.signal;
  }

  if (ver === undefined || ver === null || isNaN(ver) || ver < 1) {
    throw new RiskForecastingWorkflowApiError({
      message: 'version is required and must be an integer >= 1.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/external-resource-reference`,
    });
  }

  if (!externalResourceId || String(externalResourceId).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: 'external_resource_request_id is required for linking resource reference.',
      endpoint: `/api/v1/risk-forecasting/follow-ups/${safeId}/external-resource-reference`,
    });
  }

  const headers = buildActorHeaders(actorContext, true);
  const body = {
    version: ver,
    external_resource_request_id: String(externalResourceId).trim(),
  };

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-ups/${safeId}/external-resource-reference`, {
    method: 'POST',
    body,
    signal,
    headers,
  });
}

/**
 * Lists active Veterinary Officers eligible for follow-up assignment in a specified Sri Lankan district.
 * GET /api/v1/risk-forecasting/follow-up-vets?district={district}
 * (DAPH Official Only)
 *
 * @param {object} filters - Object containing required `district` string parameter
 * @param {object} options - Options containing `actorContext` and optional `signal`
 * @returns {Promise<object>} Promise resolving to EligibleVetListResponse ({ district, total_count, veterinary_officers })
 */
export async function listEligibleFollowUpVets(filters = {}, options = {}) {
  const rawDistrict = filters?.district ?? filters?.districtName;
  const actorContext = options.actorContext || options.actor || filters?.actorContext || filters?.actor;

  if (rawDistrict === undefined || rawDistrict === null || String(rawDistrict).trim() === '') {
    throw new RiskForecastingWorkflowApiError({
      message: 'district parameter is required for querying eligible Veterinary Officers.',
      endpoint: '/api/v1/risk-forecasting/follow-up-vets',
    });
  }

  const district = String(rawDistrict).trim();
  const headers = buildActorHeaders(actorContext, true);
  const queryString = buildQueryString({ district });

  return requestWorkflowApi(`/api/v1/risk-forecasting/follow-up-vets${queryString}`, {
    method: 'GET',
    signal: options?.signal || filters?.signal,
    headers,
  });
}

/**
 * Forwards an approved advisory to the assigned farmers of the requesting Veterinary Officer.
 * POST /api/v1/risk-forecasting/advisories/{advisoryId}/forward-to-assigned-farmers
 */
export async function forwardToAssignedFarmers(advisoryId, options = {}) {
  const actorContext = options.actorContext || options.actor;
  const headers = buildActorHeaders(actorContext, true);
  
  if (!advisoryId) {
    throw new RiskForecastingWorkflowApiError({
      message: 'advisoryId is required.',
      endpoint: '/api/v1/risk-forecasting/advisories/forward-to-assigned-farmers',
    });
  }
  
  return requestWorkflowApi(`/api/v1/risk-forecasting/advisories/${advisoryId}/forward-to-assigned-farmers`, {
    method: 'POST',
    signal: options?.signal,
    headers,
  });
}
