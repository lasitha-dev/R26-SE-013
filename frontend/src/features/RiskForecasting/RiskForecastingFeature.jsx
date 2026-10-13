import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  validateViewerContext,
} from './contracts/viewerContext';
import { getForecastingNavigation } from './navigation/forecastingNavigation';
import { AccessContextUnavailable } from './components/AccessContextUnavailable';
import { ForecastingSubNavigation } from './components/ForecastingSubNavigation';

import { FarmerDiseaseRisk } from './components/farmer/FarmerDiseaseRisk';
import { FarmerAlertsGuidance } from './components/farmer/FarmerAlertsGuidance';
import { VeterinaryForecastOverview } from './components/veterinary/VeterinaryForecastOverview';
import { VeterinarySurveillanceDashboard } from './components/veterinary/VeterinarySurveillanceDashboard';
import { VeterinaryDistrictForecasts } from './components/veterinary/VeterinaryDistrictForecasts';
import { VeterinaryAdvisoryCentre } from './components/veterinary/VeterinaryAdvisoryCentre';
import { VeterinaryForecastAdvisoryHistory } from './components/veterinary/VeterinaryForecastAdvisoryHistory';
import { VeterinaryAssignedFollowUps } from './components/veterinary/VeterinaryAssignedFollowUps';
import { DaphSurveillanceOverview } from './components/daph/DaphSurveillanceOverview';
import { DaphNationalForecastOverview } from './components/daph/DaphNationalForecastOverview';
import { DaphFollowUpMonitoring } from './components/daph/DaphFollowUpMonitoring';
import { DaphDistrictForecasts } from './components/daph/DaphDistrictForecasts';
import { DaphDataQuality } from './components/daph/DaphDataQuality';
import { DaphOutbreakMonitor } from './components/daph/DaphOutbreakMonitor';
import { ModelTransparency } from './components/transparency/ModelTransparency';

/**
 * RiskForecastingFeature — Isolated feature-level container for Seasonal Risk Forecasting.
 * Evaluates ViewerContext, resolves authorized sub-navigation items, handles role/scope-aware
 * screen switching, and enforces fail-closed access gating without AppShell or global state dependency.
 *
 * @param {object} props
 * @param {object} props.viewerContext - Primary authorization & role-scope context object.
 */
