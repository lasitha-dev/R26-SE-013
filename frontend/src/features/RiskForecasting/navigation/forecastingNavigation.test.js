import { describe, it, expect } from 'vitest';
import {
  ROLES,
  SCOPE_LEVELS,
  PERMISSIONS,
} from '../contracts/viewerContext';
import {
  NAVIGATION_ITEMS,
  getForecastingNavigation,
  isForecastingNavigationItemAllowed,
} from './forecastingNavigation';

describe('forecastingNavigation Helpers', () => {
  const farmerContext = {
    userId: 'usr_farmer_001',
    role: ROLES.FARMER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Anuradhapura',
      authorizedDistricts: ['Anuradhapura'],
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

  const vetContext = {
    userId: 'usr_vet_001',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Jaffna'],
      assignedFarmIds: ['FARM_001'],
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: false,
    },
  };

  const daphContextBasic = {
    userId: 'usr_daph_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Anuradhapura', 'Jaffna'],
      assignedFarmIds: [],
    },
    permissions: {
      viewDataQuality: false,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    },
  };

  it('returns empty array for invalid context or null', () => {
    expect(getForecastingNavigation(null)).toEqual([]);
    expect(getForecastingNavigation(undefined)).toEqual([]);
    expect(getForecastingNavigation({})).toEqual([]);
  });

  it('Farmer gets Disease Risk and Alerts & Guidance only', () => {
    const items = getForecastingNavigation(farmerContext);
    expect(items).toHaveLength(2);
    expect(items[0]).toEqual(NAVIGATION_ITEMS.DISEASE_RISK);
    expect(items[1]).toEqual(NAVIGATION_ITEMS.ALERTS_GUIDANCE);
  });

  it('Farmer does not get Vet or DAPH items', () => {
    const ids = getForecastingNavigation(farmerContext).map((i) => i.id);
    expect(ids).not.toContain('forecast-overview');
    expect(ids).not.toContain('surveillance-dashboard');
    expect(ids).not.toContain('surveillance-overview');
    expect(ids).not.toContain('data-quality');
  });

  it('Vet gets Forecast Overview, District Forecasts, Advisory Centre, and Surveillance Dashboard', () => {
    const items = getForecastingNavigation(vetContext);
    expect(items).toHaveLength(4);
    expect(items[0]).toEqual(NAVIGATION_ITEMS.FORECAST_OVERVIEW);
    expect(items[1]).toEqual(NAVIGATION_ITEMS.DISTRICT_FORECASTS);
    expect(items[2]).toEqual(NAVIGATION_ITEMS.ADVISORY_CENTRE);
    expect(items[3]).toEqual(NAVIGATION_ITEMS.SURVEILLANCE_DASHBOARD);

    const ids = items.map((i) => i.id);
    expect(ids).not.toContain('trend');
    expect(ids).not.toContain('outbox');
    expect(ids).not.toContain('history');
  });

  it('DAPH without viewDataQuality capability gets Overview and District Forecasts only', () => {
    const items = getForecastingNavigation(daphContextBasic);
    expect(items).toHaveLength(2);
    expect(items[0]).toEqual(NAVIGATION_ITEMS.SURVEILLANCE_OVERVIEW);
    expect(items[1]).toEqual(NAVIGATION_ITEMS.DISTRICT_FORECASTS);

    const ids = items.map((i) => i.id);
    expect(ids).not.toContain('data-quality');
    expect(ids).not.toContain('reports-and-trends');
    expect(ids).not.toContain('surveillance-and-alerts');
  });

  it('DAPH with viewDataQuality permission gets Data Quality item', () => {
    const daphWithDataQuality = {
      ...daphContextBasic,
      permissions: { ...daphContextBasic.permissions, viewDataQuality: true },
    };
    const items = getForecastingNavigation(daphWithDataQuality);
    expect(items).toHaveLength(3);
    expect(items[2]).toEqual(NAVIGATION_ITEMS.DATA_QUALITY);
  });

  it('explicit viewModelTransparency permission adds Model Transparency to any valid role', () => {
    const farmerWithTransparency = {
      ...farmerContext,
      permissions: { ...farmerContext.permissions, viewModelTransparency: true },
    };
    const items = getForecastingNavigation(farmerWithTransparency);
    expect(items).toHaveLength(3);
    expect(items[2]).toEqual(NAVIGATION_ITEMS.MODEL_TRANSPARENCY);
  });

  it('role alone does not grant Model Transparency without explicit permission flag', () => {
    const daphWithoutTransparency = {
      ...daphContextBasic,
      permissions: { ...daphContextBasic.permissions, viewModelTransparency: false },
    };
    const ids = getForecastingNavigation(daphWithoutTransparency).map((i) => i.id);
    expect(ids).not.toContain('model-transparency');
  });

  it('isForecastingNavigationItemAllowed validates item IDs correctly', () => {
    expect(isForecastingNavigationItemAllowed(farmerContext, 'disease-risk')).toBe(true);
    expect(isForecastingNavigationItemAllowed(vetContext, 'forecast-overview')).toBe(true);
    expect(isForecastingNavigationItemAllowed(farmerContext, 'surveillance-dashboard')).toBe(false);
    expect(isForecastingNavigationItemAllowed(farmerContext, 'invalid-item')).toBe(false);
    expect(isForecastingNavigationItemAllowed(null, 'disease-risk')).toBe(false);
  });

  it('returns defensive copies of items and arrays', () => {
    const items1 = getForecastingNavigation(farmerContext);
    items1[0].label = 'Mutated Label';
    items1.push({ id: 'fake', label: 'Fake', icon: 'fake' });

    const items2 = getForecastingNavigation(farmerContext);
    expect(items2[0].label).toBe('Disease Risk');
    expect(items2).toHaveLength(2);
  });

  it('does not mutate input viewerContext', () => {
    const contextCopy = JSON.parse(JSON.stringify(farmerContext));
    getForecastingNavigation(farmerContext);
    expect(farmerContext).toEqual(contextCopy);
  });
});
