/**
 * Custom React hook for consuming DemoForecastingAuthContext.
 */

import { useContext } from 'react';
import { DemoForecastingAuthContext } from '../context/DemoForecastingAuthContext.jsx';

export function useDemoForecastingAuth() {
  const context = useContext(DemoForecastingAuthContext);
  if (!context) {
    throw new Error('useDemoForecastingAuth must be used within a DemoForecastingAuthProvider');
  }
  return context;
}
