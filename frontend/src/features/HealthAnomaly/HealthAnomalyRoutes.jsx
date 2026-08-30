import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import DashboardLayout from '../../shared_components/DashboardLayout.jsx'
import WellnessDashboard from './screens/WellnessDashboard.jsx'
import RegistrationSuccess from '../../shared_components/RegistrationSuccess.jsx'
import SystemLogin from '../../shared_components/SystemLogin.jsx'
import RegistrationLanding from '../../shared_components/RegistrationLanding.jsx'
import PasswordReset from '../../shared_components/PasswordReset.jsx'
import VetLogin from '../../shared_components/VetLogin.jsx'
import VetRegistration from '../../shared_components/VetRegistration.jsx'
import VetRegistrationSuccess from '../../shared_components/VetRegistrationSuccess.jsx'
import SettingsFarmConfiguration from './screens/SettingsFarmConfiguration.jsx'
import HerdRegistry from './screens/HerdRegistry.jsx'
import AnimalProfile from './screens/AnimalProfile.jsx'
import AddNewAnimal from './screens/AddNewAnimal.jsx'
import WellnessDataIntake from './screens/WellnessDataIntake.jsx'
import SevenDayTriageScan from './screens/SevenDayTriageScan.jsx'
import AiWellnessReport from './screens/AiWellnessReport.jsx'
import NotificationsCenter from './screens/NotificationsCenter.jsx'
import BCSAnalyzer from './screens/BCSAnalyzer.jsx'
import FarmerSmartDiagnostics from './screens/FarmerSmartDiagnostics.jsx'
import FarmerCaseHistory from './screens/FarmerCaseHistory.jsx'
import { ProfileProvider } from '../../context/ProfileContext.jsx'

export default function HealthAnomalyRoutes() {
  return (
    <ProfileProvider>
      <Routes>

      <Route path="/" element={<Navigate to="login" replace />} />

      {/* Auth routes without sidebar/header layout */}
      <Route path="login" element={<SystemLogin />} />
      <Route path="registration" element={<RegistrationLanding />} />
      <Route path="registration-success" element={<RegistrationSuccess />} />
      <Route path="password-reset" element={<PasswordReset />} />
      <Route path="vet-login" element={<VetLogin />} />
      <Route path="vet-registration" element={<VetRegistration />} />
      <Route path="vet-registration-success" element={<VetRegistrationSuccess />} />

      {/* Main app routes wrapped with DashboardLayout for Farm Owner */}
      <Route element={<DashboardLayout />}>
        <Route path="dashboard" element={<WellnessDashboard />} />
        <Route path="settings" element={<SettingsFarmConfiguration />} />
        <Route path="herd-registry" element={<HerdRegistry />} />
        <Route path="animal-profile/:id" element={<AnimalProfile />} />
        <Route path="add-new-animal" element={<AddNewAnimal />} />
        <Route path="wellness-data-intake" element={<WellnessDataIntake />} />
        <Route path="7-day-triage-scan" element={<SevenDayTriageScan />} />
        <Route path="ai-wellness-report" element={<AiWellnessReport />} />
        <Route path="notifications" element={<NotificationsCenter />} />
        <Route path="bcs-analyzer" element={<BCSAnalyzer />} />
        <Route path="diagnostics" element={<FarmerSmartDiagnostics />} />
        <Route path="case-history" element={<FarmerCaseHistory />} />
      </Route>

      <Route path="*" element={<div className="p-6">Not Found</div>} />
    </Routes>
  </ProfileProvider>
)
}