export function RiskForecastingFeature({ viewerContext, operationalData = null }) {
  // 1. Fail-closed ViewerContext validation
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;
  const role = normalizedContext ? normalizedContext.role : null;

  // 2. Resolve allowed sub-navigation items for current normalized context
  const allowedItems = normalizedContext ? getForecastingNavigation(normalizedContext) : [];

  // 3. User-selected active screen state
  const [userSelectedScreenId, setUserSelectedScreenId] = useState(null);

  // 4. Derive effective authorized active screen ID at render time to prevent transient unauthorized renders
  const isSelectedAllowed = Boolean(
    userSelectedScreenId && allowedItems.some((item) => item.id === userSelectedScreenId)
  );
  const effectiveActiveScreenId = isSelectedAllowed
    ? userSelectedScreenId
    : allowedItems.length > 0
    ? allowedItems[0].id
    : null;

  // 5. Unconditional state synchronization: clear stored selection when it becomes unauthorized
  useEffect(() => {
    if (userSelectedScreenId !== null && !isSelectedAllowed) {
      setUserSelectedScreenId(null);
    }
  }, [userSelectedScreenId, isSelectedAllowed]);

  // 6. Fail-closed early returns for invalid context or empty authorized navigation
  if (!validation.valid) {
    return <AccessContextUnavailable reason={validation.reason} />;
  }

  if (!Array.isArray(allowedItems) || allowedItems.length === 0) {
    return (
      <AccessContextUnavailable reason="No authorized forecasting screens for current context." />
    );
  }

  // Handle user tab selection
  const handleSelectScreen = (screenId) => {
    if (allowedItems.some((item) => item.id === screenId)) {
      setUserSelectedScreenId(screenId);
    }
  };

  // 7. Render child screen based on effectiveActiveScreenId and validated role
  const renderScreenContent = () => {
    switch (effectiveActiveScreenId) {
      case 'disease-risk':
        if (role === ROLES.FARMER) {
          return <FarmerDiseaseRisk viewerContext={normalizedContext} />;
        }
        break;

      case 'alerts-guidance':
        if (role === ROLES.FARMER) {
          return (
            <FarmerAlertsGuidance
              viewerContext={normalizedContext}
              operationalData={
                operationalData
                  ? { farms: operationalData.farms, alerts: operationalData.alerts }
                  : null
              }
            />
          );
        }
        break;

      case 'forecast-overview':
        if (role === ROLES.VETERINARY_OFFICER) {
          return <VeterinaryForecastOverview viewerContext={normalizedContext} />;
        }
        break;

      case 'assigned-follow-ups':
        if (role === ROLES.VETERINARY_OFFICER) {
          return <VeterinaryAssignedFollowUps viewerContext={normalizedContext} />;
        }
        break;

      case 'surveillance-dashboard':
        if (role === ROLES.VETERINARY_OFFICER) {
          return (
            <VeterinarySurveillanceDashboard
              viewerContext={normalizedContext}
              operationalData={operationalData}
            />
          );
        }
        break;

      case 'district-forecasts':
        if (role === ROLES.VETERINARY_OFFICER) {
          return <VeterinaryDistrictForecasts viewerContext={normalizedContext} />;
        }
        if (role === ROLES.DAPH_OFFICIAL) {
          return <DaphDistrictForecasts viewerContext={normalizedContext} />;
        }
        break;

      case 'outbreak-monitor':
        if (role === ROLES.DAPH_OFFICIAL) {
          return <DaphOutbreakMonitor viewerContext={normalizedContext} />;
        }
        break;

      case 'advisory-centre':
        if (role === ROLES.VETERINARY_OFFICER) {
          return <VeterinaryAdvisoryCentre viewerContext={normalizedContext} />;
        }
        break;

      case 'history':
        if (role === ROLES.VETERINARY_OFFICER) {
          return <VeterinaryForecastAdvisoryHistory viewerContext={normalizedContext} />;
        }
        break;

      case 'national-overview':
        if (role === ROLES.DAPH_OFFICIAL) {
          return <DaphNationalForecastOverview viewerContext={normalizedContext} />;
        }
        break;

      case 'follow-up-monitoring':
        if (role === ROLES.DAPH_OFFICIAL) {
          return <DaphFollowUpMonitoring viewerContext={normalizedContext} />;
        }
        break;

      case 'surveillance-overview':
        if (role === ROLES.DAPH_OFFICIAL) {
          return (
            <DaphSurveillanceOverview
              viewerContext={normalizedContext}
              operationalData={
                operationalData
                  ? {
                      surveillanceRecords: operationalData.surveillanceRecords,
                      alerts: operationalData.alerts,
                      responseTasks: operationalData.responseTasks,
                    }
                  : null
              }
            />
          );
        }
        break;

      case 'data-quality':
        if (role === ROLES.DAPH_OFFICIAL) {
          return <DaphDataQuality viewerContext={normalizedContext} />;
        }
        break;

      case 'model-transparency':
        return <ModelTransparency viewerContext={normalizedContext} />;

      default:
        break;
    }

    // Unmapped/unknown item fallback fail-closed
    return <AccessContextUnavailable reason="Screen implementation unavailable." />;
  };

  return (
    <div className="w-full min-w-0 space-y-6">
      <ForecastingSubNavigation
        items={allowedItems}
        activeItem={effectiveActiveScreenId}
        onSelect={handleSelectScreen}
      />
      <div className="w-full min-w-0">{renderScreenContent()}</div>
    </div>
  );
}

RiskForecastingFeature.propTypes = {
  viewerContext: PropTypes.object,
  operationalData: PropTypes.object,
};
