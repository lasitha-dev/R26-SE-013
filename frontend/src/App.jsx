import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import SmartDiagnostics from './features/SmartDiagnostics/index'
import HealthAnomalyRoutes from './features/HealthAnomaly/HealthAnomalyRoutes.jsx'
import VetLayout from './shared_components/VetLayout.jsx'
import VetLogin from './shared_components/VetLogin.jsx'
import VetRegistration from './shared_components/VetRegistration.jsx'
import VetRegistrationSuccess from './shared_components/VetRegistrationSuccess.jsx'
import VetDashboard from './shared_components/VetDashboard.jsx'
import VetAssignedFarms from './shared_components/VetAssignedFarms.jsx'
import VetClinicalRecords from './features/SmartDiagnostics/screens/VetClinicalRecords.jsx'
import VetSettings from './shared_components/VetSettings.jsx'
import VetFarmCattleView from './shared_components/VetFarmCattleView.jsx'
import GeospatialLayout from './features/GeospatialMap/GeospatialLayout.jsx'
import OutbreakMapPage from './features/GeospatialMap/pages/OutbreakMapPage.jsx'
import MyAreaPage from './features/GeospatialMap/pages/MyAreaPage.jsx'
import AnalysisTrendsPage from './features/GeospatialMap/pages/AnalysisTrendsPage.jsx'
import RiskForecastingIntegrationAdapter from './features/RiskForecasting/integration/RiskForecastingIntegrationAdapter.jsx'
import { RiskForecastingDemoEntry } from './features/RiskForecasting/RiskForecastingDemoEntry'

export function isDemoPath(pathname) {
  const currentPath = pathname || (typeof window !== 'undefined' ? window.location.pathname : '/');
  return currentPath === '/risk-forecasting-demo' || currentPath.startsWith('/risk-forecasting-demo');
}

export function isDemoEnabled(envVal) {
  const flag = envVal !== undefined ? envVal : import.meta.env?.VITE_FORECASTING_DEMO_ENABLED;
  return flag === 'true';
}

function DemoRouteHandler() {
  if (isDemoEnabled()) {
    return <RiskForecastingDemoEntry />;
  }
  return (
    <div className="max-w-2xl mx-4 sm:mx-auto my-12 p-8 rounded-2xl bg-surface-container border border-outline-variant/40 shadow-xl text-on-surface text-center space-y-4">
      <div className="inline-flex p-3 rounded-2xl bg-surface-container-high text-on-surface-variant">
        <span className="material-symbols-outlined text-3xl" aria-hidden="true">
          block
        </span>
      </div>
      <h1 className="text-xl font-bold text-on-surface">Disease Forecasting Demo Disabled</h1>
      <p className="text-sm text-on-surface-variant leading-relaxed">
        The disease forecasting demonstration mode is currently disabled in this environment. To enable demo mode, configure <code className="px-1.5 py-0.5 rounded bg-surface-container-lowest font-mono text-xs text-primary">VITE_FORECASTING_DEMO_ENABLED=true</code> in your frontend environment settings.
      </p>
    </div>
  );
}

function RoleGuard({ children, allowedRoles }) {
  const role = localStorage.getItem("role");
  
  if (!role || !allowedRoles.includes(role)) {
    if (role === "daph") {
      return <Navigate to="/vet/forecasting" replace />;
    }
    return <Navigate to="/vet/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/health" replace />} />
      <Route path="/health/*" element={<HealthAnomalyRoutes />} />

      {/* Standalone Demo Gateway */}
      <Route path="/risk-forecasting-demo/*" element={<DemoRouteHandler />} />

      {/* Standalone Vet Auth Routes */}
      <Route path="/vet/login" element={<VetLogin />} />
      <Route path="/vet/registration" element={<VetRegistration />} />
      <Route path="/vet/registration-success" element={<VetRegistrationSuccess />} />

      {/* Authenticated Vet Portal with dedicated Side Navigation */}
      <Route path="/vet" element={<VetLayout />}>
        <Route index element={
          <RoleGuard allowedRoles={['vet']}>
            <Navigate to="dashboard" replace />
          </RoleGuard>
        } />
        <Route path="dashboard" element={
          <RoleGuard allowedRoles={['vet']}>
            <VetDashboard />
          </RoleGuard>
        } />
        <Route path="diagnostics" element={
          <RoleGuard allowedRoles={['vet']}>
            <SmartDiagnostics />
          </RoleGuard>
        } />
        <Route path="geospatial" element={
          <RoleGuard allowedRoles={['vet']}>
            <GeospatialLayout />
          </RoleGuard>
        }>
          <Route index element={<OutbreakMapPage />} />
          <Route path="my-area" element={<MyAreaPage />} />
          <Route path="analysis" element={<AnalysisTrendsPage />} />
        </Route>
        <Route path="forecasting" element={<RiskForecastingIntegrationAdapter />} />
        <Route path="assigned-farms" element={
          <RoleGuard allowedRoles={['vet']}>
            <VetAssignedFarms />
          </RoleGuard>
        } />
        <Route path="farm/:farmId" element={
          <RoleGuard allowedRoles={['vet']}>
            <VetFarmCattleView />
          </RoleGuard>
        } />
        <Route path="clinical-records" element={
          <RoleGuard allowedRoles={['vet']}>
            <VetClinicalRecords />
          </RoleGuard>
        } />
        <Route path="settings" element={
          <RoleGuard allowedRoles={['vet']}>
            <VetSettings />
          </RoleGuard>
        } />
      </Route>

      {/* Redirect old diagnostics route to Vet Diagnostics */}
      <Route path="/diagnostics" element={<Navigate to="/vet/diagnostics" replace />} />

      <Route path="*" element={<div className="p-6 text-on-surface">Not Found</div>} />
    </Routes>
  )
}

