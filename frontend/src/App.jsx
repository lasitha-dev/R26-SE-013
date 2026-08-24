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
import GeospatialMock from './features/GeospatialMap/screens/GeospatialMock.jsx'
import ForecastingMock from './features/RiskForecasting/screens/ForecastingMock.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/health" replace />} />
      <Route path="/health/*" element={<HealthAnomalyRoutes />} />

      {/* Standalone Vet Auth Routes */}
      <Route path="/vet/login" element={<VetLogin />} />
      <Route path="/vet/registration" element={<VetRegistration />} />
      <Route path="/vet/registration-success" element={<VetRegistrationSuccess />} />

      {/* Authenticated Vet Portal with dedicated Side Navigation */}
      <Route path="/vet" element={<VetLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<VetDashboard />} />
        <Route path="diagnostics" element={<SmartDiagnostics />} />
        <Route path="geospatial" element={<GeospatialMock />} />
        <Route path="forecasting" element={<ForecastingMock />} />
        <Route path="assigned-farms" element={<VetAssignedFarms />} />
        <Route path="farm/:farmId" element={<VetFarmCattleView />} />
        <Route path="clinical-records" element={<VetClinicalRecords />} />
        <Route path="settings" element={<VetSettings />} />
      </Route>

      {/* Redirect old diagnostics route to Vet Diagnostics */}
      <Route path="/diagnostics" element={<Navigate to="/vet/diagnostics" replace />} />

      <Route path="*" element={<div className="p-6 text-on-surface">Not Found</div>} />
    </Routes>
  )
}

