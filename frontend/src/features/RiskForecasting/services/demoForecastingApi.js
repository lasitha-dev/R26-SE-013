/**
 * Protected Demo Disease Forecasting API Module.
 *
 * Exposes functions to call protected role-scoped forecasting endpoints:
 * - fetchAuthorizedFmdForecast
 * - fetchAuthorizedLsdForecast
 * - fetchAuthorizedDiseaseForecasts
 *
 * Security & Design Rules:
 * - Reads demo access token strictly via readDemoAccessToken().
 * - Never accepts tokens from screen components or caller arguments.
 * - Sends Authorization: Bearer <token> header with POST requests.
 * - Sends strictly validated year (2017-2030) and target_month (1-12).
 * - FMD model_variant is fixed to "30_feature_baseline".
 * - Allows optional district (string) or districts (string array).
 * - Normalizes whitespace and deduplicates district values.
 * - Never sends role, scope, permissions, userId, assignedFarmIds, or operational records.
 * - Validates response envelope structure and scientific constraints.
 * - Provides sanitized error categories (UNAUTHENTICATED, FORBIDDEN, VALIDATION, UNAVAILABLE, ABORTED).
 */

import { readDemoAccessToken } from './demoSessionStorage.js';

const API_BASE = import.meta.env?.VITE_API_URL || '';

export const DEMO_FORECASTING_ERROR_CATEGORIES = Object.freeze({
  UNAUTHENTICATED: 'UNAUTHENTICATED',
  FORBIDDEN: 'FORBIDDEN',
  VALIDATION: 'VALIDATION',
  UNAVAILABLE: 'UNAVAILABLE',
  ABORTED: 'ABORTED',
});

export class DemoForecastingApiError extends Error {
  constructor({ message, category, status = null }) {
    super(message);
    this.name = 'DemoForecastingApiError';
    this.category = category;
    this.status = status;
  }
}

/**
 * Validates year parameter (2017-2030).
 */
