import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  PERMISSIONS,
  validateViewerContext,
  hasForecastingPermission,
} from '../../contracts/viewerContext';
import { AccessContextUnavailable } from '../AccessContextUnavailable';
import {
  listForecastDistricts,
  listForecastRecords,
  listAdvisories,
  listNotificationBatches,
} from '../../services/riskForecastingWorkflowApi';
import { DaphFollowUpComposer } from './DaphFollowUpComposer';

/**
 * Centralized Backend Bound Limitation Constant.
 * Phase 9 Integration Limitation: Backend request schema bounds year validation to 2017-2030.
 */
export const BACKEND_BOUND_YEARS = Object.freeze({
  min: 2017,
  max: 2030,
});

/**
 * Risk tier order ranking for deterministic priority sorting (HIGH > MEDIUM > LOW > No Record).
 */
const RISK_TIER_RANK = Object.freeze({
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
  NO_RECORD: 0,
});

/**
 * Formats a month number (1-12) to full English month name fallback.
 */
function getMonthNameFallback(monthNum) {
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  return months[(monthNum - 1) % 12] || `Month ${monthNum}`;
}

/**
 * Helper to determine latest available period from official records:
 * target_year DESC, target_month DESC, generated_at DESC.
 */
function findLatestRecordPeriod(records) {
  if (!Array.isArray(records) || records.length === 0) {
    return { year: null, month: null };
  }
  let latest = records[0];
  for (let i = 1; i < records.length; i++) {
    const r = records[i];
    const yearDiff = (r.target_year || 0) - (latest.target_year || 0);
    if (yearDiff > 0) {
      latest = r;
    } else if (yearDiff === 0) {
      const monthDiff = (r.target_month || 0) - (latest.target_month || 0);
      if (monthDiff > 0) {
        latest = r;
      } else if (monthDiff === 0 && r.generated_at && latest.generated_at) {
        if (new Date(r.generated_at) > new Date(latest.generated_at)) {
          latest = r;
        }
      }
    }
  }
  return { year: latest.target_year ?? null, month: latest.target_month ?? null };
}

/**
 * DaphNationalForecastOverview Component.
 *
 * Professional, read-only DAPH Official national/district Disease Forecasting oversight workspace.
 * Provides visibility into district risk predictions, veterinary advisory statuses, and simulated
 * notification batch summaries while enforcing strict fail-closed access gating and zero PII exposure.
 *
 * @param {object} props
 * @param {object} props.viewerContext - Authoritative ViewerContext object.
 */
