import {
  ROLES,
  PERMISSIONS,
  validateViewerContext,
  hasForecastingPermission,
} from '../contracts/viewerContext';

/**
 * Immutable Canonical Navigation Item Definitions.
 * Only screens classified as UI_READY_API_BLOCKED are defined here.
 * DEFER screens (e.g. Surveillance & Response, History, Reports & Trends) are excluded.
 */
export const NAVIGATION_ITEMS = Object.freeze({
  DISEASE_RISK: Object.freeze({
    id: 'disease-risk',
    label: 'Disease Risk',
    icon: 'health_and_safety',
  }),
  ALERTS_GUIDANCE: Object.freeze({
    id: 'alerts-guidance',
    label: 'Alerts & Guidance',
    icon: 'notifications_active',
  }),
  FORECAST_OVERVIEW: Object.freeze({
    id: 'forecast-overview',
    label: 'Forecast Overview',
    icon: 'query_stats',
  }),
  SURVEILLANCE_DASHBOARD: Object.freeze({
    id: 'surveillance-dashboard',
    label: 'My Surveillance Dashboard',
    icon: 'dashboard',
  }),
  DISTRICT_FORECASTS: Object.freeze({
    id: 'district-forecasts',
    label: 'District Forecasts',
    icon: 'analytics',
  }),
  ADVISORY_CENTRE: Object.freeze({
    id: 'advisory-centre',
    label: 'Advisory Centre',
    icon: 'campaign',
  }),
  SURVEILLANCE_OVERVIEW: Object.freeze({
    id: 'surveillance-overview',
    label: 'Surveillance Overview',
    icon: 'monitoring',
  }),
  DATA_QUALITY: Object.freeze({
    id: 'data-quality',
    label: 'Data Quality',
    icon: 'verified',
  }),
  MODEL_TRANSPARENCY: Object.freeze({
    id: 'model-transparency',
    label: 'Model Transparency',
    icon: 'psychology_alt',
  }),
});

/**
 * Pure helper to derive authorized navigation items based on ViewerContext.
 * Fails closed on invalid context or unknown roles.
 *
 * @param {Object} viewerContext
 * @returns {Array<{ id: string, label: string, icon: string }>} Defensive copy array of navigation items
 */
export function getForecastingNavigation(viewerContext) {
  const { valid, normalizedContext } = validateViewerContext(viewerContext);
  if (!valid || !normalizedContext) {
    return [];
  }

  const items = [];

  if (normalizedContext.role === ROLES.FARMER) {
    items.push({ ...NAVIGATION_ITEMS.DISEASE_RISK });
    items.push({ ...NAVIGATION_ITEMS.ALERTS_GUIDANCE });
  } else if (normalizedContext.role === ROLES.VETERINARY_OFFICER) {
    items.push({ ...NAVIGATION_ITEMS.FORECAST_OVERVIEW });
    items.push({ ...NAVIGATION_ITEMS.DISTRICT_FORECASTS });
    items.push({ ...NAVIGATION_ITEMS.ADVISORY_CENTRE });
    items.push({ ...NAVIGATION_ITEMS.SURVEILLANCE_DASHBOARD });
  } else if (normalizedContext.role === ROLES.DAPH_OFFICIAL) {
    items.push({ ...NAVIGATION_ITEMS.SURVEILLANCE_OVERVIEW });
    items.push({ ...NAVIGATION_ITEMS.DISTRICT_FORECASTS });

    if (hasForecastingPermission(viewerContext, PERMISSIONS.viewDataQuality)) {
      items.push({ ...NAVIGATION_ITEMS.DATA_QUALITY });
    }
  }

  // Capability-gated: Model Transparency
  if (hasForecastingPermission(viewerContext, PERMISSIONS.viewModelTransparency)) {
    items.push({ ...NAVIGATION_ITEMS.MODEL_TRANSPARENCY });
  }

  return items;
}

/**
 * Pure helper to verify whether a specific navigation item ID is authorized for the given viewer.
 *
 * @param {Object} viewerContext
 * @param {string} itemId
 * @returns {boolean}
 */
export function isForecastingNavigationItemAllowed(viewerContext, itemId) {
  if (typeof itemId !== 'string' || itemId.trim() === '') {
    return false;
  }
  const allowedItems = getForecastingNavigation(viewerContext);
  return allowedItems.some((item) => item.id === itemId.trim());
}
