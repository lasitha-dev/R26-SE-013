import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

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

export default function HealthAnomalyRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="dashboard" replace />} />

      <Route path="dashboard" element={<WellnessDashboard />} />
      <Route path="registration-success" element={<RegistrationSuccess />} />
      <Route path="login" element={<SystemLogin />} />
      <Route path="registration" element={<RegistrationLanding />} />
      <Route path="password-reset" element={<PasswordReset />} />
      <Route path="settings" element={<SettingsFarmConfiguration />} />
      <Route path="herd-registry" element={<HerdRegistry />} />
      <Route path="animal-profile-bt-8842" element={<AnimalProfileBT8842 />} />
      <Route path="add-new-animal" element={<AddNewAnimal />} />
      <Route path="wellness-data-intake" element={<WellnessDataIntake />} />
      <Route path="7-day-triage-scan" element={<SevenDayTriageScan />} />
      <Route path="ai-wellness-report" element={<AiWellnessReport />} />
      <Route path="notifications" element={<NotificationsCenter />} />

      <Route path="*" element={<div className="p-6">Not Found</div>} />
    </Routes>
  )
}
