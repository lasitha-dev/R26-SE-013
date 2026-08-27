import React, { useState, useEffect } from 'react';
import { RiskForecastingFeature } from '../RiskForecastingFeature';
import { validateViewerContext, ROLES } from '../contracts/viewerContext';
import { AccessContextUnavailable } from '../components/AccessContextUnavailable';

const API_BASE = import.meta.env.VITE_API_URL || '';
const REQUEST_TIMEOUT_MS = 8000;

export default function RiskForecastingIntegrationAdapter() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewerContext, setViewerContext] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setError("Authentication required.");
      setLoading(false);
      return;
    }

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), REQUEST_TIMEOUT_MS);

    async function fetchViewerContext() {
      try {
        const response = await fetch(`${API_BASE}/api/v1/risk-forecasting/viewer-context`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'application/json'
          },
          signal: abortController.signal
        });

        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();
        
        const validation = validateViewerContext(data);
        if (!validation.valid || (validation.normalizedContext.role !== ROLES.VETERINARY_OFFICER && validation.normalizedContext.role !== ROLES.DAPH_OFFICIAL)) {
          throw new Error("Invalid or unauthorized context");
        }

        setViewerContext(validation.normalizedContext);
      } catch (err) {
        if (err.name === 'AbortError') {
          setError("Request timed out.");
        } else {
          setError("Access context unavailable.");
        }
      } finally {
        clearTimeout(timeoutId);
        setLoading(false);
      }
    }

    fetchViewerContext();

    return () => {
      abortController.abort();
      clearTimeout(timeoutId);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8" role="status">
        <div className="w-8 h-8 rounded-full border-4 border-dashed border-emerald-500/50 animate-spin-slow"></div>
        <span className="sr-only">Loading forecasting context...</span>
      </div>
    );
  }

  if (error || !viewerContext) {
    return <AccessContextUnavailable reason="Access context unavailable. Please ensure you are logged in as an authorized practitioner." />;
  }

  return (
    <RiskForecastingFeature
      viewerContext={viewerContext}
      operationalData={null}
    />
  );
}
