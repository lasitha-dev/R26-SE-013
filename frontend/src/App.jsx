import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import SmartDiagnostics from './features/SmartDiagnostics/index'
import HealthAnomalyRoutes from './features/HealthAnomaly/HealthAnomalyRoutes.jsx'
import VetLayout from './shared_components/VetLayout.jsx'
import VetLogin from './features/HealthAnomaly/screens/VetLogin.jsx'
import VetRegistration from './features/HealthAnomaly/screens/VetRegistration.jsx'
import VetRegistrationSuccess from './features/HealthAnomaly/screens/VetRegistrationSuccess.jsx'
import VetDashboard from './features/HealthAnomaly/screens/VetDashboard.jsx'
import VetAssignedFarms from './features/HealthAnomaly/screens/VetAssignedFarms.jsx'
import VetClinicalRecords from './features/HealthAnomaly/screens/VetClinicalRecords.jsx'
import VetSettings from './features/HealthAnomaly/screens/VetSettings.jsx'

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
        <Route path="assigned-farms" element={<VetAssignedFarms />} />
        <Route path="clinical-records" element={<VetClinicalRecords />} />
        <Route path="settings" element={<VetSettings />} />
      </Route>

      {/* AI Smart Diagnostics Workbench */}
      <Route path="/diagnostics" element={<SmartDiagnostics />} />

      <Route path="*" element={<div className="p-6 text-on-surface">Not Found</div>} />
    </Routes>
  )
}

