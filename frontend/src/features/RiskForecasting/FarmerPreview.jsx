import React, { useState } from 'react';
import { FarmerDiseaseRisk } from './components/farmer/FarmerDiseaseRisk';
import { ROLES, SCOPE_LEVELS } from './contracts/viewerContext';

/**
 * Review-only preview of the Farmer "Disease Risk" screen.
 *
 * The integrated app has no farmer entry into forecasting yet, so this page lets a reviewer see what a
 * farmer registered in a chosen district would see. It reads exactly the same stored forecast records as
 * every other screen (public GET), grants nothing and is off unless VITE_FORECASTING_FARMER_PREVIEW=true.
 */
export const PREVIEW_DISTRICTS = [
  'Ampara', 'Anuradhapura', 'Badulla', 'Batticaloa', 'Colombo', 'Galle', 'Gampaha', 'Hambantota', 'Jaffna',
  'Kalutara', 'Kandy', 'Kegalle', 'Kilinochchi', 'Kurunegala', 'Mannar', 'Matale', 'Matara', 'Monaragala',
  'Mullaitivu', 'Nuwara Eliya', 'Polonnaruwa', 'Puttalam', 'Ratnapura', 'Trincomalee', 'Vavuniya',
];

export function isFarmerPreviewEnabled(envVal) {
  const flag = envVal !== undefined ? envVal : import.meta.env?.VITE_FORECASTING_FARMER_PREVIEW;
  return flag === 'true';
}

function farmerContextFor(district) {
  return {
    userId: `preview-farmer-${district.toLowerCase().replace(/\s+/g, '-')}`,
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: district,
      authorizedDistricts: [district],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: false,
      recordResponse: false,
      viewReports: false,
    },
  };
}

export default function FarmerPreview({ enabled } = {}) {
  const [district, setDistrict] = useState('Colombo');
  if (!(enabled ?? isFarmerPreviewEnabled())) {
    return (
      <div className="max-w-2xl mx-4 sm:mx-auto my-12 p-8 rounded-2xl bg-surface-container border border-outline-variant/40 text-on-surface text-center space-y-2">
        <h1 className="text-xl font-bold">Farmer preview is disabled</h1>
        <p className="text-sm text-on-surface-variant">
          Start the frontend with <code className="font-mono">VITE_FORECASTING_FARMER_PREVIEW=true</code> to enable this review-only page.
        </p>
      </div>
    );
  }
  return (
    <div className="min-h-screen bg-surface text-on-surface p-4 space-y-4">
      <div className="max-w-5xl mx-auto p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-xs text-amber-200 space-y-2">
        <p>
          <strong>Review preview, not a real login.</strong> This shows what a farmer registered in the chosen
          district would see. It reads the same stored forecasts as the vet and DAPH screens.
        </p>
        <label className="flex items-center gap-2">
          <span>Farmer's registered district</span>
          <select
            aria-label="Preview district"
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            className="bg-surface-container text-on-surface border border-outline-variant/40 rounded-lg px-2 py-1"
          >
            {PREVIEW_DISTRICTS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
      </div>
      <FarmerDiseaseRisk key={district} viewerContext={farmerContextFor(district)} />
    </div>
  );
}
