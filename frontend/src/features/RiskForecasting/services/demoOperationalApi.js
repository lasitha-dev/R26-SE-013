/**
 * Protected Operational Demo Data API Module.
 *
 * Exposes GET functions for:
 * - fetchDemoFarms
 * - fetchDemoSurveillanceRecords
 * - fetchDemoAlerts
 * - fetchDemoResponseTasks
 *
 * Rules:
 * - Reads access token strictly via readDemoAccessToken().
 * - Sends Authorization: Bearer <token> header.
 * - Passes only skip and limit as query params.
 * - Validates response envelope: dataOrigin === "SYNTHETIC_DEMO", scientificUseAllowed === false, count === items.length.
 * - Validates strict synthetic field markers and ID prefixes per record.
 * - Contains NO write, POST, PUT, PATCH, DELETE, seed, or admin methods.
 */

import { readDemoAccessToken } from './demoSessionStorage.js';

const API_BASE = import.meta.env?.VITE_API_URL || '';

export const OPERATIONAL_ERROR_CATEGORIES = Object.freeze({
  UNAUTHENTICATED: 'UNAUTHENTICATED',
  FORBIDDEN: 'FORBIDDEN',
  VALIDATION: 'VALIDATION',
  UNAVAILABLE: 'UNAVAILABLE',
  ABORTED: 'ABORTED',
});

export class DemoOperationalApiError extends Error {
  constructor({ message, category, status = null }) {
    super(message);
    this.name = 'DemoOperationalApiError';
    this.category = category;
    this.status = status;
  }
}

/**
 * Validates pagination integer parameters.
 * @param {number} skip
 * @param {number} limit
 */
