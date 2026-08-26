import React from 'react';
import PropTypes from 'prop-types';
import { useDemoForecastingAuth } from '../../hooks/useDemoForecastingAuth.js';
import {
  useDemoFarms,
  useDemoSurveillanceRecords,
  useDemoAlerts,
  useDemoResponseTasks,
} from '../../hooks/useDemoOperationalData.js';
import { RiskForecastingFeature } from '../../RiskForecastingFeature.jsx';
import { validateViewerContext, ROLES } from '../../contracts/viewerContext.js';

/**
 * DemoForecastingOperationalBridge Component
 * Consumes role-optimized operational data hooks and passes structured operationalData
 * state to RiskForecastingFeature during an authenticated demo session.
 */
export function DemoForecastingOperationalBridge({ viewerContext }) {
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;
  const role = normalizedContext ? normalizedContext.role : null;

  const isFarmer = role === ROLES.FARMER;
  const isVet = role === ROLES.VETERINARY_OFFICER;
  const isDaph = role === ROLES.DAPH_OFFICIAL;

  // Request optimization: Enable hooks strictly by role needs
  const farmsHook = useDemoFarms({ enabled: isFarmer || isVet });
  const surveillanceHook = useDemoSurveillanceRecords({ enabled: isVet || isDaph });
  const alertsHook = useDemoAlerts({ enabled: isFarmer || isVet || isDaph });
  const responseTasksHook = useDemoResponseTasks({ enabled: isVet || isDaph });

  const operationalData = {
    farms: farmsHook,
    surveillanceRecords: surveillanceHook,
    alerts: alertsHook,
    responseTasks: responseTasksHook,
  };

  return (
    <RiskForecastingFeature
      viewerContext={viewerContext}
      operationalData={operationalData}
    />
  );
}

DemoForecastingOperationalBridge.propTypes = {
  viewerContext: PropTypes.object,
};
