import React, { useState } from 'react';
import PropTypes from 'prop-types';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

/**
 * ForecastDashboard — Displays climatological risk forecasts across all 25 Sri Lankan districts.
 */
const ForecastDashboard = ({ forecastData, onRunForecast, onBackToForm }) => {
  const [disease, setDisease] = useState(forecastData?.disease || 'FMD');
  const [month, setMonth] = useState(forecastData?.month || 1);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortAsc, setSortAsc] = useState(false); // Default sort descending by probability

  const results = forecastData?.districts || forecastData?.forecasts || forecastData?.results || [];


  // Count high / medium / low risk districts
  const highCount = results.filter((r) => r.risk_level === 'HIGH' || r.stage1?.risk_level === 'HIGH').length;
  const mediumCount = results.filter((r) => r.risk_level === 'MEDIUM' || r.stage1?.risk_level === 'MEDIUM').length;
  const lowCount = results.filter((r) => r.risk_level === 'LOW' || r.stage1?.risk_level === 'LOW').length;

  // Filter and sort results
  const filtered = results.filter((r) =>
    r.district.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const sorted = [...filtered].sort((a, b) => {
    const probA = a.probability_pct ?? a.stage1?.probability_pct ?? 0;
    const probB = b.probability_pct ?? b.stage1?.probability_pct ?? 0;
    return sortAsc ? probA - probB : probB - probA;
  });

  const handleRun = () => {
    if (onRunForecast) onRunForecast(disease, month);
  };

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6" data-testid="forecast-dashboard-container">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl md:text-2xl font-bold text-on-surface">
              All-District Climatological Risk Forecast
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-primary/10 text-primary border border-primary/20">
              {forecastData?.disease || disease}
            </span>
          </div>
          <p className="text-xs text-on-surface-variant mt-1">
            Comparative outbreak probability across all 25 Sri Lankan administrative districts.
          </p>
        </div>

        <button
          type="button"
          onClick={onBackToForm}
          className="px-4 py-2.5 bg-surface-container-highest border border-outline-variant/30 rounded-lg text-xs md:text-sm font-semibold text-on-surface hover:bg-surface-bright transition-colors flex items-center justify-center gap-2 shrink-0"
          data-testid="back-to-form-btn"
        >
          <span className="material-symbols-outlined text-sm">arrow_back</span>
          Single-District Predictor
        </button>
      </div>

      {/* Control Bar: Disease & Month Selector */}
      <div className="bg-surface-container-low p-4 rounded-xl border border-outline-variant/10 shadow-lg flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full sm:w-auto">
          {/* Disease Switcher */}
          <div className="flex bg-surface-container-lowest p-1 rounded-lg border border-outline-variant/10">
            <button
              type="button"
              onClick={() => setDisease('FMD')}
              className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${
                disease === 'FMD' ? 'bg-primary text-on-primary' : 'text-tertiary hover:text-primary'
              }`}
            >
              FMD
            </button>
            <button
              type="button"
              onClick={() => setDisease('LSD')}
              className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${
                disease === 'LSD' ? 'bg-primary text-on-primary' : 'text-tertiary hover:text-primary'
              }`}
            >
              LSD
            </button>
          </div>

          {/* Month Selector */}
          <select
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            className="bg-surface-container rounded-lg px-3 py-1.5 text-xs text-on-surface border border-outline-variant/20 focus:outline-none"
          >
            {MONTH_NAMES.map((name, idx) => (
              <option key={name} value={idx + 1}>
                {idx + 1} — {name}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={handleRun}
          className="w-full sm:w-auto primary-gradient text-on-primary px-5 py-2 rounded-lg font-bold text-xs flex items-center justify-center gap-2 shadow-md hover:scale-[1.02] transition-transform"
          data-testid="run-all-forecast-btn"
        >
          <span className="material-symbols-outlined text-base">refresh</span>
          Run Forecast ({disease})
        </button>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-surface-container-low p-4 rounded-xl border border-error/20 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-error uppercase tracking-wider block">
              High Risk Districts
            </span>
            <span className="text-2xl font-black text-error">{highCount}</span>
          </div>
          <span className="material-symbols-outlined text-error text-3xl">warning</span>
        </div>

        <div className="bg-surface-container-low p-4 rounded-xl border border-[#f59e0b]/20 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-[#f59e0b] uppercase tracking-wider block">
              Medium Risk Districts
            </span>
            <span className="text-2xl font-black text-[#f59e0b]">{mediumCount}</span>
          </div>
          <span className="material-symbols-outlined text-[#f59e0b] text-3xl">error_outline</span>
        </div>

        <div className="bg-surface-container-low p-4 rounded-xl border border-primary/20 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-primary uppercase tracking-wider block">
              Low Risk Districts
            </span>
            <span className="text-2xl font-black text-primary">{lowCount}</span>
          </div>
          <span className="material-symbols-outlined text-primary text-3xl">shield</span>
        </div>
      </div>

      {/* Filter & Sort Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-surface-container-low p-4 rounded-xl border border-outline-variant/10">
        <div className="relative w-full sm:w-64">
          <span className="material-symbols-outlined absolute left-3 top-2.5 text-on-surface-variant text-sm">
            search
          </span>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filter district..."
            className="w-full bg-surface-container rounded-lg pl-9 pr-4 py-2 text-xs text-on-surface border border-outline-variant/20 outline-none placeholder:text-on-surface-variant/50"
            data-testid="district-filter-input"
          />
        </div>

        <button
          type="button"
          onClick={() => setSortAsc((prev) => !prev)}
          className="text-xs font-semibold text-primary hover:text-primary-fixed-dim flex items-center gap-1 self-end sm:self-center"
        >
          <span className="material-symbols-outlined text-base">sort</span>
          Sort by Prob: {sortAsc ? 'Low → High' : 'High → Low'}
        </button>
      </div>

      {/* All-District Data Table */}
      <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 shadow-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" data-testid="forecast-table">
            <thead>
              <tr className="bg-surface-container-lowest/80 text-[10px] uppercase font-bold text-on-surface-variant border-b border-outline-variant/10">
                <th className="py-3.5 px-4">District</th>
                <th className="py-3.5 px-4">Outbreak Probability</th>
                <th className="py-3.5 px-4">Risk Level</th>
                <th className="py-3.5 px-4">Severity</th>
                <th className="py-3.5 px-4">Stage 2 Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/5 text-xs text-on-surface">
              {sorted.length > 0 ? (
                sorted.map((row) => {
                  const prob = row.probability_pct ?? row.stage1?.probability_pct ?? 0;
                  const level = row.risk_level || row.stage1?.risk_level || 'LOW';
                  const sev = row.severity_predicted || row.stage2?.severity_predicted || 'LOW';
                  const evalStatus = row.stage2?.evaluated ?? (prob >= 40);

                  const levelColor =
                    level === 'HIGH' ? 'text-error bg-error/10 border-error/20' :
                    level === 'MEDIUM' ? 'text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/20' :
                    'text-primary bg-primary/10 border-primary/20';

                  return (
                    <tr key={row.district} className="hover:bg-surface-container-high/40 transition-colors">
                      <td className="py-3 px-4 font-bold">{row.district}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <span className="font-mono font-bold w-12">{prob}%</span>
                          <div className="w-24 bg-surface-container rounded-full h-1.5 overflow-hidden hidden sm:block">
                            <div
                              className={`h-full rounded-full ${level === 'HIGH' ? 'bg-error' : level === 'MEDIUM' ? 'bg-[#f59e0b]' : 'bg-primary'}`}
                              style={{ width: `${Math.min(100, prob)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${levelColor}`}>
                          {level}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-semibold text-on-surface-variant">{sev}</td>
                      <td className="py-3 px-4 text-[10px]">
                        {evalStatus ? (
                          <span className="text-primary font-bold">EVALUATED</span>
                        ) : (
                          <span className="text-tertiary">BYPASSED</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-on-surface-variant italic">
                    No districts match filter criteria or no forecast data loaded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

ForecastDashboard.propTypes = {
  forecastData: PropTypes.object,
  onRunForecast: PropTypes.func,
  onBackToForm: PropTypes.func.isRequired,
};

export default ForecastDashboard;
