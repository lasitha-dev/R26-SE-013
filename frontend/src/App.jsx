import React from 'react'
import SmartDiagnostics from './features/SmartDiagnostics/index'
import { Navigate, Route, Routes } from 'react-router-dom'

import HealthAnomalyRoutes from './features/HealthAnomaly/HealthAnomalyRoutes.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/health" replace />} />
      <Route path="/health/*" element={<HealthAnomalyRoutes />} />
      <Route path="/diagnostics" element={<SmartDiagnostics />} />
      <Route path="*" element={<div className="p-6 text-on-surface">Not Found</div>} />
    </Routes>
  )
}