function validateYear(year) {
  const numYear = Number(year);
  if (!Number.isInteger(numYear) || numYear < 2017 || numYear > 2030) {
    throw new DemoForecastingApiError({
      message: 'Forecast year must be an integer between 2017 and 2030.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }
  return numYear;
}

/**
 * Validates targetMonth parameter (1-12).
 */
function validateTargetMonth(targetMonth) {
  const numMonth = Number(targetMonth);
  if (!Number.isInteger(numMonth) || numMonth < 1 || numMonth > 12) {
    throw new DemoForecastingApiError({
      message: 'Forecast target month must be an integer between 1 and 12.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }
  return numMonth;
}

/**
 * Normalizes single district parameter.
 */
function normalizeDistrict(district) {
  if (district === undefined || district === null) return undefined;
  if (typeof district !== 'string' || district.trim() === '') {
    throw new DemoForecastingApiError({
      message: 'District parameter must be a non-empty string.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }
  return district.trim();
}

/**
 * Normalizes districts array parameter.
 */
function normalizeDistricts(districts) {
  if (districts === undefined || districts === null) return undefined;
  if (!Array.isArray(districts)) {
    throw new DemoForecastingApiError({
      message: 'Districts parameter must be an array of strings.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }
  const cleaned = [];
  const seen = new Set();
  for (const d of districts) {
    if (typeof d !== 'string' || d.trim() === '') continue;
    const trimmed = d.trim();
    if (!seen.has(trimmed)) {
      seen.add(trimmed);
      cleaned.push(trimmed);
    }
  }
  return cleaned.length > 0 ? cleaned : undefined;
}

/**
 * Validates general scientific forecast response structure.
 */
function validateForecastResponse(data, expectedDisease, expectedYear, expectedMonth, allowedDistricts) {
  if (!data || typeof data !== 'object') {
    throw new DemoForecastingApiError({
      message: 'Forecast response payload must be an object.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }

  if (data.disease !== expectedDisease) {
    throw new DemoForecastingApiError({
      message: `Forecast response disease '${data.disease}' does not match requested disease '${expectedDisease}'.`,
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }

  if (data.target_year !== expectedYear || data.target_month !== expectedMonth) {
    throw new DemoForecastingApiError({
      message: 'Forecast response target period does not match requested year and month.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }

  if (!Array.isArray(data.districts)) {
    throw new DemoForecastingApiError({
      message: 'Forecast response districts field must be an array.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }

  const allowedNormalized = allowedDistricts && Array.isArray(allowedDistricts)
    ? allowedDistricts.map(d => d.trim().toLowerCase())
    : null;

  for (const item of data.districts) {
    if (!item || typeof item !== 'object' || typeof item.district !== 'string' || item.district.trim() === '') {
      throw new DemoForecastingApiError({
        message: 'Forecast response district item is invalid.',
        category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
      });
    }
    if (allowedNormalized && !allowedNormalized.includes(item.district.trim().toLowerCase())) {
      throw new DemoForecastingApiError({
        message: `Forecast response contains unauthorized district '${item.district}'.`,
        category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
      });
    }
  }
}

/**
 * Core internal HTTP POST runner for protected demo forecasting endpoints.
 */
async function requestDemoForecast(endpointSlug, payload, expectedDisease, signal) {
  const token = readDemoAccessToken();
  if (!token) {
    throw new DemoForecastingApiError({
      message: 'Your demo session has expired.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED,
      status: 401,
    });
  }

  const allowedDistricts = payload.district ? [payload.district] : (payload.districts || null);

  const endpoint = `${API_BASE}/api/v1/demo-forecasting/forecast/${endpointSlug}`;

  let res;
  try {
    res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if (err?.name === 'AbortError') {
      throw new DemoForecastingApiError({
        message: 'Forecast request was cancelled.',
        category: DEMO_FORECASTING_ERROR_CATEGORIES.ABORTED,
      });
    }
    throw new DemoForecastingApiError({
      message: 'Forecast service is currently unavailable.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.UNAVAILABLE,
    });
  }

  if (!res.ok) {
    if (res.status === 401) {
      throw new DemoForecastingApiError({
        message: 'Your demo session has expired.',
        category: DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED,
        status: 401,
      });
    }
    if (res.status === 403) {
      throw new DemoForecastingApiError({
        message: 'Forecast access to the requested district is forbidden.',
        category: DEMO_FORECASTING_ERROR_CATEGORIES.FORBIDDEN,
        status: 403,
      });
    }
    if (res.status === 422) {
      throw new DemoForecastingApiError({
        message: 'Invalid forecast request parameters.',
        category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
        status: 422,
      });
    }
    throw new DemoForecastingApiError({
      message: 'Forecast service is currently unavailable.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.UNAVAILABLE,
      status: res.status,
    });
  }

  let data;
  try {
    data = await res.json();
  } catch (_) {
    throw new DemoForecastingApiError({
      message: 'Forecast response failed JSON validation.',
      category: DEMO_FORECASTING_ERROR_CATEGORIES.VALIDATION,
    });
  }

  validateForecastResponse(data, expectedDisease, payload.year, payload.target_month, allowedDistricts);
  return data;
}

/**
 * Fetch authenticated role-scoped FMD forecast.
 * Calls POST /api/v1/demo-forecasting/forecast/fmd
 */
export async function fetchAuthorizedFmdForecast({ year, targetMonth, district, districts, signal } = {}) {
  const parsedYear = validateYear(year);
  const parsedMonth = validateTargetMonth(targetMonth);
  const parsedDistrict = normalizeDistrict(district);
  const parsedDistricts = normalizeDistricts(districts);

  const payload = {
    target_month: parsedMonth,
    year: parsedYear,
    model_variant: '30_feature_baseline',
  };

  if (parsedDistrict) payload.district = parsedDistrict;
  if (parsedDistricts) payload.districts = parsedDistricts;

  return requestDemoForecast('fmd', payload, 'FMD', signal);
}

/**
 * Fetch authenticated role-scoped LSD forecast.
 * Calls POST /api/v1/demo-forecasting/forecast/lsd
 */
export async function fetchAuthorizedLsdForecast({ year, targetMonth, district, districts, signal } = {}) {
  const parsedYear = validateYear(year);
  const parsedMonth = validateTargetMonth(targetMonth);
  const parsedDistrict = normalizeDistrict(district);
  const parsedDistricts = normalizeDistricts(districts);

  const payload = {
    target_month: parsedMonth,
    year: parsedYear,
  };

  if (parsedDistrict) payload.district = parsedDistrict;
  if (parsedDistricts) payload.districts = parsedDistricts;

  return requestDemoForecast('lsd', payload, 'LSD', signal);
}

/**
 * Fetch combined authorized role-scoped FMD and LSD forecasts concurrently.
 * Supports partial success via Promise.allSettled.
 */
export async function fetchAuthorizedDiseaseForecasts({ year, targetMonth, district, districts, signal } = {}) {
  const [fmdSettled, lsdSettled] = await Promise.allSettled([
    fetchAuthorizedFmdForecast({ year, targetMonth, district, districts, signal }),
    fetchAuthorizedLsdForecast({ year, targetMonth, district, districts, signal }),
  ]);

  const fmdSuccess = fmdSettled.status === 'fulfilled';
  const lsdSuccess = lsdSettled.status === 'fulfilled';

  // Check if any failed due to authentication/authorization abort or error
  const fmdErr = fmdSuccess ? null : fmdSettled.reason;
  const lsdErr = lsdSuccess ? null : lsdSettled.reason;

  // Handle unauthenticated / forbidden auth failures
  if (fmdErr?.category === DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED || lsdErr?.category === DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED) {
    throw fmdErr?.category === DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED ? fmdErr : lsdErr;
  }
  if (fmdErr?.category === DEMO_FORECASTING_ERROR_CATEGORIES.FORBIDDEN || lsdErr?.category === DEMO_FORECASTING_ERROR_CATEGORIES.FORBIDDEN) {
    throw fmdErr?.category === DEMO_FORECASTING_ERROR_CATEGORIES.FORBIDDEN ? fmdErr : lsdErr;
  }

  let overallStatus = 'error';
  if (fmdSuccess && lsdSuccess) {
    overallStatus = 'success';
  } else if (fmdSuccess || lsdSuccess) {
    overallStatus = 'partial';
  }

  return {
    year: Number(year),
    targetMonth: Number(targetMonth),
    fmd: {
      status: fmdSuccess ? 'success' : 'error',
      data: fmdSuccess ? fmdSettled.value : null,
      error: fmdSuccess ? null : fmdErr?.message || 'FMD forecast unavailable',
      category: fmdSuccess ? null : fmdErr?.category || DEMO_FORECASTING_ERROR_CATEGORIES.UNAVAILABLE,
    },
    lsd: {
      status: lsdSuccess ? 'success' : 'error',
      data: lsdSuccess ? lsdSettled.value : null,
      error: lsdSuccess ? null : lsdErr?.message || 'LSD forecast unavailable',
      category: lsdSuccess ? null : lsdErr?.category || DEMO_FORECASTING_ERROR_CATEGORIES.UNAVAILABLE,
    },
    overallStatus,
  };
}