function validatePagination(skip, limit) {
  if (!Number.isInteger(skip) || skip < 0) {
    throw new DemoOperationalApiError({
      message: 'Pagination parameter "skip" must be a non-negative integer.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    throw new DemoOperationalApiError({
      message: 'Pagination parameter "limit" must be an integer between 1 and 100.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }
}

/**
 * Validates common synthetic operational response envelope.
 * @param {Object} data
 */
function validateEnvelope(data) {
  if (!data || typeof data !== 'object') {
    throw new DemoOperationalApiError({
      message: 'Operational data response envelope must be an object.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }

  const { items, skip, limit, count, dataOrigin, scientificUseAllowed } = data;

  if (!Array.isArray(items)) {
    throw new DemoOperationalApiError({
      message: 'Operational data envelope "items" must be an array.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }

  if (dataOrigin !== 'SYNTHETIC_DEMO') {
    throw new DemoOperationalApiError({
      message: 'Operational data envelope dataOrigin must be "SYNTHETIC_DEMO".',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }

  if (scientificUseAllowed !== false) {
    throw new DemoOperationalApiError({
      message: 'Operational data envelope scientificUseAllowed must be strictly false.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }

  if (!Number.isInteger(count) || count !== items.length) {
    throw new DemoOperationalApiError({
      message: 'Operational data envelope count must equal items array length.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }

  if (!Number.isInteger(skip) || skip < 0 || !Number.isInteger(limit) || limit < 1) {
    throw new DemoOperationalApiError({
      message: 'Operational data envelope pagination values are invalid.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }
}

/**
 * Validates DemoFarm item schema.
 */
function validateFarmItem(farm) {
  if (!farm || typeof farm !== 'object') return false;

  const {
    farmId,
    displayName,
    district,
    ownerUserId,
    assignedVetUserIds,
    livestockTypes,
    active,
    isSynthetic,
    dataOrigin,
    scientificUseAllowed,
  } = farm;

  if (typeof farmId !== 'string' || !farmId.startsWith('DEMO_FARM_')) return false;
  if (typeof displayName !== 'string' || displayName.trim() === '') return false;
  if (typeof district !== 'string' || district.trim() === '') return false;
  if (typeof ownerUserId !== 'string' || !ownerUserId.startsWith('DEMO_USER_')) return false;
  if (!Array.isArray(assignedVetUserIds)) return false;
  if (!Array.isArray(livestockTypes)) return false;
  if (typeof active !== 'boolean') return false;

  if (isSynthetic !== true) return false;
  if (dataOrigin !== 'SYNTHETIC_DEMO') return false;
  if (scientificUseAllowed !== false) return false;

  return true;
}

/**
 * Validates DemoSurveillanceRecord item schema.
 */
function validateSurveillanceRecordItem(rec) {
  if (!rec || typeof rec !== 'object') return false;

  const {
    surveillanceRecordId,
    farmId,
    district,
    diseaseCode,
    observedAt,
    evidenceType,
    verificationStatus,
    sourceModule,
    summary,
    isSynthetic,
    dataOrigin,
    scientificUseAllowed,
  } = rec;

  if (typeof surveillanceRecordId !== 'string' || !surveillanceRecordId.startsWith('DEMO_SURV_')) return false;
  if (typeof farmId !== 'string' || !farmId.startsWith('DEMO_FARM_')) return false;
  if (typeof district !== 'string' || district.trim() === '') return false;
  if (diseaseCode !== 'FMD' && diseaseCode !== 'LSD') return false;
  if (typeof observedAt !== 'string' || observedAt.trim() === '') return false;
  if (typeof evidenceType !== 'string' || evidenceType.trim() === '') return false;
  if (typeof verificationStatus !== 'string' || verificationStatus.trim() === '') return false;
  if (typeof sourceModule !== 'string' || sourceModule.trim() === '') return false;
  if (typeof summary !== 'string' || summary.trim() === '') return false;

  if (isSynthetic !== true) return false;
  if (dataOrigin !== 'SYNTHETIC_DEMO') return false;
  if (scientificUseAllowed !== false) return false;

  return true;
}

/**
 * Validates DemoAlert item schema.
 */
function validateAlertItem(alert) {
  if (!alert || typeof alert !== 'object') return false;

  const {
    alertId,
    district,
    diseaseCode,
    status,
    priority,
    issuedAt,
    affectedFarmIds,
    sourceSurveillanceRecordIds,
    title,
    message,
    isSynthetic,
    dataOrigin,
    scientificUseAllowed,
  } = alert;

  if (typeof alertId !== 'string' || !alertId.startsWith('DEMO_ALERT_')) return false;
  if (typeof district !== 'string' || district.trim() === '') return false;
  if (diseaseCode !== 'FMD' && diseaseCode !== 'LSD') return false;
  if (typeof status !== 'string' || status.trim() === '') return false;
  if (typeof priority !== 'string' || priority.trim() === '') return false;
  if (typeof issuedAt !== 'string' || issuedAt.trim() === '') return false;
  if (!Array.isArray(affectedFarmIds)) return false;
  if (!Array.isArray(sourceSurveillanceRecordIds)) return false;
  if (typeof title !== 'string' || title.trim() === '') return false;
  if (typeof message !== 'string' || message.trim() === '') return false;

  if (isSynthetic !== true) return false;
  if (dataOrigin !== 'SYNTHETIC_DEMO') return false;
  if (scientificUseAllowed !== false) return false;

  return true;
}

/**
 * Validates DemoResponseTask item schema.
 */
function validateResponseTaskItem(task) {
  if (!task || typeof task !== 'object') return false;

  const {
    responseTaskId,
    alertId,
    assignedOfficerUserId,
    district,
    farmId,
    taskType,
    status,
    dueAt,
    notes,
    isSynthetic,
    dataOrigin,
    scientificUseAllowed,
  } = task;

  if (typeof responseTaskId !== 'string' || !responseTaskId.startsWith('DEMO_TASK_')) return false;
  if (typeof alertId !== 'string' || !alertId.startsWith('DEMO_ALERT_')) return false;
  if (typeof assignedOfficerUserId !== 'string' || !assignedOfficerUserId.startsWith('DEMO_USER_')) return false;
  if (typeof district !== 'string' || district.trim() === '') return false;
  if (farmId !== undefined && farmId !== null && (typeof farmId !== 'string' || !farmId.startsWith('DEMO_FARM_'))) return false;
  if (typeof taskType !== 'string' || taskType.trim() === '') return false;
  if (typeof status !== 'string' || status.trim() === '') return false;
  if (typeof dueAt !== 'string' || dueAt.trim() === '') return false;
  if (typeof notes !== 'string') return false;

  if (isSynthetic !== true) return false;
  if (dataOrigin !== 'SYNTHETIC_DEMO') return false;
  if (scientificUseAllowed !== false) return false;

  return true;
}

/**
 * Internal core request handler for protected operational endpoints.
 */
async function fetchOperationalResource(pathSlug, itemValidator, { skip = 0, limit = 50, signal } = {}) {
  validatePagination(skip, limit);

  const token = readDemoAccessToken();
  if (!token) {
    throw new DemoOperationalApiError({
      message: 'Your demo session has expired.',
      category: OPERATIONAL_ERROR_CATEGORIES.UNAUTHENTICATED,
      status: 401,
    });
  }

  const endpoint = `${API_BASE}/api/v1/demo-operational/${pathSlug}?skip=${skip}&limit=${limit}`;

  let res;
  try {
    res = await fetch(endpoint, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal,
    });
  } catch (err) {
    if (err?.name === 'AbortError') {
      throw new DemoOperationalApiError({
        message: 'Request was cancelled.',
        category: OPERATIONAL_ERROR_CATEGORIES.ABORTED,
      });
    }
    throw new DemoOperationalApiError({
      message: 'Operational data service is currently unavailable.',
      category: OPERATIONAL_ERROR_CATEGORIES.UNAVAILABLE,
    });
  }

  if (!res.ok) {
    if (res.status === 401) {
      throw new DemoOperationalApiError({
        message: 'Your demo session has expired.',
        category: OPERATIONAL_ERROR_CATEGORIES.UNAUTHENTICATED,
        status: 401,
      });
    }
    if (res.status === 403) {
      throw new DemoOperationalApiError({
        message: 'Operational data access is not permitted for your assigned role or scope.',
        category: OPERATIONAL_ERROR_CATEGORIES.FORBIDDEN,
        status: 403,
      });
    }
    throw new DemoOperationalApiError({
      message: 'Operational data service is currently unavailable.',
      category: OPERATIONAL_ERROR_CATEGORIES.UNAVAILABLE,
      status: res.status,
    });
  }

  let data;
  try {
    data = await res.json();
  } catch (_) {
    throw new DemoOperationalApiError({
      message: 'Operational data response failed validation.',
      category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
    });
  }

  validateEnvelope(data);

  for (const item of data.items) {
    if (!itemValidator(item)) {
      throw new DemoOperationalApiError({
        message: 'Operational record item failed validation schema checks.',
        category: OPERATIONAL_ERROR_CATEGORIES.VALIDATION,
      });
    }
  }

  return data;
}

/**
 * Fetch authenticated synthetic farms.
 * Calls GET /api/v1/demo-operational/farms
 */
export async function fetchDemoFarms(options = {}) {
  return fetchOperationalResource('farms', validateFarmItem, options);
}

/**
 * Fetch authenticated synthetic surveillance records.
 * Calls GET /api/v1/demo-operational/surveillance-records
 */
export async function fetchDemoSurveillanceRecords(options = {}) {
  return fetchOperationalResource('surveillance-records', validateSurveillanceRecordItem, options);
}

/**
 * Fetch authenticated synthetic alerts.
 * Calls GET /api/v1/demo-operational/alerts
 */
export async function fetchDemoAlerts(options = {}) {
  return fetchOperationalResource('alerts', validateAlertItem, options);
}

/**
 * Fetch authenticated synthetic response tasks.
 * Calls GET /api/v1/demo-operational/response-tasks
 */
export async function fetchDemoResponseTasks(options = {}) {
  return fetchOperationalResource('response-tasks', validateResponseTaskItem, options);
}
