import React, { useState, useEffect, useRef, useCallback, useContext } from 'react';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getRegisteredFarmDistrict,
} from '../../contracts/viewerContext';
import { predictDistrictDiseaseRisks } from '../../services/api';
import { AccessContextUnavailable } from '../AccessContextUnavailable';
import { DemoForecastingAuthContext } from '../../context/DemoForecastingAuthContext.jsx';
import {
  fetchAuthorizedDiseaseForecasts,
  DEMO_FORECASTING_ERROR_CATEGORIES,
} from '../../services/demoForecastingApi.js';

const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

const VALID_YEARS = Array.from({ length: 14 }, (_, i) => 2017 + i); // 2017-2030

/**
 * Validates initial period props.
 * Omitted props (null/undefined) safely default to current local period.
 * Explicitly provided props must be integers within valid ranges (years 2017-2030, months 1-12).
 */
function validatePeriod(initialYear, initialMonth) {
  const now = new Date();

  let year = null;
  let isYearValid = true;
  if (initialYear === undefined || initialYear === null) {
    let currentYr = now.getFullYear();
    if (currentYr < 2017) currentYr = 2017;
    if (currentYr > 2030) currentYr = 2030;
    year = currentYr;
  } else {
    const numYr = Number(initialYear);
    if (Number.isInteger(numYr) && numYr >= 2017 && numYr <= 2030) {
      year = numYr;
    } else {
      isYearValid = false;
    }
  }

  let month = null;
  let isMonthValid = true;
  if (initialMonth === undefined || initialMonth === null) {
    month = now.getMonth() + 1;
  } else {
    const numMth = Number(initialMonth);
    if (Number.isInteger(numMth) && numMth >= 1 && numMth <= 12) {
      month = numMth;
    } else {
      isMonthValid = false;
    }
  }

  return {
    valid: isYearValid && isMonthValid,
    year: year !== null ? year : 2026,
    month: month !== null ? month : 1,
    reason:
      !isYearValid || !isMonthValid
        ? 'The requested forecast year or month is outside the valid range (years 2017–2030, months 1–12).'
        : null,
  };
}

/**
 * Derives risk presentation details for recognized risk levels.
 * Does NOT default unknown risk levels to LOW.
 */
function getRiskDetails(riskLevel) {
  if (typeof riskLevel !== 'string') return null;
  const normalized = riskLevel.trim().toUpperCase();
  switch (normalized) {
    case 'HIGH':
      return {
        label: 'HIGH RISK',
        colorClass: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
        icon: 'warning',
        meaning: 'Conditions indicate an increased district-level outbreak risk.',
        guidance: [
          'Strengthen routine farm biosecurity.',
          'Monitor animals closely for unusual health changes.',
          'Follow instructions issued by your local veterinary authority.',
        ],
      };
    case 'MEDIUM':
      return {
        label: 'MEDIUM RISK',
        colorClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
        icon: 'warning',
        meaning: 'Conditions indicate a moderate district-level outbreak risk.',
        guidance: [
          'Continue careful animal monitoring.',
          'Review routine biosecurity measures.',
          'Stay alert for official veterinary guidance.',
        ],
      };
    case 'LOW':
      return {
        label: 'LOW RISK',
        colorClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
        icon: 'verified',
        meaning: 'Current conditions indicate a lower district-level outbreak risk.',
        guidance: [
          'Continue routine biosecurity and regular monitoring.',
          'Keep farm records current.',
          'Continue following local veterinary guidance.',
        ],
      };
    default:
      return null;
  }
}

/**
 * Extracts normalized stage1 and provenance data from prediction service or protected demo API response.
 */
function extractStage1AndProvenance(resultData) {
  if (!resultData) return { stage1: null, provenance: null };
  if (resultData.stage1) {
    return {
      stage1: resultData.stage1,
      provenance: resultData.provenance || null,
    };
  }
  if (Array.isArray(resultData.districts) && resultData.districts.length > 0) {
    const item = resultData.districts[0];
    const stage1 = item.stage1 || {
      probability_pct: item.probability_pct,
      risk_level: item.risk_level,
      predicted_severity: item.predicted_severity,
    };
    const provenance = item.provenance || resultData.provenance || {
      data_quality_status: resultData.data_quality_status || 'OK',
      fallback_applied: resultData.data_quality_status === 'DEGRADED',
    };
    return { stage1, provenance };
  }
  return { stage1: null, provenance: null };
}

/**
 * Validates whether a single disease response contains displayable Stage 1 data.
 */
