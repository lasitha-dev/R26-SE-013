import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import DashboardLayout from '../../shared_components/DashboardLayout.jsx'
import WellnessDashboard from './screens/WellnessDashboard.jsx'
import RegistrationSuccess from './screens/RegistrationSuccess.jsx'
import SystemLogin from './screens/SystemLogin.jsx'
import RegistrationLanding from './screens/RegistrationLanding.jsx'
import PasswordReset from './screens/PasswordReset.jsx'
import SettingsFarmConfiguration from './screens/SettingsFarmConfiguration.jsx'
import HerdRegistry from './screens/HerdRegistry.jsx'
import AnimalProfileBT8842 from './screens/AnimalProfileBT8842.jsx'
import AddNewAnimal from './screens/AddNewAnimal.jsx'
import WellnessDataIntake from './screens/WellnessDataIntake.jsx'
import SevenDayTriageScan from './screens/SevenDayTriageScan.jsx'
import AiWellnessReport from './screens/AiWellnessReport.jsx'
import NotificationsCenter from './screens/NotificationsCenter.jsx'
import SmartDiagnosticsPage from '../SmartDiagnostics/screens/SmartDiagnosticsPage.jsx'

// Quick responsive mock components for Geospatial and Forecasting modules
function GeospatialMock() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-3xl font-extrabold tracking-tight text-on-surface">Geospatial Intelligence</h2>
        <p className="text-slate-400">Real-time localized outbreak velocities and trajectory mapping.</p>
      </div>
      <div className="glass-card rounded-xl p-8 flex flex-col items-center justify-center min-h-[400px] border border-white/5 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(78,222,163,0.05),transparent_60%)]"></div>
        <span className="material-symbols-outlined text-primary text-6xl mb-4 animate-pulse">map</span>
        <h3 className="text-lg font-bold mb-2">Interactive Heatmap & Tracking UI</h3>
        <p className="text-sm text-slate-400 max-w-md text-center">
          The Geospatial Intelligence module integrates MongoDB geospatial queries to track infectious animal disease spreads across coordinates. Map features will initialize here.
        </p>
      </div>
    </div>
  )
}

function ForecastingMock() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-3xl font-extrabold tracking-tight text-on-surface">Seasonal Risk Forecasting</h2>
        <p className="text-slate-400">Time-series forecasting models integrated with monsoon and climate patterns.</p>
      </div>
      <div className="glass-card rounded-xl p-8 flex flex-col items-center justify-center min-h-[400px] border border-white/5 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(78,222,163,0.05),transparent_60%)]"></div>
        <span className="material-symbols-outlined text-primary text-6xl mb-4 animate-pulse">partly_cloudy_day</span>
        <h3 className="text-lg font-bold mb-2">Predictive Risk Index Dashboard</h3>
        <p className="text-sm text-slate-400 max-w-md text-center">
          The Risk Forecasting module correlates weather data with historical trends to predict outbreak likelihoods. Time-series graphs and probability distributions will initialize here.
        </p>
      </div>
    </div>
  )
}

export default function HealthAnomalyRoutes() {
  return (
    <Routes>
      {/* Auth routes without sidebar/header layout */}
      <Route path="login" element={<SystemLogin />} />
      <Route path="registration" element={<RegistrationLanding />} />
      <Route path="registration-success" element={<RegistrationSuccess />} />
      <Route path="password-reset" element={<PasswordReset />} />

      {/* Main app routes wrapped with DashboardLayout */}
      <Route element={<DashboardLayout />}>
        <Route path="/" element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<WellnessDashboard />} />
        <Route path="settings" element={<SettingsFarmConfiguration />} />
        <Route path="herd-registry" element={<HerdRegistry />} />
        <Route path="animal-profile-bt-8842" element={<AnimalProfileBT8842 />} />
        <Route path="add-new-animal" element={<AddNewAnimal />} />
        <Route path="wellness-data-intake" element={<WellnessDataIntake />} />
        <Route path="7-day-triage-scan" element={<SevenDayTriageScan />} />
        <Route path="ai-smart-diagnosis" element={<SmartDiagnosticsPage />} />
        <Route path="ai-wellness-report" element={<AiWellnessReport />} />
        <Route path="notifications" element={<NotificationsCenter />} />
        
        {/* Placeholder screens for other research domains */}
        <Route path="geospatial" element={<GeospatialMock />} />
        <Route path="forecasting" element={<ForecastingMock />} />
      </Route>

      <Route path="*" element={<div className="p-6">Not Found</div>} />
    </Routes>
  )
}