export function DaphNationalForecastOverview({ viewerContext }) {
  // 1. Authorization Access Gating (Amendment 7)
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;

  const isDaphOfficial = normalizedContext?.role === ROLES.DAPH_OFFICIAL;
  const isNationalScope =
    normalizedContext?.authorization?.scopeLevel === SCOPE_LEVELS.NATIONAL ||
    normalizedContext?.authorization?.scopeLevel === SCOPE_LEVELS.PROVINCE ||
    normalizedContext?.authorization?.scopeLevel === SCOPE_LEVELS.DISTRICT;

  // 2. State Management
  const [districtList, setDistrictList] = useState([]);
  const [monthNamesList, setMonthNamesList] = useState([]);
  const [allRecords, setAllRecords] = useState([]);
  const [advisories, setAdvisories] = useState([]);
  const [notificationBatches, setNotificationBatches] = useState([]);

  const [selectedDisease, setSelectedDisease] = useState('ALL'); // 'ALL' | 'FMD' | 'LSD'
  const [selectedYear, setSelectedYear] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(null);
  const [riskFilter, setRiskFilter] = useState('ALL'); // 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NO_RECORD'
  const [advisoryFilter, setAdvisoryFilter] = useState('ALL'); // 'ALL' | 'NO_ADVISORY' | 'DRAFT' | 'REVIEW_READY' | 'APPROVED' | 'CANCELLED'
  const [followUpOnly, setFollowUpOnly] = useState(false);

  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  const [selectedDetailRow, setSelectedDetailRow] = useState(null);
  const [composingForecastRecord, setComposingForecastRecord] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [operationalWarning, setOperationalWarning] = useState(null);
  const [lastLoadedAt, setLastLoadedAt] = useState(null);

  // Active AbortController ref for race-condition safeguarding
  const abortControllerRef = useRef(null);

  // 3. Data Fetching Handler
  const fetchData = useCallback(async () => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);
    setOperationalWarning(null);

    try {
      // Step A: Fetch Authoritative District Directory (Amendment 6)
      let fetchedDistricts = [];
      let fetchedMonths = [];
      try {
        const districtsRes = await listForecastDistricts({ signal: controller.signal });
        if (controller.signal.aborted) return;
        fetchedDistricts = districtsRes?.districts || [];
        fetchedMonths = districtsRes?.month_names || [];
      } catch (distErr) {
        if (controller.signal.aborted) return;
        fetchedDistricts = [
          'Ampara', 'Anuradhapura', 'Badulla', 'Batticaloa', 'Colombo', 'Galle', 'Gampaha',
          'Hambantota', 'Jaffna', 'Kalutara', 'Kandy', 'Kegalle', 'Kilinochchi', 'Kurunegala',
          'Mannar', 'Matale', 'Matara', 'Monaragala', 'Mullaitivu', 'Nuwara Eliya', 'Polonnaruwa',
          'Puttalam', 'Ratnapura', 'Trincomalee', 'Vavuniya',
        ];
        fetchedMonths = [
          'January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December',
        ];
      }
      setDistrictList(fetchedDistricts);
      setMonthNamesList(fetchedMonths);

      // Step B: Fetch Official Forecast Records (Complete set for national summary, Amendment 2)
      let fetchedRecords = [];
      try {
        const recordsRes = await listForecastRecords(
          { limit: 200, offset: 0 },
          { signal: controller.signal }
        );
        if (controller.signal.aborted) return;
        fetchedRecords = recordsRes?.records || [];
      } catch (recErr) {
        if (controller.signal.aborted) return;
        fetchedRecords = [];
      }
      setAllRecords(fetchedRecords);

      // Automatically set default year/month to latest available official record period
      if (fetchedRecords.length > 0) {
        const latestPeriod = findLatestRecordPeriod(fetchedRecords);
        setSelectedYear((prev) => (prev === null ? latestPeriod.year : prev));
        setSelectedMonth((prev) => (prev === null ? latestPeriod.month : prev));
      }

      // Extract authorized forecast IDs for client-side relationship containment
      const forecastIds = fetchedRecords.map((r) => r.forecast_id).filter(Boolean);

      // Step C & D: Fetch Advisories & Batches with Bounded Concurrency & Partial Failure Protection (Amendment 8)
      let fetchedAdvisories = [];
      let fetchedBatches = [];

      try {
        const [advisoriesResult, batchesResult] = await Promise.allSettled([
          listAdvisories({ limit: 200 }, { signal: controller.signal }),
          listNotificationBatches({ limit: 200 }, { signal: controller.signal }),
        ]);

        if (controller.signal.aborted) return;

        if (advisoriesResult.status === 'rejected' || batchesResult.status === 'rejected') {
          setOperationalWarning(
            'Operational coverage (advisories/notification batches) failed to load or experienced partial failure. Displaying official forecast decision records.'
          );
        }

        const advisoriesRes = advisoriesResult.status === 'fulfilled' ? advisoriesResult.value : { advisories: [] };
        const batchesRes = batchesResult.status === 'fulfilled' ? batchesResult.value : { batches: [] };

        // Contain advisories to authorized forecasts
        const rawAdvisories = advisoriesRes?.advisories || [];
        fetchedAdvisories = rawAdvisories.filter((adv) => forecastIds.includes(adv.forecast_id));

        // Contain batches to authorized advisories
        const advisoryIds = fetchedAdvisories.map((a) => a.advisory_id).filter(Boolean);
        const rawBatches = batchesRes?.batches || [];
        fetchedBatches = rawBatches.filter(
          (b) => advisoryIds.includes(b.advisory_id) || forecastIds.includes(b.forecast_id)
        );
      } catch (opErr) {
        if (controller.signal.aborted) return;
        setOperationalWarning(
          'Operational coverage (advisories/notification batches) failed to load or experienced partial failure. Displaying official forecast decision records.'
        );
      }

      if (controller.signal.aborted) return;

      setAdvisories(fetchedAdvisories);
      setNotificationBatches(fetchedBatches);
      setLastLoadedAt(new Date().toLocaleTimeString());
      setLoading(false);
    } catch (err) {
      if (controller.signal.aborted) return;
      if (err.name !== 'AbortError') {
        setError(err.message || 'Failed to retrieve national forecast overview data.');
      }
      setLoading(false);
    }
  }, []); // Stable fetchData callback on mount

  useEffect(() => {
    if (isDaphOfficial && isNationalScope) {
      fetchData();
    }
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [isDaphOfficial, isNationalScope]);

  // 4. Derived Period & Year Options (Requirement 3: derived from official records)
  const defaultPeriod = useMemo(() => {
    return findLatestRecordPeriod(allRecords);
  }, [allRecords]);

  const effectiveYear = selectedYear ?? defaultPeriod.year;
  const effectiveMonth = selectedMonth ?? defaultPeriod.month;

  const availableYears = useMemo(() => {
    const yearsSet = new Set();
    (Array.isArray(allRecords) ? allRecords : []).forEach((r) => {
      if (r && typeof r.target_year === 'number') {
        yearsSet.add(r.target_year);
      }
    });
    if (effectiveYear !== null && typeof effectiveYear === 'number') {
      yearsSet.add(effectiveYear);
    }
    return Array.from(yearsSet).sort((a, b) => b - a);
  }, [allRecords, effectiveYear]);

  // 5. Maps & Lookup Structures for Forecast <-> Advisory <-> Batch Chaining
  const advisoriesByForecastId = useMemo(() => {
    const map = new Map();
    (Array.isArray(advisories) ? advisories : []).forEach((adv) => {
      if (adv && adv.forecast_id) {
        if (!map.has(adv.forecast_id)) {
          map.set(adv.forecast_id, []);
        }
        map.get(adv.forecast_id).push(adv);
      }
    });
    return map;
  }, [advisories]);

  const batchesByAdvisoryId = useMemo(() => {
    const map = new Map();
    (Array.isArray(notificationBatches) ? notificationBatches : []).forEach((batch) => {
      if (batch && batch.advisory_id) {
        if (!map.has(batch.advisory_id)) {
          map.set(batch.advisory_id, []);
        }
        map.get(batch.advisory_id).push(batch);
      }
    });
    return map;
  }, [notificationBatches]);

  // 6. Complete-Collection Filtering & National Summary Metrics (Amendment 2 & 3 & 1)
  const periodFilteredRecords = useMemo(() => {
    return allRecords.filter((r) => {
      const matchPeriod =
        (effectiveYear === null || r.target_year === Number(effectiveYear)) &&
        (effectiveMonth === null || r.target_month === Number(effectiveMonth));
      const matchDisease =
        selectedDisease === 'ALL' || r.disease === selectedDisease;
      return matchPeriod && matchDisease;
    });
  }, [allRecords, effectiveYear, effectiveMonth, selectedDisease]);

  const summaryMetrics = useMemo(() => {
    const totalRecords = periodFilteredRecords.length;
    let highRisk = 0;
    let mediumRisk = 0;
    let lowRisk = 0;
    let fallbackAppliedCount = 0; // Amendment 1: using exact record.fallback_applied

    periodFilteredRecords.forEach((r) => {
      if (r.risk_level === 'HIGH') highRisk++;
      else if (r.risk_level === 'MEDIUM') mediumRisk++;
      else if (r.risk_level === 'LOW') lowRisk++;

      if (r.fallback_applied === true) {
        fallbackAppliedCount++;
      }
    });

    // Amendment 3: Missing-record semantics for FMD/LSD/All
    const totalDistrictsCount = districtList.length > 0 ? districtList.length : 25;
    let missingCount = 0;
    let missingLabel = '';

    if (selectedDisease === 'FMD') {
      const presentDistricts = new Set(
        periodFilteredRecords.filter((r) => r.disease === 'FMD').map((r) => r.district)
      );
      missingCount = Math.max(0, totalDistrictsCount - presentDistricts.size);
      missingLabel = `Districts without FMD Forecast (out of ${totalDistrictsCount})`;
    } else if (selectedDisease === 'LSD') {
      const presentDistricts = new Set(
        periodFilteredRecords.filter((r) => r.disease === 'LSD').map((r) => r.district)
      );
      missingCount = Math.max(0, totalDistrictsCount - presentDistricts.size);
      missingLabel = `Districts without LSD Forecast (out of ${totalDistrictsCount})`;
    } else {
      // ALL selected: 25 districts x 2 diseases = 50 total possible slots
      const totalSlots = totalDistrictsCount * 2;
      missingCount = Math.max(0, totalSlots - totalRecords);
      missingLabel = `Missing District–Disease Forecasts (out of ${totalSlots})`;
    }

    return {
      totalRecords,
      highRisk,
      mediumRisk,
      lowRisk,
      fallbackAppliedCount,
      missingCount,
      missingLabel,
    };
  }, [periodFilteredRecords, districtList, selectedDisease]);

  // 7. Dynamic Table Rows Construction (Including District-Disease Rows & Missing Slots)
  const sortedTableRows = useMemo(() => {
    const rows = [];
    const totalDistrictsCount = districtList.length > 0 ? districtList.length : 25;
    const effectiveDistricts = districtList.length > 0 ? districtList : [
      'Ampara', 'Anuradhapura', 'Badulla', 'Batticaloa', 'Colombo', 'Galle', 'Gampaha',
      'Hambantota', 'Jaffna', 'Kalutara', 'Kandy', 'Kegalle', 'Kilinochchi', 'Kurunegala',
      'Mannar', 'Matale', 'Matara', 'Monaragala', 'Mullaitivu', 'Nuwara Eliya', 'Polonnaruwa',
      'Puttalam', 'Ratnapura', 'Trincomalee', 'Vavuniya',
    ];

    const diseasesToEvaluate = selectedDisease === 'ALL' ? ['FMD', 'LSD'] : [selectedDisease];

    effectiveDistricts.forEach((dist) => {
      diseasesToEvaluate.forEach((dis) => {
        const record = periodFilteredRecords.find(
          (r) => r.district.toLowerCase() === dist.toLowerCase() && r.disease === dis
        );

        if (record) {
          const linkedAdv = advisoriesByForecastId.get(record.forecast_id) || [];
          const hasApprovedAdv = linkedAdv.some((a) => a.status === 'APPROVED');
          const isHighOrMed = record.risk_level === 'HIGH' || record.risk_level === 'MEDIUM';
          const requiresFollowUp = isHighOrMed && !hasApprovedAdv;

          let advisoryStatusSummary = 'No Advisory';
          if (linkedAdv.length === 1) {
            advisoryStatusSummary = linkedAdv[0].status;
          } else if (linkedAdv.length > 1) {
            advisoryStatusSummary = hasApprovedAdv ? 'APPROVED' : 'Multiple Advisories';
          }

          let batchSummary = null;
          if (linkedAdv.length > 0) {
            const allLinkedBatches = linkedAdv.flatMap(
              (a) => batchesByAdvisoryId.get(a.advisory_id) || []
            );
            if (allLinkedBatches.length > 0) {
              const totalSucceeded = allLinkedBatches.reduce((acc, b) => acc + (b.succeeded_count || 0), 0);
              const totalFailed = allLinkedBatches.reduce((acc, b) => acc + (b.failed_count || 0), 0);
              const totalPending = allLinkedBatches.reduce((acc, b) => acc + (b.pending_count || 0), 0);
              const primaryStatus = allLinkedBatches[0].status;
              batchSummary = {
                batchCount: allLinkedBatches.length,
                status: primaryStatus,
                succeeded: totalSucceeded,
                failed: totalFailed,
                pending: totalPending,
              };
            }
          }

          rows.push({
            id: record.forecast_id,
            district: dist,
            disease: dis,
            target_year: record.target_year,
            target_month: record.target_month,
            probability: record.probability,
            probability_pct: record.probability_pct,
            risk_level: record.risk_level,
            predicted_severity: record.predicted_severity || 'N/A',
            status: record.status,
            data_quality: record.data_quality,
            fallback_applied: record.fallback_applied, // Amendment 1
            source_year: record.source_year,
            source_month: record.source_month,
            data_age_months: record.data_age_months,
            record,
            linkedAdvisories: linkedAdv,
            advisoryStatusSummary,
            requiresFollowUp,
            batchSummary,
            isMissingRecord: false,
          });
        } else {
          // Missing district forecast record slot
          rows.push({
            id: `missing_${dist}_${dis}`,
            district: dist,
            disease: dis,
            target_year: effectiveYear,
            target_month: effectiveMonth,
            probability: 0,
            probability_pct: 0,
            risk_level: 'NO_RECORD',
            predicted_severity: 'N/A',
            status: 'UNAVAILABLE',
            data_quality: 'UNAVAILABLE',
            fallback_applied: false,
            source_year: null,
            source_month: null,
            data_age_months: null,
            record: null,
            linkedAdvisories: [],
            advisoryStatusSummary: 'N/A',
            requiresFollowUp: false,
            batchSummary: null,
            isMissingRecord: true,
          });
        }
      });
    });

    // Filtering table rows
    let filtered = rows;
    if (riskFilter !== 'ALL') {
      filtered = filtered.filter((r) => r.risk_level === riskFilter);
    }
    if (advisoryFilter !== 'ALL') {
      filtered = filtered.filter((r) => {
        if (advisoryFilter === 'NO_ADVISORY') return r.advisoryStatusSummary === 'No Advisory';
        return r.advisoryStatusSummary === advisoryFilter;
      });
    }
    if (followUpOnly) {
      filtered = filtered.filter((r) => r.requiresFollowUp);
    }

    // Deterministic Priority Sorting:
    // 1. Risk Tier Rank (HIGH > MEDIUM > LOW > NO_RECORD)
    // 2. Probability descending
    // 3. District name ascending
    return filtered.sort((a, b) => {
      const rankA = RISK_TIER_RANK[a.risk_level] ?? 0;
      const rankB = RISK_TIER_RANK[b.risk_level] ?? 0;
      if (rankA !== rankB) {
        return rankB - rankA;
      }
      if (a.probability !== b.probability) {
        return b.probability - a.probability;
      }
      return a.district.localeCompare(b.district);
    });
  }, [
    districtList,
    selectedDisease,
    periodFilteredRecords,
    advisoriesByForecastId,
    batchesByAdvisoryId,
    effectiveYear,
    effectiveMonth,
    riskFilter,
    advisoryFilter,
    followUpOnly,
  ]);

  // Paginated Rows for Priority Table
  const paginatedRows = useMemo(() => {
    return sortedTableRows.slice(offset, offset + limit);
  }, [sortedTableRows, offset, limit]);

  // Handlers for Reset and Pagination
  const handleResetFilters = () => {
    setSelectedDisease('ALL');
    setRiskFilter('ALL');
    setAdvisoryFilter('ALL');
    setFollowUpOnly(false);
    setOffset(0);
  };

  // Fail-Closed Access Early Return (Amendment 7)
  if (!validation.valid || !isDaphOfficial || !isNationalScope) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'DAPH National Forecast Overview requires DAPH_OFFICIAL role with verified NATIONAL scope level.'
        }
      />
    );
  }

  return (
    <div className="w-full min-w-0 space-y-6 bg-slate-900 text-slate-100 p-6 rounded-xl border border-slate-800 shadow-2xl">
      {/* 1. Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-slate-800 pb-4 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-emerald-400 text-3xl">travel_explore</span>
            <h1 className="text-2xl font-bold tracking-tight text-white">National Forecast Overview</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40">
              Scope: NATIONAL
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Departmental Disease Forecasting & Operational Advisory Oversight Workspace
          </p>
        </div>

        <div className="flex items-center gap-3">
          {lastLoadedAt && (
            <span className="text-xs text-slate-400 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
              Loaded: {lastLoadedAt}
            </span>
          )}
          <button
            type="button"
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
          >
            <span className={`material-symbols-outlined text-sm ${loading ? 'animate-spin' : ''}`}>refresh</span>
            Refresh Data
          </button>
        </div>
      </div>

      {/* 2. Operational Protection Clarification Banner */}
      <div className="bg-slate-800/60 border border-slate-700/80 rounded-lg p-4 flex items-start gap-3 text-xs text-slate-300">
        <span className="material-symbols-outlined text-amber-400 text-lg shrink-0 mt-0.5">shield</span>
        <div>
          <strong className="text-slate-100 block mb-0.5">Read-Only National Oversight Protection</strong>
          This workspace displays official, immutable persisted forecast records, linked veterinary advisories, and aggregate simulated notification outbox statuses. No PII is exposed, auto-generation of predictions is disabled, and mutation controls are strictly prohibited.
        </div>
      </div>

      {/* 3. Operational Warning Banner (Amendment 8) */}
      {operationalWarning && (
        <div className="bg-amber-950/50 border border-amber-500/40 rounded-lg p-4 flex items-start gap-3 text-xs text-amber-200">
          <span className="material-symbols-outlined text-amber-400 text-lg shrink-0 mt-0.5">warning</span>
          <div>
            <strong className="block mb-0.5">Partial Operational Coverage Warning</strong>
            {operationalWarning}
          </div>
        </div>
      )}

      {/* 4. Filter & Target Period Controls */}
      <div className="bg-slate-800/40 border border-slate-800 rounded-xl p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-3">
          {/* Disease Selector */}
          <div>
            <label htmlFor="disease-filter-select" className="block text-xs font-medium text-slate-400 mb-1">
              Disease Filter
            </label>
            <select
              id="disease-filter-select"
              value={selectedDisease}
              onChange={(e) => {
                setSelectedDisease(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="ALL">All Diseases (FMD & LSD)</option>
              <option value="FMD">Foot-and-Mouth Disease (FMD)</option>
              <option value="LSD">Lumpy Skin Disease (LSD)</option>
            </select>
          </div>

          {/* Target Year Selector (Amendment 4) */}
          <div>
            <label htmlFor="year-filter-select" className="block text-xs font-medium text-slate-400 mb-1">
              Target Year
            </label>
            <select
              id="year-filter-select"
              value={effectiveYear ?? ''}
              onChange={(e) => {
                setSelectedYear(Number(e.target.value));
                setOffset(0);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            >
              {availableYears.length === 0 ? (
                <option value="">No Available Years</option>
              ) : (
                availableYears.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Target Month Selector */}
          <div>
            <label htmlFor="month-filter-select" className="block text-xs font-medium text-slate-400 mb-1">
              Target Month
            </label>
            <select
              id="month-filter-select"
              value={effectiveMonth ?? ''}
              onChange={(e) => {
                setSelectedMonth(Number(e.target.value));
                setOffset(0);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>
                  {monthNamesList[m - 1] || getMonthNameFallback(m)}
                </option>
              ))}
            </select>
          </div>

          {/* Risk Level Filter */}
          <div>
            <label htmlFor="risk-filter-select" className="block text-xs font-medium text-slate-400 mb-1">
              Risk Tier
            </label>
            <select
              id="risk-filter-select"
              value={riskFilter}
              onChange={(e) => {
                setRiskFilter(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="ALL">All Risk Tiers</option>
              <option value="HIGH">HIGH Risk Only</option>
              <option value="MEDIUM">MEDIUM Risk Only</option>
              <option value="LOW">LOW Risk Only</option>
              <option value="NO_RECORD">No Record Only</option>
            </select>
          </div>

          {/* Advisory Coverage Filter */}
          <div>
            <label htmlFor="advisory-filter-select" className="block text-xs font-medium text-slate-400 mb-1">
              Advisory Coverage
            </label>
            <select
              id="advisory-filter-select"
              value={advisoryFilter}
              onChange={(e) => {
                setAdvisoryFilter(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="ALL">All Advisory Statuses</option>
              <option value="APPROVED">APPROVED Advisory</option>
              <option value="REVIEW_READY">REVIEW_READY Advisory</option>
              <option value="DRAFT">DRAFT Advisory</option>
              <option value="NO_ADVISORY">No Advisory Linked</option>
            </select>
          </div>

          {/* Reset Filters */}
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleResetFilters}
              className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-2 px-3 rounded-lg border border-slate-700 font-medium transition flex items-center justify-center gap-1"
            >
              <span className="material-symbols-outlined text-sm">filter_alt_off</span>
              Reset Filters
            </button>
          </div>
        </div>

        {/* Operational Follow-Up Toggle */}
        <div className="flex items-start sm:items-center gap-2 pt-2 border-t border-slate-800">
          <input
            type="checkbox"
            id="follow-up-checkbox"
            checked={followUpOnly}
            onChange={(e) => {
              setFollowUpOnly(e.target.checked);
              setOffset(0);
            }}
            className="rounded bg-slate-900 border-slate-700 text-amber-500 focus:ring-amber-500 mt-0.5 sm:mt-0 shrink-0"
          />
          <label htmlFor="follow-up-checkbox" className="text-xs text-amber-300 font-medium cursor-pointer whitespace-normal break-words">
            Display Operational Follow-up Required Only (Medium/High Risk without Approved Vet Advisory)
          </label>
        </div>
      </div>

      {/* 5. Summary Metric Cards (Complete-Collection Summary, Amendment 2 & 3 & 1) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5">
          <span className="text-xs text-slate-400 font-medium block">Total Forecast Records</span>
          <span className="text-2xl font-bold text-white mt-1 block">{summaryMetrics.totalRecords}</span>
          <span className="text-[10px] text-slate-500">Selected target period</span>
        </div>

        <div className="bg-rose-950/30 border border-rose-500/30 rounded-xl p-3.5">
          <span className="text-xs text-rose-300 font-medium block">HIGH Risk Districts</span>
          <span className="text-2xl font-bold text-rose-400 mt-1 block">{summaryMetrics.highRisk}</span>
          <span className="text-[10px] text-rose-500">t ≥ 0.40 outbreak prob</span>
        </div>

        <div className="bg-amber-950/30 border border-amber-500/30 rounded-xl p-3.5">
          <span className="text-xs text-amber-300 font-medium block">MEDIUM Risk Districts</span>
          <span className="text-2xl font-bold text-amber-400 mt-1 block">{summaryMetrics.mediumRisk}</span>
          <span className="text-[10px] text-amber-500">Elevated risk tier</span>
        </div>

        <div className="bg-emerald-950/30 border border-emerald-500/30 rounded-xl p-3.5">
          <span className="text-xs text-emerald-300 font-medium block">LOW Risk Districts</span>
          <span className="text-2xl font-bold text-emerald-400 mt-1 block">{summaryMetrics.lowRisk}</span>
          <span className="text-[10px] text-emerald-500">Routine surveillance</span>
        </div>

        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5">
          <span className="text-xs text-slate-400 font-medium block">Fallback Data Applied</span>
          <span className="text-2xl font-bold text-amber-300 mt-1 block">{summaryMetrics.fallbackAppliedCount}</span>
          <span className="text-[10px] text-slate-500">fallback_applied = true</span>
        </div>

        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5">
          <span className="text-xs text-slate-400 font-medium block whitespace-normal break-words" title={summaryMetrics.missingLabel}>
            {summaryMetrics.missingLabel}
          </span>
          <span className="text-2xl font-bold text-slate-300 mt-1 block">{summaryMetrics.missingCount}</span>
          <span className="text-[10px] text-slate-500">Un-generated slots</span>
        </div>
      </div>

      {/* 6. Deterministic Priority District Table */}
      <div className="bg-slate-800/30 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-slate-400 text-lg">format_list_bulleted</span>
            <h2 className="text-sm font-semibold text-white">District Priority Assessment Matrix</h2>
          </div>
          <span className="text-xs text-slate-400">
            Showing {paginatedRows.length} of {sortedTableRows.length} matching district entries
          </span>
        </div>

        {loading ? (
          <div className="p-6 md:p-12 text-center text-slate-400 flex flex-col items-center justify-center gap-2">
            <span className="material-symbols-outlined text-3xl animate-spin text-emerald-400">sync</span>
            <span className="text-sm font-medium">Loading official national forecast records...</span>
          </div>
        ) : error ? (
          <div className="p-6 md:p-8 text-center text-rose-300 flex flex-col items-center justify-center gap-2">
            <span className="material-symbols-outlined text-3xl text-rose-400">error</span>
            <span className="text-sm font-medium">{error}</span>
          </div>
        ) : (allRecords.length === 0 || paginatedRows.length === 0) ? (
          <div className="p-6 md:p-12 text-center text-slate-400 flex flex-col items-center justify-center gap-2">
            <span className="material-symbols-outlined text-3xl text-slate-500">find_in_page</span>
            <span className="text-sm font-medium text-slate-300">No official forecast records found for selected criteria.</span>
            <p className="text-xs text-slate-500 max-w-md mt-1">
              Auto-generation of predictions is prohibited in the DAPH oversight workspace. Predictions must originate from authorized backend runs.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
                  <th className="py-3 px-3 w-10 text-center">Rank</th>
                  <th className="py-3 px-3">District</th>
                  <th className="py-3 px-3">Disease</th>
                  <th className="py-3 px-3">Target Period</th>
                  <th className="py-3 px-[#10b981] text-right">Probability</th>
                  <th className="py-3 px-3 text-center">Risk Tier</th>
                  <th className="py-3 px-3 text-center">Severity</th>
                  <th className="py-3 px-3 text-center">Advisory Coverage</th>
                  <th className="py-3 px-3 text-center">Simulated Batch</th>
                  <th className="py-3 px-3 text-center">Follow-up</th>
                  <th className="py-3 px-3 text-center">Data Provenance</th>
                  <th className="py-3 px-3 text-center">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {paginatedRows.map((row, idx) => {
                  const globalRank = offset + idx + 1;
                  const isHigh = row.risk_level === 'HIGH';
                  const isMedium = row.risk_level === 'MEDIUM';
                  const isLow = row.risk_level === 'LOW';
                  const isMissing = row.isMissingRecord;

                  return (
                    <tr
                      key={row.id}
                      className={`hover:bg-slate-800/50 transition ${
                        selectedDetailRow?.id === row.id ? 'bg-slate-800/80' : ''
                      }`}
                    >
                      <td className="py-3 px-3 text-center font-mono text-slate-500">{globalRank}</td>
                      <td className="py-3 px-3 font-semibold text-white">{row.district}</td>
                      <td className="py-3 px-3 font-mono font-medium text-slate-300">{row.disease}</td>
                      <td className="py-3 px-3 text-slate-300">
                        {monthNamesList[row.target_month - 1] || getMonthNameFallback(row.target_month)}{' '}
                        {row.target_year}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-bold">
                        {isMissing ? (
                          <span className="text-slate-500">N/A</span>
                        ) : (
                          <span className={isHigh ? 'text-rose-400' : isMedium ? 'text-amber-400' : 'text-emerald-400'}>
                            {(row.probability * 100).toFixed(1)}%
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {isHigh && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                            HIGH
                          </span>
                        )}
                        {isMedium && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                            MEDIUM
                          </span>
                        )}
                        {isLow && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                            LOW
                          </span>
                        )}
                        {isMissing && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                            No Record
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center font-mono text-slate-300">{row.predicted_severity}</td>

                      {/* Advisory Coverage */}
                      <td className="py-3 px-3 text-center">
                        {row.advisoryStatusSummary === 'APPROVED' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-600/40">
                            APPROVED
                          </span>
                        ) : row.advisoryStatusSummary === 'REVIEW_READY' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-950 text-sky-300 border border-sky-600/40">
                            REVIEW_READY
                          </span>
                        ) : row.advisoryStatusSummary === 'DRAFT' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                            DRAFT
                          </span>
                        ) : row.advisoryStatusSummary === 'No Advisory' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-500">
                            No Advisory
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400">
                            {row.advisoryStatusSummary}
                          </span>
                        )}
                      </td>

                      {/* Simulated Batch */}
                      <td className="py-3 px-3 text-center font-mono text-slate-300">
                        {row.batchSummary ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700" title={`Simulated Success: ${row.batchSummary.succeeded}`}>
                            {row.batchSummary.status} ({row.batchSummary.succeeded})
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* Operational Follow-Up */}
                      <td className="py-3 px-3 text-center">
                        {row.requiresFollowUp ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse" title="High/Medium risk without an approved Vet advisory">
                            Required
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* Data Provenance (Amendment 1: fallback_applied) */}
                      <td className="py-3 px-3 text-center">
                        {isMissing ? (
                          <span className="text-slate-600">—</span>
                        ) : row.fallback_applied ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-amber-950/80 text-amber-300 border border-amber-600/40" title={`Data quality: ${row.data_quality}`}>
                            Fallback Proxy
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400" title={`Data quality: ${row.data_quality}`}>
                            Exact Period
                          </span>
                        )}
                      </td>

                      {/* View Details Action */}
                      <td className="py-3 px-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            type="button"
                            onClick={() => setSelectedDetailRow(row)}
                            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 hover:text-emerald-300 font-medium text-[11px] border border-slate-700 transition"
                          >
                            View
                          </button>
                          {!row.isMissingRecord && Boolean(row.record?.forecast_id) && String(row.record.forecast_id).trim() !== '' && (
                            <button
                              type="button"
                              onClick={() => setComposingForecastRecord(row.record)}
                              className="px-2.5 py-1 rounded bg-amber-950/80 hover:bg-amber-900 text-amber-300 hover:text-amber-200 font-semibold text-[11px] border border-amber-600/40 transition"
                              title="Issue operational follow-up to Veterinary Officer"
                            >
                              Follow-up
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        <div className="px-4 py-3 border-t border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div className="text-xs text-slate-400">
            Showing Page {Math.floor(offset / limit) + 1} of {Math.ceil(sortedTableRows.length / limit) || 1}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
              disabled={offset === 0}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
            >
              Previous Page
            </button>
            <button
              type="button"
              onClick={() => setOffset((prev) => (prev + limit < sortedTableRows.length ? prev + limit : prev))}
              disabled={offset + limit >= sortedTableRows.length}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
            >
              Next Page
            </button>
          </div>
        </div>
      </div>

      {/* 7. Read-Only District Detail Panel / Drawer (Amendment 10) */}
      {selectedDetailRow && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end p-4 sm:p-6">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-y-auto p-6 space-y-6 flex flex-col justify-between">
            <div className="space-y-6">
              {/* Drawer Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-lg font-bold text-white">
                    {selectedDetailRow.district} — {selectedDetailRow.disease}
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Target Period: {monthNamesList[selectedDetailRow.target_month - 1] || getMonthNameFallback(selectedDetailRow.target_month)}{' '}
                    {selectedDetailRow.target_year}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedDetailRow(null)}
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 transition"
                >
                  <span className="material-symbols-outlined text-lg">close</span>
                </button>
              </div>

              {selectedDetailRow.isMissingRecord ? (
                <div className="p-6 bg-slate-800/40 rounded-xl border border-slate-800 text-center space-y-2">
                  <span className="material-symbols-outlined text-4xl text-slate-600">hide_source</span>
                  <h4 className="text-sm font-semibold text-slate-300">No Official Forecast Decision Record</h4>
                  <p className="text-xs text-slate-500">
                    There is currently no official persisted forecast record for {selectedDetailRow.district} ({selectedDetailRow.disease}) in {selectedDetailRow.target_year}-{selectedDetailRow.target_month}.
                  </p>
                </div>
              ) : (
                <>
                  {/* Forecast Metadata */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                      Authoritative Forecast Record Metadata
                    </h4>
                    <div className="grid grid-cols-2 gap-3 text-xs bg-slate-800/40 p-4 rounded-xl border border-slate-800">
                      <div>
                        <span className="text-slate-500 block">Forecast Record ID</span>
                        <span className="font-mono text-slate-200">{selectedDetailRow.record.forecast_id}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Outbreak Probability</span>
                        <span className="font-mono font-bold text-emerald-400">
                          {(selectedDetailRow.record.probability * 100).toFixed(2)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Authoritative Risk Tier</span>
                        <span className="font-semibold text-white">{selectedDetailRow.record.risk_level}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Predicted Severity</span>
                        <span className="font-semibold text-white">{selectedDetailRow.record.predicted_severity || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Lifecycle Status</span>
                        <span className="font-mono text-slate-300">{selectedDetailRow.record.status}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Model Architecture Variant</span>
                        <span className="font-mono text-slate-300">{selectedDetailRow.record.model_variant}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Data Quality Classification</span>
                        <span className="font-mono text-slate-300">{selectedDetailRow.record.data_quality}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Fallback Proxy Applied</span>
                        <span className="font-semibold text-amber-300">
                          {selectedDetailRow.record.fallback_applied ? 'YES (Fallback Proxy)' : 'NO (Exact Period)'}
                        </span>
                      </div>
                      {selectedDetailRow.record.source_year && (
                        <div>
                          <span className="text-slate-500 block">Source Data Period</span>
                          <span className="font-mono text-slate-300">
                            {selectedDetailRow.record.source_year}-{selectedDetailRow.record.source_month}
                          </span>
                        </div>
                      )}
                      {selectedDetailRow.record.data_age_months !== null && (
                        <div>
                          <span className="text-slate-500 block">Proxy Data Age</span>
                          <span className="font-mono text-slate-300">{selectedDetailRow.record.data_age_months} months</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Linked Veterinary Advisories Aggregate (Amendment 10: No PII) */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                      Linked Veterinary Advisory Aggregate Status
                    </h4>
                    {selectedDetailRow.linkedAdvisories.length === 0 ? (
                      <div className="p-3 bg-slate-800/40 rounded-lg text-xs text-slate-400">
                        No veterinary advisory draft or approved record linked to this forecast.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {selectedDetailRow.linkedAdvisories.map((adv) => (
                          <div key={adv.advisory_id} className="p-3 bg-slate-800/40 rounded-lg border border-slate-800 text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-medium text-slate-200">{adv.advisory_id}</span>
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-200">
                                {adv.status}
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 pt-1">
                              <div>Recipient Scope: <strong className="text-slate-200">{adv.recipient_scope}</strong></div>
                              <div>Approved By: <strong className="text-slate-200">{adv.approved_by || 'Unapproved'}</strong></div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Mandated Disclaimers */}
                  <div className="space-y-2 text-[11px] text-slate-400 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
                    <p className="font-semibold text-slate-300">Scientific Disclaimer:</p>
                    <p>{selectedDetailRow.record.disclaimer}</p>
                    <p className="pt-2 border-t border-slate-800/60 text-slate-500">
                      Standalone notification simulation disclaimers apply. Simulated delivery success confirms mock provider execution only and does not confirm receipt by farmers.
                    </p>
                  </div>
                </>
              )}
            </div>

            <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
              {!selectedDetailRow.isMissingRecord && Boolean(selectedDetailRow.record?.forecast_id) && String(selectedDetailRow.record.forecast_id).trim() !== '' ? (
                <button
                  type="button"
                  onClick={() => {
                    const recordToCompose = selectedDetailRow.record;
                    setSelectedDetailRow(null);
                    setComposingForecastRecord(recordToCompose);
                  }}
                  className="px-3.5 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow transition flex items-center gap-1.5"
                >
                  <span className="material-symbols-outlined text-sm">assignment_add</span>
                  <span>Issue Operational Follow-Up</span>
                </button>
              ) : (
                <div />
              )}
              <button
                type="button"
                onClick={() => setSelectedDetailRow(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 8. Follow-up Issuing Composer Modal */}
      {composingForecastRecord && (
        <DaphFollowUpComposer
          forecastRecord={composingForecastRecord}
          viewerContext={viewerContext}
          onClose={() => setComposingForecastRecord(null)}
          onFollowUpCreated={() => {
            fetchData();
          }}
        />
      )}
    </div>
  );
}

DaphNationalForecastOverview.propTypes = {
  viewerContext: PropTypes.object,
};