function isDiseaseValid(result) {
  if (!result || result.status !== 'success' || !result.data) return false;
  const { stage1 } = extractStage1AndProvenance(result.data);
  if (!stage1) return false;
  if (typeof stage1.probability_pct !== 'number' || !Number.isFinite(stage1.probability_pct)) {
    return false;
  }
  const riskDetails = getRiskDetails(stage1.risk_level);
  if (!riskDetails) return false;
  return true;
}

/**
 * Farmer Disease Risk Screen Component
 * Displays district-level seasonal early-warning forecasts tailored for farmers.
 *
 * @param {object} props
 * @param {object} props.viewerContext
 * @param {number|string} [props.initialYear]
 * @param {number|string} [props.initialMonth]
 * @param {Function} [props.predictionService=predictDistrictDiseaseRisks]
 */
export function FarmerDiseaseRisk({
  viewerContext,
  initialYear,
  initialMonth,
  predictionService = predictDistrictDiseaseRisks,
}) {
  // 1. Access & Fail-Closed Validation
  const validation = validateViewerContext(viewerContext);
  const isValidFarmer =
    validation.valid &&
    validation.normalizedContext.role === ROLES.FARMER &&
    validation.normalizedContext.authorization.scopeLevel === SCOPE_LEVELS.FARM;

  const district = isValidFarmer ? getRegisteredFarmDistrict(viewerContext) : null;
  const isAccessAllowed = Boolean(isValidFarmer && district && district.trim() !== '');

  // 2. Period Validation
  const periodValidation = validatePeriod(initialYear, initialMonth);

  // 3. Form State (Draft selection controls)
  const [selectedYear, setSelectedYear] = useState(periodValidation.year);
  const [selectedMonth, setSelectedMonth] = useState(periodValidation.month);

  const [loading, setLoading] = useState(false);
  const [isInitialRequest, setIsInitialRequest] = useState(true);
  const [forecastData, setForecastData] = useState(null);
  const [errorState, setErrorState] = useState(null);

  const requestIdRef = useRef(0);
  const isMountedRef = useRef(true);
  const lastFetchedKeyRef = useRef(null);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const authContext = useContext(DemoForecastingAuthContext);
  const isDemoAuthActive = Boolean(
    (authContext?.isDemoEnabled || authContext?.demoEnabled) &&
    (authContext?.isDemoAuthenticated || authContext?.status === 'authenticated')
  );

  // 4. Fetch Forecast Function
  const fetchForecast = useCallback(
    async (yr, mth, isInitial = false) => {
      if (!isAccessAllowed || !district || !periodValidation.valid) return;

      const currentRequestId = ++requestIdRef.current;
      lastFetchedKeyRef.current = `${district}:${yr}:${mth}`;

      setLoading(true);
      setIsInitialRequest(isInitial);
      setErrorState(null);

      try {
        let result;
        if (isDemoAuthActive) {
          result = await fetchAuthorizedDiseaseForecasts({
            district,
            year: Number(yr),
            targetMonth: Number(mth),
          });
        } else {
          result = await predictionService({
            district,
            year: Number(yr),
            month: Number(mth),
          });
        }

        if (!isMountedRef.current || currentRequestId !== requestIdRef.current) {
          return;
        }

        setForecastData(result);
        setLoading(false);
      } catch (err) {
        if (!isMountedRef.current || currentRequestId !== requestIdRef.current) {
          return;
        }

        setForecastData(null);
        if (err?.category === DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED || err?.status === 401) {
          setErrorState('Your demo session has expired.');
          if (authContext?.logout) authContext.logout();
        } else if (err?.category === DEMO_FORECASTING_ERROR_CATEGORIES.FORBIDDEN || err?.status === 403) {
          setErrorState('Forecast access to the requested district is forbidden.');
        } else {
          setErrorState(
            'Forecast service unavailable. Unable to load outbreak risk metrics at this time.'
          );
        }
        setLoading(false);
      }
    },
    [isAccessAllowed, district, periodValidation.valid, predictionService, isDemoAuthActive, authContext]
  );

  // 5. Scoped District & Access Change Observer Effect
  useEffect(() => {
    if (!isAccessAllowed || !periodValidation.valid) {
      // Fail-closed / Invalid period state: invalidate in-flight requests and clear old data immediately
      requestIdRef.current++;
      lastFetchedKeyRef.current = null;
      setForecastData(null);
      setLoading(false);
      return;
    }

    const currentKey = `${district}:${periodValidation.year}:${periodValidation.month}`;
    if (lastFetchedKeyRef.current !== currentKey) {
      // District or initial period changed: clear previous district data immediately and fetch for new district
      setForecastData(null);
      fetchForecast(periodValidation.year, periodValidation.month, true);
    }
  }, [isAccessAllowed, district, periodValidation.valid, periodValidation.year, periodValidation.month, fetchForecast]);

  // Fail-Closed Access Gate
  if (!isAccessAllowed) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'FARMER role with valid FARM scopeLevel and registered district required.'
        }
      />
    );
  }

  // Explicit Invalid Forecast Period Gate
  if (!periodValidation.valid) {
    return (
      <div
        role="alert"
        aria-live="polite"
        className="max-w-2xl mx-4 sm:mx-auto my-8 p-6 rounded-2xl bg-surface-container border border-amber-500/30 shadow-xl text-on-surface"
      >
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
            <span className="material-symbols-outlined text-2xl" aria-hidden="true">
              event_busy
            </span>
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-amber-300 tracking-wide">
              Invalid forecast period
            </h3>
            <p className="text-sm text-on-surface-variant leading-relaxed">{periodValidation.reason}</p>
          </div>
        </div>
      </div>
    );
  }

  const handleUpdate = (e) => {
    e.preventDefault();
    if (!loading) {
      fetchForecast(selectedYear, selectedMonth, false);
    }
  };

  const fmdResult = forecastData?.fmd;
  const lsdResult = forecastData?.lsd;

  const fmdValid = isDiseaseValid(fmdResult);
  const lsdValid = isDiseaseValid(lsdResult);

  const overallStatus = forecastData?.overallStatus;
  const isPartial = overallStatus === 'partial' || (forecastData && (fmdValid !== lsdValid));
  const isBothFailed = overallStatus === 'error' || (forecastData && !fmdValid && !lsdValid);

  // Live status message calculation
  let liveStatusMessage = '';
  if (loading) {
    liveStatusMessage = isInitialRequest ? 'Loading forecast…' : 'Updating forecast…';
  } else if (errorState || isBothFailed) {
    liveStatusMessage = `Forecast service unavailable for ${district}.`;
  } else if (isPartial) {
    liveStatusMessage = `Forecast updated with partial data for ${district}. Some metrics could not be loaded.`;
  } else if (forecastData) {
    liveStatusMessage = `Forecast updated for ${district}.`;
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Header & Controls */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold text-primary tracking-tight">
            Disease Risk in My Area
          </h1>
          <p className="text-sm text-on-surface-variant">
            District-level seasonal early-warning forecast for{' '}
            <span className="font-semibold text-on-surface">{district}</span> District
          </p>
        </div>

        {/* Period Selector Form */}
        <form onSubmit={handleUpdate} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col space-y-1">
            <label
              htmlFor="farmer-month-select"
              className="text-xs font-medium text-on-surface-variant"
            >
              Forecast month
            </label>
            <select
              id="farmer-month-select"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(Number(e.target.value))}
              disabled={loading}
              className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400 focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:opacity-50"
            >
              {MONTH_NAMES.map((name, idx) => (
                <option key={name} value={idx + 1}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col space-y-1">
            <label
              htmlFor="farmer-year-select"
              className="text-xs font-medium text-on-surface-variant"
            >
              Forecast year
            </label>
            <select
              id="farmer-year-select"
              value={selectedYear}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
              disabled={loading}
              className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400 focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:opacity-50"
            >
              {VALID_YEARS.map((yr) => (
                <option key={yr} value={yr}>
                  {yr}
                </option>
              ))}
            </select>
          </div>


          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2.5 bg-primary-container hover:brightness-110 disabled:bg-surface-container-high disabled:text-on-surface-variant text-on-primary font-semibold text-sm rounded-xl transition-all min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400 focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            {loading ? 'Updating forecast…' : 'Update forecast'}
          </button>
        </form>
      </header>

      {/* Accessible Live Region */}
      <div role="status" aria-live="polite" className="sr-only">
        {liveStatusMessage}
      </div>

      {/* Global Service Error */}
      {errorState && (
        <div className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            error
          </span>
          <span>{errorState}</span>
        </div>
      )}

      {/* Partial Failure Notice */}
      {isPartial && !loading && !errorState && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-300 text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            warning
          </span>
          <span>
            Partial forecast data available. Some disease metrics could not be loaded for the selected period.
          </span>
        </div>
      )}

      {/* Both Diseases Failed Notice */}
      {isBothFailed && !loading && !errorState && (
        <div className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            error
          </span>
          <span>
            Forecast service unavailable. Unable to load outbreak risk metrics at this time.
          </span>
        </div>
      )}

      {/* Disease Risk Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Foot-and-Mouth Disease (FMD) Card */}
        <DiseaseCard
          title="Foot-and-Mouth Disease (FMD)"
          abbreviation="FMD"
          loading={loading}
          result={fmdResult}
        />

        {/* Lumpy Skin Disease (LSD) Card */}
        <DiseaseCard
          title="Lumpy Skin Disease (LSD)"
          abbreviation="LSD"
          loading={loading}
          result={lsdResult}
        />
      </div>

      {/* Mandatory District-Level Scientific Disclaimer */}
      <footer className="p-4 bg-surface-container-low rounded-xl border border-outline-variant/30 text-center text-xs text-on-surface-variant space-y-1">
        <p className="font-medium text-on-surface">
          This is a district-level early-warning forecast and does not mean disease has been detected on your farm.
        </p>
        <p className="text-on-surface-variant/70">
          Seasonal forecasts provide statistical risk estimates for veterinary surveillance planning.
        </p>
      </footer>
    </div>
  );
}

