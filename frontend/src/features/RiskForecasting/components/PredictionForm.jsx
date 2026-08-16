import React from 'react';
import PropTypes from 'prop-types';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

/**
 * PredictionForm — Input form for single-district outbreak risk forecasting.
 */
const PredictionForm = ({
  districts = [],
  selectedDisease = 'FMD',
  onSelectDisease,
  selectedDistrict = 'Anuradhapura',
  onSelectDistrict,
  selectedYear = 2024,
  onSelectYear,
  selectedMonth = 1,
  onSelectMonth,
  use31Features = false,
  onToggle31Features,
  onSubmit,
  onOpenDashboard,
  isLoading = false,
}) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isLoading && onSubmit) onSubmit();
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6" data-testid="prediction-form-container">
      {/* Top Header & Mode Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-on-surface tracking-tight flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-2xl">analytics</span>
            Bovine Disease Risk Predictor
          </h2>
          <p className="text-xs md:text-sm text-on-surface-variant mt-1">
            Two-stage epidemiological forecasting model for Sri Lankan livestock districts.
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenDashboard}
          className="px-4 py-2.5 bg-surface-container-highest border border-outline-variant/30 rounded-lg text-xs md:text-sm font-semibold text-primary hover:bg-surface-bright transition-colors flex items-center justify-center gap-2 shrink-0"
          id="view-all-districts-btn"
          data-testid="view-dashboard-btn"
        >
          <span className="material-symbols-outlined text-sm">map</span>
          All-District Forecast
        </button>
      </div>

      {/* Form Card */}
      <form onSubmit={handleSubmit} className="bg-surface-container-low p-6 md:p-8 rounded-xl border border-outline-variant/10 shadow-2xl space-y-6">
        {/* 1. Disease Selection Toggle */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-primary uppercase tracking-widest block">
            Target Epizootic Disease
          </label>
          <div className="grid grid-cols-2 gap-3 p-1.5 bg-surface-container-lowest rounded-xl border border-outline-variant/10">
            <button
              type="button"
              onClick={() => onSelectDisease('FMD')}
              className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 ${
                selectedDisease === 'FMD'
                  ? 'primary-gradient text-on-primary shadow-lg'
                  : 'text-tertiary opacity-70 hover:text-primary hover:bg-surface-container-high'
              }`}
              data-testid="disease-toggle-fmd"
            >
              <span className="material-symbols-outlined text-lg">coronavirus</span>
              Foot-and-Mouth (FMD)
            </button>
            <button
              type="button"
              onClick={() => onSelectDisease('LSD')}
              className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 ${
                selectedDisease === 'LSD'
                  ? 'primary-gradient text-on-primary shadow-lg'
                  : 'text-tertiary opacity-70 hover:text-primary hover:bg-surface-container-high'
              }`}
              data-testid="disease-toggle-lsd"
            >
              <span className="material-symbols-outlined text-lg">vaccines</span>
              Lumpy Skin Disease (LSD)
            </button>
          </div>
        </div>

        {/* 2. District & Time Range Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* District Dropdown */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block" htmlFor="district-select">
              Administrative District
            </label>
            <div className="relative">
              <select
                id="district-select"
                value={selectedDistrict}
                onChange={(e) => onSelectDistrict(e.target.value)}
                className="w-full bg-surface-container rounded-lg px-4 py-3 text-sm text-on-surface border border-outline-variant/20 focus:border-primary focus:ring-1 focus:ring-primary outline-none appearance-none cursor-pointer"
                data-testid="district-select"
              >
                {districts.map((d) => (
                  <option key={d} value={d} className="bg-surface-container-low text-on-surface">
                    {d}
                  </option>
                ))}
              </select>
              <span className="material-symbols-outlined absolute right-3 top-3.5 text-on-surface-variant pointer-events-none text-sm">
                expand_more
              </span>
            </div>
          </div>

          {/* Year Input */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block" htmlFor="year-input">
              Forecast Year
            </label>
            <input
              id="year-input"
              type="number"
              min={2017}
              max={2030}
              value={selectedYear}
              onChange={(e) => onSelectYear(e.target.value)}
              className="w-full bg-surface-container rounded-lg px-4 py-3 text-sm text-on-surface border border-outline-variant/20 focus:border-primary focus:ring-1 focus:ring-primary outline-none"
              data-testid="year-input"
            />
          </div>

          {/* Month Dropdown */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block" htmlFor="month-select">
              Target Month
            </label>
            <div className="relative">
              <select
                id="month-select"
                value={selectedMonth}
                onChange={(e) => onSelectMonth(Number(e.target.value))}
                className="w-full bg-surface-container rounded-lg px-4 py-3 text-sm text-on-surface border border-outline-variant/20 focus:border-primary focus:ring-1 focus:ring-primary outline-none appearance-none cursor-pointer"
                data-testid="month-select"
              >
                {MONTH_NAMES.map((name, idx) => (
                  <option key={name} value={idx + 1} className="bg-surface-container-low text-on-surface">
                    {idx + 1} — {name}
                  </option>
                ))}
              </select>
              <span className="material-symbols-outlined absolute right-3 top-3.5 text-on-surface-variant pointer-events-none text-sm">
                expand_more
              </span>
            </div>
          </div>
        </div>

        {/* 3. FMD Variant Toggle (Only visible if FMD) */}
        {selectedDisease === 'FMD' && (
          <div className="p-4 bg-surface-container-lowest/60 rounded-lg border border-outline-variant/10 flex items-center justify-between">
            <div>
              <span className="text-xs font-bold text-primary uppercase tracking-widest block">
                Model Feature Variant
              </span>
              <p className="text-xs text-on-surface-variant mt-0.5">
                {use31Features
                  ? '31-Feature Autocorrelation Variant (Includes target lag features)'
                  : '30-Feature Baseline Variant (Standard environmental & spatial features)'}
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0 ml-4">
              <input
                type="checkbox"
                checked={use31Features}
                onChange={(e) => onToggle31Features(e.target.checked)}
                className="sr-only peer"
                data-testid="fmd-variant-toggle"
              />
              <div className="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
            </label>
          </div>
        )}

        {/* 4. Action Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full primary-gradient text-on-primary py-4 rounded-lg font-bold text-sm md:text-base flex items-center justify-center gap-3 shadow-xl hover:scale-[1.01] transition-all disabled:opacity-50"
          id="submit-forecast-btn"
          data-testid="submit-forecast-btn"
        >
          {isLoading ? (
            <>
              <div className="w-5 h-5 border-2 border-on-primary border-t-transparent rounded-full animate-spin" />
              <span>Evaluating Risk Model...</span>
            </>
          ) : (
            <>
              <span className="material-symbols-outlined text-xl">psychology</span>
              <span>Execute Risk Inference</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};

PredictionForm.propTypes = {
  districts: PropTypes.arrayOf(PropTypes.string),
  selectedDisease: PropTypes.string,
  onSelectDisease: PropTypes.func.isRequired,
  selectedDistrict: PropTypes.string,
  onSelectDistrict: PropTypes.func.isRequired,
  selectedYear: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  onSelectYear: PropTypes.func.isRequired,
  selectedMonth: PropTypes.number,
  onSelectMonth: PropTypes.func.isRequired,
  use31Features: PropTypes.bool,
  onToggle31Features: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  onOpenDashboard: PropTypes.func.isRequired,
  isLoading: PropTypes.bool,
};

export default PredictionForm;
