const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Custom Error class for Risk Forecasting API failures.
 */
export class RiskForecastingApiError extends Error {
  constructor({ message, status, endpoint, disease = null, detail = null, cause = null }) {
    super(message);
    this.name = 'RiskForecastingApiError';
    this.status = status;
    this.endpoint = endpoint;
    this.disease = disease;
    this.detail = detail;
    if (cause) {
      this.cause = cause;
    }
  }
}

/**
 * Internal error handler for normalizing API responses using single-pass body consumption.
 * @param {Response} res
 * @param {string} endpoint
 * @param {string|null} disease
 */
async function parseApiError(res, endpoint, disease = null) {
  const status = res.status;
  let text = '';

  try {
    text = await res.text();
  } catch (_) {
    // Single-pass text consumption fallback
  }

  let detail = null;
  let parsed = null;

  if (text && text.trim() !== '') {
    try {
      parsed = JSON.parse(text);
      detail = parsed?.detail ?? parsed;
    } catch (_) {
      // Non-JSON response or malformed JSON
    }
  }

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
    ? `API Error ${status}: ${detailMsg}`
    : `API Error ${status}`;

  return new RiskForecastingApiError({
    message,
    status,
    endpoint,
    disease,
    detail,
  });
}

/**
 * Centralized internal API fetch wrapper handling network failures and response parsing.
 * @param {string} endpoint
 * @param {object} options
 * @param {string|null} disease
 */
async function requestApi(endpoint, options = {}, disease = null) {
  let res;
  try {
    res = await fetch(endpoint, options);
  } catch (err) {
    throw new RiskForecastingApiError({
      message: `Network request failed: ${err.message || 'Unable to connect to backend'}`,
      status: null,
      endpoint,
      disease,
      detail: null,
      cause: err,
    });
  }

  if (!res.ok) {
    throw await parseApiError(res, endpoint, disease);
  }

  return res.json();
}

/**
 * Fetch health status of the Risk Forecasting module.
 * Calls GET /api/v1/risk-forecasting/health
 * @returns {Promise<{status: string, component: string, version: string, models_loaded: boolean, loaded_artifacts: string[]}>}
 */
export async function fetchRiskForecastingHealth() {
  const endpoint = `${API_BASE}/api/v1/risk-forecasting/health`;
  return requestApi(endpoint, { method: 'GET' }, null);
}

/**
 * Fetch the list of 25 Sri Lankan administrative districts and month names metadata.
 * Calls GET /api/v1/risk-forecasting/districts
 * @returns {Promise<{total_districts: number, districts: string[], month_names: string[]}>}
 */
export async function fetchDistricts() {
  const endpoint = `${API_BASE}/api/v1/risk-forecasting/districts`;
  return requestApi(endpoint, { method: 'GET' }, null);
}

/**
 * Request single-district outbreak prediction for Foot-and-Mouth Disease (FMD).
 * Calls POST /api/v1/risk-forecasting/predict/fmd
 * @param {object} payload - { district: string, year: number, month: number, use31Features?: boolean }
 * @returns {Promise<object>} FMD prediction response object
 */
export async function predictFMD({ district, year, month, use31Features = false } = {}) {
  const endpoint = `${API_BASE}/api/v1/risk-forecasting/predict/fmd`;
  const body = {
    district,
    year: Number(year),
    month: Number(month),
    model_variant: use31Features ? '31_feature_autocorrelation' : '30_feature_baseline',
  };
  return requestApi(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, 'FMD');
}

/**
 * Request single-district outbreak prediction for Lumpy Skin Disease (LSD).
 * Calls POST /api/v1/risk-forecasting/predict/lsd
 * @param {object} payload - { district: string, year: number, month: number }
 * @returns {Promise<object>} LSD prediction response object
 */
export async function predictLSD({ district, year, month } = {}) {
  const endpoint = `${API_BASE}/api/v1/risk-forecasting/predict/lsd`;
  const body = {
    district,
    year: Number(year),
    month: Number(month),
  };
  return requestApi(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, 'LSD');
}

/**
 * Request all-district climatological risk forecast for FMD or LSD.
 * Calls POST /api/v1/risk-forecasting/forecast/{fmd|lsd}
 * @param {string} disease - 'FMD' or 'LSD'
 * @param {object} payload - { month: number, target_month?: number, year?: number, target_year?: number }
 * @returns {Promise<object>} Forecast response object
 */
