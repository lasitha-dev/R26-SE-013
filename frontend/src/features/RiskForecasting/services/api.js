const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Fetch the list of 25 Sri Lankan administrative districts and available month metadata.
 * @returns {Promise<{districts: string[], total_districts: number, available_months: Array<{month: number, name: string}>}>}
 */
export async function fetchDistricts() {
  const url = `${API_BASE}/api/v1/risk-forecasting/districts`;
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API Error ${res.status}: ${txt}`);
  }
  return res.json();
}

/**
 * Request single-district outbreak prediction for Foot-and-Mouth Disease (FMD).
 * @param {object} payload - { district: string, year: number, month: number, use_31_features?: boolean }
 * @returns {Promise<object>} FMD prediction response object
 */
export async function predictFMD(payload) {
  const url = `${API_BASE}/api/v1/risk-forecasting/predict/fmd`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`FMD Predict API Error ${res.status}: ${txt}`);
  }
  return res.json();
}

/**
 * Request single-district outbreak prediction for Lumpy Skin Disease (LSD).
 * @param {object} payload - { district: string, year: number, month: number }
 * @returns {Promise<object>} LSD prediction response object
 */
export async function predictLSD(payload) {
  const url = `${API_BASE}/api/v1/risk-forecasting/predict/lsd`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`LSD Predict API Error ${res.status}: ${txt}`);
  }
  return res.json();
}

/**
 * Request all-district climatological risk forecast for FMD or LSD.
 * @param {string} disease - 'fmd' or 'lsd'
 * @param {object} payload - { month: number, year?: number }
 * @returns {Promise<object>} Forecast response object
 */
export async function fetchForecast(disease, payload) {
  const endpoint = disease.toLowerCase() === 'lsd' ? 'lsd' : 'fmd';
  const url = `${API_BASE}/api/v1/risk-forecasting/forecast/${endpoint}`;
  
  // Format body to match backend ForecastRequest schema
  const body = {
    target_month: payload.target_month ?? payload.month,
    year: payload.year ?? payload.target_year ?? 2024,
  };

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Forecast API Error ${res.status}: ${txt}`);
  }
  return res.json();
}