/**
 * Pure Farmer Disease Card Helper
 */
function DiseaseCard({ title, abbreviation, loading, result }) {
  if (loading) {
    return (
      <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 space-y-4 animate-pulse motion-reduce:animate-none">
        <div className="h-6 w-3/4 bg-surface-container-high rounded"></div>
        <div className="h-10 w-1/2 bg-surface-container-high rounded"></div>
        <div className="h-16 w-full bg-surface-container-high rounded"></div>
      </div>
    );
  }

  const isValid = isDiseaseValid(result);
  const { stage1, provenance } = isValid ? extractStage1AndProvenance(result.data) : { stage1: null, provenance: null };
  const riskDetails = isValid ? getRiskDetails(stage1.risk_level) : null;

  return (
    <section
      className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xl flex flex-col justify-between space-y-6"
      aria-labelledby={`disease-card-${abbreviation}`}
    >
      <div className="space-y-4">
        {/* Card Header */}
        <div className="flex items-center justify-between">
          <h2 id={`disease-card-${abbreviation}`} className="text-lg font-semibold text-on-surface">
            {title}
          </h2>
          <span className="text-xs font-mono px-2.5 py-1 bg-surface-container-high text-on-surface-variant rounded-lg border border-outline-variant/40">
            {abbreviation}
          </span>
        </div>

        {/* Risk Percentage & Badge */}
        {isValid ? (
          <div className="flex items-center justify-between gap-4 p-4 rounded-xl bg-surface-container-lowest/60 border border-outline-variant/30">
            <div>
              <span className="text-3xl font-extrabold tracking-tight text-on-surface">
                {stage1.probability_pct.toFixed(1)}%
              </span>
              <span className="block text-xs text-on-surface-variant mt-0.5">District Outbreak Likelihood</span>
            </div>

            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-bold tracking-wider ${riskDetails.colorClass}`}
            >
              <span className="material-symbols-outlined text-base" aria-hidden="true">
                {riskDetails.icon}
              </span>
              <span>{riskDetails.label}</span>
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-surface-container-lowest/40 border border-outline-variant/30 text-on-surface-variant text-sm">
            <span className="font-semibold text-error">Forecast unavailable</span>
            <span className="block text-xs text-on-surface-variant/70 mt-1">
              Data for this disease could not be retrieved for the selected period.
            </span>
          </div>
        )}

        {/* Farmer Simple Meaning */}
        {isValid && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              Risk Assessment
            </h3>
            <p className="text-sm text-on-surface-variant leading-relaxed">{riskDetails.meaning}</p>
          </div>
        )}

        {/* Preventive Guidance */}
        {isValid && (
          <div className="space-y-2 pt-2 border-t border-outline-variant/20">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              Recommended Preventive Measures
            </h3>
            <ul className="space-y-1.5 text-xs text-on-surface-variant">
              {riskDetails.guidance.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-primary font-bold">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Farmer-Safe Data Provenance Caution */}
      {isValid && (
        <div className="pt-3 border-t border-outline-variant/20 text-xs text-on-surface-variant flex items-start gap-2">
          <span className="material-symbols-outlined text-sm text-amber-400 shrink-0 mt-0.5" aria-hidden="true">
            {provenance && typeof provenance.fallback_applied === 'boolean'
              ? provenance.fallback_applied
                ? 'info'
                : 'check_circle'
              : 'help_outline'}
          </span>
          <span>
            {provenance && typeof provenance.fallback_applied === 'boolean'
              ? provenance.fallback_applied
                ? 'Some forecast inputs use historical reference data because current-period data was unavailable. Interpret this forecast with additional care.'
                : 'Forecast inputs are available for the selected period.'
              : 'Forecast input-source information is unavailable.'}
          </span>
        </div>
      )}
    </section>
  );
}
