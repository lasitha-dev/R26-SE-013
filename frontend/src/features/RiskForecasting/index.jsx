import React from 'react';
import AppShell from '../../shared_components/AppShell';
import useRiskPrediction from './hooks/useRiskPrediction';
import PredictionForm from './components/PredictionForm';
import PredictionResults from './components/PredictionResults';
import ForecastDashboard from './components/ForecastDashboard';

/**
 * RiskForecasting — Entry component for the Seasonal Risk Forecasting feature module.
 * Wraps in the shared AppShell and coordinates state-driven view navigation between:
 * - 'form' (Screen A: Input Form)
 * - 'results' (Screen B: Single-District Inference Results)
 * - 'dashboard' (Screen C: All-District Forecast Table)
 */
const RiskForecasting = () => {
  const {
    viewMode,
    setViewMode,
    status,
    error,
    districts,
    predictionResult,
    forecastResult,
    selectedDisease,
    setSelectedDisease,
    selectedDistrict,
    setSelectedDistrict,
    selectedYear,
    setSelectedYear,
    selectedMonth,
    setSelectedMonth,
    use31Features,
    setUse31Features,
    submitPrediction,
    submitForecast,
    resetToForm,
  } = useRiskPrediction();

  const isLoading = status === 'loading';

  return (
    <AppShell activeNavItem="forecasting" headerTitle="Seasonal Risk Forecasting">
      <div className="w-full py-4 space-y-6">
        {/* Error Banner */}
        {error && (
          <div className="w-full max-w-4xl mx-auto p-4 bg-error-container/40 border border-error/40 rounded-xl flex items-center justify-between text-on-error-container text-xs md:text-sm">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-error text-xl shrink-0">error</span>
              <div>
                <span className="font-bold block">Inference Error</span>
                <span className="opacity-90">{error}</span>
              </div>
            </div>
            <button
              onClick={resetToForm}
              className="px-3 py-1.5 bg-error/20 hover:bg-error/30 text-error font-bold rounded-lg transition-colors text-xs shrink-0"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* View Switcher: Form vs Results vs Dashboard */}
        {viewMode === 'form' && (
          <PredictionForm
            districts={districts}
            selectedDisease={selectedDisease}
            onSelectDisease={setSelectedDisease}
            selectedDistrict={selectedDistrict}
            onSelectDistrict={setSelectedDistrict}
            selectedYear={selectedYear}
            onSelectYear={setSelectedYear}
            selectedMonth={selectedMonth}
            onSelectMonth={setSelectedMonth}
            use31Features={use31Features}
            onToggle31Features={setUse31Features}
            onSubmit={submitPrediction}
            onOpenDashboard={() => {
              submitForecast(selectedDisease, selectedMonth, selectedYear);
            }}
            isLoading={isLoading}
          />
        )}

        {viewMode === 'results' && predictionResult && (
          <PredictionResults
            result={predictionResult}
            onBack={resetToForm}
          />
        )}

        {viewMode === 'dashboard' && (
          <ForecastDashboard
            forecastData={forecastResult}
            onRunForecast={(disease, month) => submitForecast(disease, month, selectedYear)}
            onBackToForm={resetToForm}
          />
        )}
      </div>
    </AppShell>
  );
};

export default RiskForecasting;
