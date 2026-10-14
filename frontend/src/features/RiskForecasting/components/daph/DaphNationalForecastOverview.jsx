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
import { getDefaultTargetPeriod } from '../../config/forecastPeriod';
import {
  listForecastDistricts,
  listForecastRecords,
  listAdvisories,
  listNotificationBatches,
  generateV2Forecasts,
  getActiveSurveillance,
} from '../../services/riskForecastingWorkflowApi';
import { DaphFollowUpComposer } from './DaphFollowUpComposer';
import { ForecastSourceBadge } from '../ForecastSourceBadge';
import { TierBasisNote } from '../TierBasisNote';
import { OutlookCard } from '../OutlookCard';
import { loadOutlooks, outlookFor, NO_OUTLOOK } from '../../services/outlookLoader';
import { loadSeverityHistory, severityFor, NO_SEVERITY_HISTORY } from '../../services/severityHistoryLoader';
import { SeverityEstimate } from '../SeverityEstimate';
import { describeLastMonthPlain } from '../forecastPresentation';
import { BASELINE_BADGE, describePreviousMonth, formatProbabilityInterval, formatRelativeRisk, isActiveRecord, isBaselineRecord, isV2Record, nextPeriod, periodLabel, selectOfficialRecords } from '../forecastPresentation';

const periodKey = (p) => p.year * 12 + p.month;

const RISK_TIER_RANK = Object.freeze({
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
  NO_RECORD: 0,
});

const SUPERSEDE_PROTECTION_TEXT = Object.freeze({
  HAS_ADVISORY: 'has advisories',
  HAS_FOLLOW_UP: 'has follow-ups',
  WORKFLOW_STATUS: 'already used in a workflow',
  DEPENDENCY_CHECK_UNAVAILABLE: 'dependency check unavailable',
});

function getMonthNameFallback(monthNum) {
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  return months[(monthNum - 1) % 12] || `Month ${monthNum}`;
}



/**
 * DAPH National Forecast Overview Component
 *
 * @param {object} props
 * @param {object} props.viewerContext
 */
