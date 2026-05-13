import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import HealthAnomalyRoutes from './features/HealthAnomaly/HealthAnomalyRoutes.jsx'
import PageLinksBar from './shared_components/PageLinksBar.jsx'

export default function App() {
  return (
    <div className="h-full pb-12">
      <Routes>
        <Route path="/" element={<Navigate to="/health" replace />} />
        <Route path="/health/*" element={<HealthAnomalyRoutes />} />
        <Route path="*" element={<div className="p-6">Not Found</div>} />
      </Routes>

      <PageLinksBar />
    </div>
  )
}