export async function fetchForecast(disease, payload = {}) {
  const diseaseUpper = disease ? disease.toUpperCase() : 'FMD';
  const endpointSlug = diseaseUpper === 'LSD' ? 'lsd' : 'fmd';
  const endpoint = `${API_BASE}/api/v1/risk-forecasting/forecast/${endpointSlug}`;

  const body = {
    target_month: Number(payload.target_month ?? payload.month),
    year: Number(payload.year ?? payload.target_year ?? 2024),
  };

  return requestApi(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, diseaseUpper);
}

/**
 * Internal helper to validate year parameter (2017-2030).
 */
function validateYear(year) {
  const numYear = Number(year);
  if (!Number.isInteger(numYear) || numYear < 2017 || numYear > 2030) {
    throw new RangeError('Invalid year: year must be an integer between 2017 and 2030');
  }
  return numYear;
}

/**
 * Internal helper to validate month parameter (1-12).
 */
function validateMonth(month) {
  const numMonth = Number(month);
  if (!Number.isInteger(numMonth) || numMonth < 1 || numMonth > 12) {
    throw new RangeError('Invalid month: month must be an integer between 1 and 12');
  }
  return numMonth;
}

/**
 * Request combined single-district predictions for both FMD and LSD.
 * Supports partial success via Promise.allSettled.
 * @param {object} params - { district: string, year: number, month: number, use31Features?: boolean }
 * @returns {Promise<object>} Normalized combined prediction result
 */
export async function predictDistrictDiseaseRisks({ district, year, month, use31Features = true } = {}) {
  if (typeof district !== 'string' || district.trim() === '') {
    throw new TypeError('Invalid district: district must be a non-empty string');
  }
  const parsedDistrict = district.trim();
  const parsedYear = validateYear(year);
  const parsedMonth = validateMonth(month);

  const [fmdSettled, lsdSettled] = await Promise.allSettled([
    predictFMD({ district: parsedDistrict, year: parsedYear, month: parsedMonth, use31Features }),
    predictLSD({ district: parsedDistrict, year: parsedYear, month: parsedMonth }),
  ]);

  const fmdSuccess = fmdSettled.status === 'fulfilled';
  const lsdSuccess = lsdSettled.status === 'fulfilled';

  let overallStatus = 'error';
  if (fmdSuccess && lsdSuccess) {
    overallStatus = 'success';
  } else if (fmdSuccess || lsdSuccess) {
    overallStatus = 'partial';
  }

  return {
    district: parsedDistrict,
    year: parsedYear,
    month: parsedMonth,
    fmd: {
      status: fmdSuccess ? 'success' : 'error',
      data: fmdSuccess ? fmdSettled.value : null,
      error: fmdSuccess ? null : fmdSettled.reason,
    },
    lsd: {
      status: lsdSuccess ? 'success' : 'error',
      data: lsdSuccess ? lsdSettled.value : null,
      error: lsdSuccess ? null : lsdSettled.reason,
    },
    overallStatus,
  };
}

/**
 * Request combined all-district forecasts for both FMD and LSD.
 * Supports partial success via Promise.allSettled.
 * @param {object} params - { year: number, targetMonth?: number, month?: number }
 * @returns {Promise<object>} Normalized combined forecast result
 */
export async function fetchCombinedDistrictForecasts({ year, targetMonth, month } = {}) {
  const parsedYear = validateYear(year);
  const rawMonth = targetMonth ?? month;
  const parsedTargetMonth = validateMonth(rawMonth);

  const [fmdSettled, lsdSettled] = await Promise.allSettled([
    fetchForecast('FMD', { year: parsedYear, month: parsedTargetMonth }),
    fetchForecast('LSD', { year: parsedYear, month: parsedTargetMonth }),
  ]);

  const fmdSuccess = fmdSettled.status === 'fulfilled';
  const lsdSuccess = lsdSettled.status === 'fulfilled';

  let overallStatus = 'error';
  if (fmdSuccess && lsdSuccess) {
    overallStatus = 'success';
  } else if (fmdSuccess || lsdSuccess) {
    overallStatus = 'partial';
  }

  return {
    year: parsedYear,
    targetMonth: parsedTargetMonth,
    fmd: {
      status: fmdSuccess ? 'success' : 'error',
      data: fmdSuccess ? fmdSettled.value : null,
      error: fmdSuccess ? null : fmdSettled.reason,
    },
    lsd: {
      status: lsdSuccess ? 'success' : 'error',
      data: lsdSuccess ? lsdSettled.value : null,
      error: lsdSuccess ? null : lsdSettled.reason,
    },
    overallStatus,
  };
}