export function DaphNationalForecastOverview({ viewerContext }) {
  // 1. Authorization Gate & Context Normalization (Amendment 7)
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.normalizedContext;

  const isDaphOfficial = normalizedContext?.role === ROLES.DAPH_OFFICIAL;
  const hasNationalPermission =
    validation.valid &&
    hasForecastingPermission(viewerContext, PERMISSIONS.FORECASTING_READ_NATIONAL);

  const isNationalScope =
    normalizedContext?.authorization?.scopeLevel === SCOPE_LEVELS.NATIONAL ||
    normalizedContext?.authorization?.scopeLevel === SCOPE_LEVELS.PROVINCE ||
    normalizedContext?.authorization?.scopeLevel === SCOPE_LEVELS.DISTRICT;

  const isDistrictScopeOnly =
    isDaphOfficial &&
    !hasNationalPermission &&
    normalizedContext?.authorization?.scopeLevel === SCOPE_LEVELS.DISTRICT;

  // 2. State Management
  const [selectedYear, setSelectedYear] = useState(() => getDefaultTargetPeriod().year);
  const [selectedMonth, setSelectedMonth] = useState(() => getDefaultTargetPeriod().month);
  const [districtList, setDistrictList] = useState([]);
  const [monthNamesList, setMonthNamesList] = useState([]);
  const [allRecords, setAllRecords] = useState([]);
  const [outlooks, setOutlooks] = useState(NO_OUTLOOK);
  const [storedPeriods, setStoredPeriods] = useState([]);   // months that have a stored forecast
  const [severityHistory, setSeverityHistory] = useState(NO_SEVERITY_HISTORY);
  const [advisories, setAdvisories] = useState([]);
  const [notificationBatches, setNotificationBatches] = useState([]);

  const [selectedDisease, setSelectedDisease] = useState('ALL'); // 'ALL' | 'FMD' | 'LSD'
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
  const [generating, setGenerating] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [generationPreview, setGenerationPreview] = useState(null);
  const generationInFlight = useRef(false);
  const [generationMessage, setGenerationMessage] = useState(null);
  const [activeAlerts, setActiveAlerts] = useState([]);

  // Active AbortController ref for race-condition safeguarding
  const abortControllerRef = useRef(null);

  // 3. Data Fetching Handler
  useEffect(() => {
    let active = true;
    loadSeverityHistory().then((history) => { if (active) setSeverityHistory(history); });
    return () => { active = false; };
  }, []);

  // Months that have a stored forecast (for the Month list). Loaded once, after the table's own request, and not awaited.
  const periodsRequested = useRef(false);
  const loadStoredPeriods = useCallback(async () => {
    if (periodsRequested.current) return;
    periodsRequested.current = true;
    const found = new Map();
    try {
      for (let offsetValue = 0; offsetValue < 1000; offsetValue += 200) {
        const res = await listForecastRecords({ limit: 200, offset: offsetValue });
        const batch = (res?.records || []).filter(isActiveRecord);
        batch.forEach((r) => {
          const year = r.target_year ?? r.targetYear;
          const month = r.target_month ?? r.targetMonth;
          if (year && month) found.set(`${year}-${month}`, { year, month });
        });
        if ((res?.records || []).length < 200) break;
      }
    } catch (_) { /* the list falls back to the default and outlook months */ }
    setStoredPeriods([...found.values()]);
  }, []);

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
      let activeRecords = [];
      try {
        const recordsRes = await listForecastRecords(
          { limit: 200, offset: 0, target_year: Number(selectedYear), target_month: Number(selectedMonth) },
          { signal: controller.signal }
        );
        if (controller.signal.aborted) return;
        activeRecords = (recordsRes?.records || []).filter(isActiveRecord);
        // One official record per disease, district and month; advisories on the others stay linked.
        fetchedRecords = selectOfficialRecords(activeRecords);
      } catch (recErr) {
        if (controller.signal.aborted) return;
        fetchedRecords = [];
      }

      loadStoredPeriods();

      // Only persisted forecast records are displayed. Periods without stored records
      // are shown as "No Record"; no client-side substitute predictions are generated.
      setAllRecords(fetchedRecords);

      // Seasonal Outlook for the same month (stored, or the next month's server-computed preview)
      // (not awaited: the table must not wait for the outlook)
      loadOutlooks({ year: Number(selectedYear), month: Number(selectedMonth), signal: controller.signal }).then((outlookResult) => {
        if (!controller.signal.aborted) setOutlooks(outlookResult);
      });

      // Real-time signal, separate from the forecast: verified cases/deaths recorded this month.
      try {
        const now = new Date();
        const results = await Promise.allSettled(
          ['FMD', 'LSD'].map((disease) =>
            getActiveSurveillance(
              { disease, year: now.getFullYear(), month: now.getMonth() + 1 },
              { signal: controller.signal }
            )
          )
        );
        if (controller.signal.aborted) return;
        const alerts = [];
        results.forEach((res) => {
          if (res.status !== 'fulfilled' || !res.value?.districts) return;
          Object.entries(res.value.districts).forEach(([district, observation]) => {
            if (observation.status === 'CONFIRMED_OUTBREAK') {
              alerts.push({ disease: res.value.disease, district, period: res.value.period, ...observation });
            }
          });
        });
        setActiveAlerts(alerts);
      } catch (_) {
        setActiveAlerts([]); // the alert panel is optional; the forecast table still loads
      }

      // Extract authorized forecast IDs for client-side relationship containment
      const forecastIds = activeRecords.map((r) => r.forecast_id).filter(Boolean);

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
  }, [selectedYear, selectedMonth]); // Re-fetch on target period selection change

  useEffect(() => {
    if (isDaphOfficial && isNationalScope) {
      fetchData();
    }
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [isDaphOfficial, isNationalScope, fetchData]);

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
        (selectedYear === null || (r.target_year ?? r.targetYear) === Number(selectedYear)) &&
        (selectedMonth === null || (r.target_month ?? r.targetMonth) === Number(selectedMonth));
      const matchDisease =
        selectedDisease === 'ALL' || r.disease === selectedDisease;
      return matchPeriod && matchDisease;
    });
  }, [allRecords, selectedYear, selectedMonth, selectedDisease]);

  // 6. Dynamic Table Rows Construction
  const sortedTableRows = useMemo(() => {
    const rows = [];
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
          const linkedAdv = [record.forecast_id, ...(record.related_forecast_ids || [])]
            .flatMap((id) => advisoriesByForecastId.get(id) || []);
          const hasApprovedAdv = linkedAdv.some((a) => a.status === 'APPROVED');
          const isHighOrMed = record.risk_level === 'HIGH' || record.risk_level === 'MEDIUM';
          // Persisted records are authoritative model outputs; proxy-input records keep their
          // provenance badge but are not excluded from operational follow-up.
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
            id: record.forecast_id || record._id,
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
            fallback_applied: record.fallback_applied,
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
          // No persisted forecast record exists for this district/disease/period slot.
          rows.push({
            id: `missing_${dist}_${dis}_${selectedYear}_${selectedMonth}`,
            district: dist,
            disease: dis,
            target_year: Number(selectedYear),
            target_month: Number(selectedMonth),
            probability: null,
            probability_pct: null,
            risk_level: null,
            predicted_severity: '—',
            status: null,
            data_quality: null,
            fallback_applied: false,
            source_year: null,
            source_month: null,
            data_age_months: null,
            record: null,
            outlook: outlookFor(outlooks, dist, dis),
            outlookPreview: outlooks.source === 'preview',
            linkedAdvisories: [],
            advisoryStatusSummary: 'No Advisory',
            requiresFollowUp: false,
            batchSummary: null,
            isMissingRecord: true,
          });
        }
      });
    });

    // Filtering table rows
    let filtered = rows;
    if (riskFilter === 'NO_RECORD') {
      filtered = filtered.filter((r) => r.isMissingRecord);
    } else if (riskFilter !== 'ALL') {
      filtered = filtered.filter((r) => r.risk_level === riskFilter);
    }
    if (advisoryFilter !== 'ALL') {
      filtered = filtered.filter((r) => {
        if (r.isMissingRecord) return false;
        if (advisoryFilter === 'NO_ADVISORY') return r.advisoryStatusSummary === 'No Advisory';
        return r.advisoryStatusSummary === advisoryFilter;
      });
    }
    if (followUpOnly) {
      filtered = filtered.filter((r) => r.requiresFollowUp);
    }

    return filtered.sort((a, b) => {
      if (Boolean(a.isMissingRecord) !== Boolean(b.isMissingRecord)) {
        return a.isMissingRecord ? 1 : -1;
      }
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
    outlooks,
    advisoriesByForecastId,
    batchesByAdvisoryId,
    selectedYear,
    selectedMonth,
    riskFilter,
    advisoryFilter,
    followUpOnly,
  ]);

  // 7. Complete-Collection Filtering & National Summary Metrics
  const summaryMetrics = useMemo(() => {
    const dbRecords = periodFilteredRecords;
    const totalRecords = dbRecords.length;
    let highRisk = 0;
    let mediumRisk = 0;
    let lowRisk = 0;
    let baselineOnly = 0;
    const fallbackAppliedCount = dbRecords.filter((r) => r.fallback_applied).length;

    dbRecords.forEach((r) => {
      if (r.risk_level === 'HIGH') highRisk++;
      else if (r.risk_level === 'MEDIUM') mediumRisk++;
      else if (isBaselineRecord(r)) baselineOnly++; // seasonal baseline, not an assessed LOW tier
      else if (r.risk_level === 'LOW') lowRisk++;
    });

    const totalDistrictsCount = districtList.length > 0 ? districtList.length : 25;
    let missingCount = 0;
    let missingLabel = '';

    if (selectedDisease === 'FMD') {
      const dbDistricts = new Set(
        dbRecords.filter((r) => r.disease === 'FMD').map((r) => r.district)
      );
      missingCount = Math.max(0, totalDistrictsCount - dbDistricts.size);
      missingLabel = `Districts without FMD Forecast (out of ${totalDistrictsCount})`;
    } else if (selectedDisease === 'LSD') {
      const dbDistricts = new Set(
        dbRecords.filter((r) => r.disease === 'LSD').map((r) => r.district)
      );
      missingCount = Math.max(0, totalDistrictsCount - dbDistricts.size);
      missingLabel = `Districts without LSD Forecast (out of ${totalDistrictsCount})`;
    } else {
      const totalSlots = totalDistrictsCount * 2;
      missingCount = Math.max(0, totalSlots - dbRecords.length);
      missingLabel = `Missing District–Disease Combinations (out of ${totalSlots})`;
    }

    return {
      totalRecords,
      highRisk,
      mediumRisk,
      lowRisk,
      baselineOnly,
      fallbackAppliedCount,
      missingCount,
      missingLabel,
    };
  }, [periodFilteredRecords, districtList, selectedDisease]);



  // Paginated Rows for Priority Table
  const paginatedRows = useMemo(() => {
    return sortedTableRows.slice(offset, offset + limit);
  }, [sortedTableRows, offset, limit]);

  // Month list: months with a stored forecast, the forecast month and the outlook month after it; older ones are grouped apart.
  const periodOptions = useMemo(() => {
    const target = getDefaultTargetPeriod();
    const outlookMonth = nextPeriod(target.year, target.month);
    const all = new Map();
    [...storedPeriods, target, { year: Number(selectedYear), month: Number(selectedMonth) }, outlookMonth]
      .forEach((p) => all.set(`${p.year}-${p.month}`, { year: p.year, month: p.month }));
    const hasStored = (p) => storedPeriods.some((q) => q.year === p.year && q.month === p.month);
    const list = [...all.values()]
      .sort((a, b) => periodKey(b) - periodKey(a))
      .map((p) => ({ ...p, outlook: p.year === outlookMonth.year && p.month === outlookMonth.month && !hasStored(p) }));
    const isRecent = (p) => p.outlook || (periodKey(p) <= periodKey(target) && periodKey(p) >= periodKey(target) - 3);
    return { recent: list.filter(isRecent), other: list.filter((p) => !isRecent(p)) };
  }, [storedPeriods, selectedYear, selectedMonth]);

  // Handlers for Reset and Pagination
  const handleResetFilters = () => {
    setSelectedDisease('ALL');
    setRiskFilter('ALL');
    setAdvisoryFilter('ALL');
    const defaultPeriod = getDefaultTargetPeriod();
    setSelectedYear(defaultPeriod.year);
    setSelectedMonth(defaultPeriod.month);
    setFollowUpOnly(false);
    setOffset(0);
  };

  // Step 1: read-only preview. Nothing is written until the official confirms the dialog.
  const handlePreviewGeneration = async () => {
    if (generationInFlight.current) return;
    generationInFlight.current = true;
    setPreviewing(true);
    setGenerationMessage(null);
    try {
      const res = await generateV2Forecasts({ year: selectedYear, month: selectedMonth, dryRun: true });
      setGenerationPreview(res?.summary || {});
    } catch (err) {
      setGenerationMessage({
        tone: 'error',
        text: err?.status === 403 ? 'Only DAPH officials can generate forecasts.' : 'Could not prepare the forecast preview. Please try again.',
      });
    } finally {
      generationInFlight.current = false;
      setPreviewing(false);
    }
  };

  // Step 2: one controlled write, bound to the count the official saw in the preview.
  const handleConfirmGeneration = async () => {
    if (generationInFlight.current || !generationPreview) return;
    generationInFlight.current = true;
    setGenerating(true);
    const confirmedCount = generationPreview.would_supersede ?? 0;
    try {
      const res = await generateV2Forecasts({
        year: selectedYear,
        month: selectedMonth,
        expectedSupersedeCount: confirmedCount,
      });
      const summary = res?.summary || {};
      if (summary.status === 'PARTIAL') {
        const failed = (summary.failed || []).length + (summary.supersede_failed || []).length;
        setGenerationMessage({
          tone: 'error',
          text: `Partly stored: ${summary.saved ?? 0} of ${summary.records ?? 0} records saved, ${failed} step(s) failed and no older records were superseded. Running it again is safe and will complete the rest.`,
        });
      } else {
        setGenerationMessage({
          tone: 'success',
          text: `Stored ${summary.records ?? 0} v2 forecast records for ${summary.target_period}; ${summary.superseded ?? 0} older records marked superseded; ${summary.protected ?? 0} protected records left unchanged.`,
        });
      }
      await fetchData();
    } catch (err) {
      let text = 'Forecast generation failed. Nothing was changed unless stated above. Please try again.';
      if (err?.status === 403) text = 'Only DAPH officials can generate forecasts.';
      else if (err?.status === 409) text = 'The records changed since the preview, so nothing was stored. Please preview again.';
      else if (err?.status === 400) text = 'A fresh preview is required before storing. Please preview again.';
      setGenerationMessage({ tone: 'error', text });
    } finally {
      generationInFlight.current = false;
      setGenerating(false);
      setGenerationPreview(null);
    }
  };

  const handleCancelGeneration = () => {
    if (!generating) setGenerationPreview(null);
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
          <button
            type="button"
            onClick={handlePreviewGeneration}
            disabled={loading || generating || previewing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold border border-emerald-500/50 transition disabled:opacity-50"
            title="Compute and store v2 forecasts for the selected month from public climate data and recorded surveillance"
          >
            <span className={`material-symbols-outlined text-sm ${generating || previewing ? 'animate-spin' : ''}`}>{generating || previewing ? 'sync' : 'model_training'}</span>
            {previewing ? 'Preparing preview…' : generating ? 'Storing…' : `Generate v2 forecasts (${getMonthNameFallback(selectedMonth)} ${selectedYear})`}
          </button>
        </div>
      </div>

      {/* 2. Operational Protection Clarification Banner */}
      <div className="bg-slate-800/60 border border-slate-700/80 rounded-lg p-4 flex items-start gap-3 text-xs text-slate-300">
        <span className="material-symbols-outlined text-amber-400 text-lg shrink-0 mt-0.5">shield</span>
        <div>
          <strong className="text-slate-100 block mb-0.5">Read-Only National Oversight Protection</strong>
          This workspace displays official, immutable persisted forecast records, linked veterinary advisories, and aggregate simulated notification outbox statuses. No PII is exposed. Forecasts are generated only on explicit request (button above) or by the monthly job, and stored records are never edited.
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

      {generationPreview && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="generation-confirm-title">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-6 space-y-4 text-sm text-slate-200">
            <h2 id="generation-confirm-title" className="text-lg font-bold text-white">
              Store v2 forecasts for {getMonthNameFallback(selectedMonth)} {selectedYear}?
            </h2>
            <ul className="space-y-1.5 text-xs">
              <li>
                <strong className="text-white">{generationPreview.records ?? 0}</strong> new forecast records will be stored
                {generationPreview.reused ? ` (${generationPreview.reused} already stored and reused)` : ''}.
              </li>
              <li>
                <strong className="text-white">{generationPreview.would_supersede ?? 0}</strong> older records will be marked
                superseded (never deleted).
              </li>
              <li>
                <strong className="text-white">{generationPreview.protected ?? 0}</strong> older records stay unchanged
                {Object.keys(generationPreview.protected_reasons || {}).length > 0 && (
                  <>
                    {' '}because they are protected:{' '}
                    {Object.entries(generationPreview.protected_reasons).map(([reason, count]) => (
                      <span key={reason} className="mr-2">{count} {SUPERSEDE_PROTECTION_TEXT[reason] || reason}</span>
                    ))}
                  </>
                )}
                .
              </li>
            </ul>
            <p className="text-[11px] text-slate-400">
              Nothing has been written yet. Records with advisories, follow-ups or workflow activity are never superseded.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={handleCancelGeneration}
                disabled={generating}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmGeneration}
                disabled={generating}
                className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold border border-emerald-500/50 disabled:opacity-50"
              >
                {generating ? 'Storing…' : 'Confirm and store'}
              </button>
            </div>
          </div>
        </div>
      )}

      {generationMessage && (
        <div
          role="status"
          className={`rounded-lg p-3 text-xs border ${generationMessage.tone === 'success' ? 'bg-emerald-950/50 border-emerald-500/40 text-emerald-200' : 'bg-rose-950/50 border-rose-500/40 text-rose-200'}`}
        >
          {generationMessage.text}
        </div>
      )}

      {activeAlerts.length > 0 && (
        <div className="bg-rose-950/40 border border-rose-500/40 rounded-lg p-4 text-xs text-rose-200" aria-label="Active outbreak signals">
          <strong className="block mb-1 text-rose-100">Active outbreak signals this month (verified app records)</strong>
          <ul className="space-y-0.5">
            {activeAlerts.map((alert) => (
              <li key={`${alert.disease}-${alert.district}`}>
                {alert.district} — {alert.disease}: {alert.verified_cases} verified case{alert.verified_cases === 1 ? '' : 's'}, {alert.deaths} death{alert.deaths === 1 ? '' : 's'}
              </li>
            ))}
          </ul>
          <span className="block mt-1 text-rose-300/70">Observed facts, shown separately from the forecasts below.</span>
        </div>
      )}

      {/* 4. Filter & Target Period Controls */}
      <div className="bg-slate-800/40 border border-slate-800 rounded-xl p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Month */}
          <div>
            <label htmlFor="national-month-select" className="block text-xs font-medium text-slate-400 mb-1">
              Month
            </label>
            <select
              id="national-month-select"
              value={`${selectedYear}-${selectedMonth}`}
              onChange={(e) => {
                const [year, month] = e.target.value.split('-').map(Number);
                setSelectedYear(year);
                setSelectedMonth(month);
                setOffset(0);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            >
              {periodOptions.recent.map((p) => (
                <option key={`${p.year}-${p.month}`} value={`${p.year}-${p.month}`}>
                  {periodLabel(p.year, p.month)}{p.outlook ? ' (outlook)' : ''}
                </option>
              ))}
              {periodOptions.other.length > 0 && (
                <optgroup label="Other months">
                  {periodOptions.other.map((p) => (
                    <option key={`${p.year}-${p.month}`} value={`${p.year}-${p.month}`}>{periodLabel(p.year, p.month)}</option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>

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
              <option value="NO_RECORD">Not issued yet</option>
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
            Follow-up required only
          </label>
        </div>
      </div>

      {/* 5. Summary Metric Cards (Complete-Collection Summary, Amendment 2 & 3 & 1) */}
      {summaryMetrics.totalRecords === 0 && outlooks.records.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="bg-sky-950/30 border border-sky-500/30 rounded-xl p-3.5" data-testid="outlook-summary-tile">
            <span className="text-xs text-sky-300 font-medium block">Outlook available</span>
            <span className="text-2xl font-bold text-sky-300 mt-1 block">{outlooks.records.length}</span>
            <span className="text-[10px] text-sky-400">
              {outlooks.source === 'preview' ? 'Preview from past years' : `Prepared ${outlooks.records[0].issue_date}`}
            </span>
          </div>
        </div>
      ) : (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5">
          <span className="text-xs text-slate-400 font-medium block">Total Forecast Records</span>
          <span className="text-2xl font-bold text-white mt-1 block">{summaryMetrics.totalRecords}</span>
          <span className="text-[10px] text-slate-500">Selected target period</span>
        </div>

        <div className="bg-rose-950/30 border border-rose-500/30 rounded-xl p-3.5">
          <span className="text-xs text-rose-300 font-medium block">HIGH Risk Districts</span>
          <span className="text-2xl font-bold text-rose-400 mt-1 block">{summaryMetrics.highRisk}</span>
          <span className="text-[10px] text-rose-500">Much higher than usual</span>
        </div>

        <div className="bg-amber-950/30 border border-amber-500/30 rounded-xl p-3.5">
          <span className="text-xs text-amber-300 font-medium block">MEDIUM Risk Districts</span>
          <span className="text-2xl font-bold text-amber-400 mt-1 block">{summaryMetrics.mediumRisk}</span>
          <span className="text-[10px] text-amber-500">Somewhat higher than usual</span>
        </div>

        <div className="bg-emerald-950/30 border border-emerald-500/30 rounded-xl p-3.5">
          <span className="text-xs text-emerald-300 font-medium block">LOW Risk Districts</span>
          <span className="text-2xl font-bold text-emerald-400 mt-1 block">{summaryMetrics.lowRisk}</span>
          <span className="text-[10px] text-emerald-500">Not higher than usual</span>
          {summaryMetrics.baselineOnly > 0 && (
            <span className="block text-[10px] text-slate-400 mt-0.5">
              {summaryMetrics.baselineOnly} more at the usual seasonal level
            </span>
          )}
        </div>

        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5">
          <span className="text-xs text-slate-400 font-medium block">Using the seasonal average</span>
          <span className="text-2xl font-bold text-amber-300 mt-1 block">{summaryMetrics.fallbackAppliedCount}</span>
          <span className="text-[10px] text-slate-500">No recent local reports</span>

        </div>

        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5">
          <span className="text-xs text-slate-400 font-medium block whitespace-normal break-words" title={summaryMetrics.missingLabel}>
            {summaryMetrics.missingLabel}
          </span>
          <span className="text-2xl font-bold text-slate-300 mt-1 block">{summaryMetrics.missingCount}</span>
          <span className="text-[10px] text-slate-500">Not issued yet</span>
        </div>
      </div>
      )}

      {/* 6. Deterministic Priority District Table */}
      <div className="bg-slate-800/30 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-slate-400 text-lg">format_list_bulleted</span>
            <h2 className="text-sm font-semibold text-white">District Priority Assessment Matrix</h2>
          </div>
          <span className="text-xs text-slate-400">
            Showing {paginatedRows.length} of {sortedTableRows.length} matching matrix entries
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
        ) : (paginatedRows.length === 0) ? (
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
                  <th className="py-3 px-3 text-center" title="Usual severity of this district's past outbreak years">Severity if outbreak</th>
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
                  const isBaseline = Boolean(row.record) && isBaselineRecord(row.record);
                  const isLow = row.risk_level === 'LOW' && !isBaseline;
                  const isMissing = row.isMissingRecord;

                  return (
                    <tr
                      key={row.id}
                      className={`hover:bg-slate-800/50 transition ${selectedDetailRow?.id === row.id ? 'bg-slate-800/80' : ''
                        }`}
                    >
                      <td className="py-3 px-3 text-center font-mono text-slate-500">
                        {isMissing ? '—' : globalRank}
                      </td>
                      <td className="py-3 px-3 font-semibold text-white">{row.district}</td>
                      <td className="py-3 px-3 font-mono font-medium text-slate-300">{row.disease}</td>
                      <td className="py-3 px-3 text-slate-300">
                        {row.target_year !== null && row.target_month !== null ? (
                          <>
                            {monthNamesList[row.target_month - 1] || getMonthNameFallback(row.target_month)}{' '}
                            {row.target_year}
                          </>
                        ) : (
                          <span className="text-slate-500 italic">No saved period</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-bold">
                        {row.probability != null ? (
                          <span className={isHigh ? 'text-rose-400' : isMedium ? 'text-amber-400' : isBaseline ? 'text-slate-300' : 'text-emerald-400'}>
                            {(row.probability * 100).toFixed(1)}%
                            {formatRelativeRisk(row.record?.relative_risk) && (
                              <span className="block text-[10px] font-medium text-slate-400">{formatRelativeRisk(row.record.relative_risk)}</span>
                            )}
                            {formatProbabilityInterval(row.record) && (
                              <span className="block text-[10px] font-medium text-slate-500" title="Uncertainty of the probability estimate">{formatProbabilityInterval(row.record)}</span>
                            )}
                          </span>
                        ) : row.outlook ? (
                          <span className="text-slate-300">
                            {(row.outlook.probability * 100).toFixed(1)}%
                            <span className="block text-[10px] font-medium text-sky-300">
                              Outlook{row.outlookPreview ? ' (preview)' : ''}
                            </span>
                          </span>
                        ) : (
                          <span className="text-slate-500">N/A</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {isBaseline ? (
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${BASELINE_BADGE.class}`} title={BASELINE_BADGE.title}>
                            {BASELINE_BADGE.label}
                          </span>
                        ) : isHigh ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                            HIGH
                          </span>
                        ) : isMedium ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                            MEDIUM
                          </span>
                        ) : isLow ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                            LOW
                          </span>
                        ) : isMissing && row.outlook ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/80 text-sky-300 border border-sky-600/40" title="Seasonal outlook: no early-month forecast has been issued yet">
                            OUTLOOK
                          </span>
                        ) : isMissing ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                            No Record
                          </span>
                        ) : null}
                      </td>
                      <td className="py-3 px-3 text-center" title={describeLastMonthPlain(row.record?.previous_month_observation) || undefined}><SeverityEstimate compact entry={severityFor(severityHistory, row.disease, row.district)} /></td>

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
                        ) : (
                          <ForecastSourceBadge record={row.record} />
                        )}
                      </td>

                      {/* View Details Action */}
                      <td className="py-3 px-3 text-center">
                        {isMissing && row.outlook ? (
                          <button
                            type="button"
                            onClick={() => setSelectedDetailRow(row)}
                            className="text-[11px] text-sky-300 hover:text-sky-200 font-medium underline"
                            aria-label={`View outlook for ${row.district} ${row.disease}`}
                          >
                            View outlook
                          </button>
                        ) : isMissing ? (
                          <span className="text-[11px] text-slate-500 font-medium">No record</span>
                        ) : (
                          <div className="flex items-center justify-center gap-1">
                            <button
                              type="button"
                              onClick={() => setSelectedDetailRow(row)}
                              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 hover:text-emerald-300 font-medium text-[11px] border border-slate-700 transition"
                            >
                              View
                            </button>
                            {Boolean(row.id) && (
                              <button
                                type="button"
                                onClick={() => setComposingForecastRecord(row)}
                                className="px-2.5 py-1 rounded bg-amber-950/80 hover:bg-amber-900 text-amber-300 hover:text-amber-200 font-semibold text-[11px] border border-amber-600/40 transition"
                                title="Issue operational follow-up to Veterinary Officer"
                              >
                                Follow-up
                              </button>
                            )}
                          </div>
                        )}
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
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
          <div className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-6 space-y-6 flex flex-col justify-between">
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

              {selectedDetailRow.isMissingRecord && selectedDetailRow.outlook ? (
                <div className="space-y-3">
                  <p className="text-xs text-slate-400">
                    No early-month forecast has been issued for {selectedDetailRow.district} ({selectedDetailRow.disease}) yet.
                    The seasonal outlook below was prepared from historical patterns.
                  </p>
                  <OutlookCard outlook={selectedDetailRow.outlook} preview={selectedDetailRow.outlookPreview} />
                </div>
              ) : selectedDetailRow.isMissingRecord ? (
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
                        <span className="text-slate-500 block">Outbreak Probability</span>
                        <span className="font-mono font-bold text-emerald-400">
                          {(selectedDetailRow.record.probability * 100).toFixed(2)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Authoritative Risk Tier</span>
                        <span className="font-semibold text-white">
                          {isBaselineRecord(selectedDetailRow.record) ? 'Baseline (no elevated signal assessed)' : selectedDetailRow.record.risk_level}
                        </span>
                        <TierBasisNote record={selectedDetailRow.record} className="block text-[11px] text-slate-400 mt-1" />
                      </div>
                      <div>
                        <SeverityEstimate entry={severityFor(severityHistory, selectedDetailRow.disease, selectedDetailRow.district)} />
                        {describeLastMonthPlain(selectedDetailRow.record.previous_month_observation) && (
                          <span className="block text-[11px] text-slate-400 mt-1">{describeLastMonthPlain(selectedDetailRow.record.previous_month_observation)}</span>
                        )}
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
                      {selectedDetailRow.record.fallback_applied && (
                        <div className="col-span-2">
                          <span className="text-slate-400 italic">
                            {isV2Record(selectedDetailRow.record) ? 'Historical baseline (no model features applied)' : 'Historical proxy data used'}
                          </span>
                        </div>
                      )}
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


                </>
              )}
            </div>

            <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
              {!selectedDetailRow.isMissingRecord && Boolean(selectedDetailRow.id) && String(selectedDetailRow.id).trim() !== '' ? (
                <button
                  type="button"
                  onClick={() => {
                    const recordToCompose = selectedDetailRow;
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
