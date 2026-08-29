import { useState, useCallback, useEffect } from 'react';
import { fetchDistricts, predictFMD, predictLSD, fetchForecast } from '../services/api';

/**
 * useRiskPrediction — Custom hook managing the Risk Forecasting UI lifecycle.
 *
 * View Modes: 'form' | 'results' | 'dashboard'
 * API Status: 'idle' | 'loading' | 'success' | 'error'
 */
export default function useRiskPrediction() {
  const [viewMode, setViewMode] = useState('form'); // 'form' | 'results' | 'dashboard'
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);

  // Data states
  const [districts, setDistricts] = useState([]);
  const [predictionResult, setPredictionResult] = useState(null);
  const [forecastResult, setForecastResult] = useState(null);

  // Form selections
  const [selectedDisease, setSelectedDisease] = useState('FMD'); // 'FMD' | 'LSD'
  const [selectedDistrict, setSelectedDistrict] = useState('Anuradhapura');
  const [selectedYear, setSelectedYear] = useState(2024);
  const [selectedMonth, setSelectedMonth] = useState(1);
  const [use31Features, setUse31Features] = useState(false);

  // Load district metadata on initial mount
  useEffect(() => {
    let isMounted = true;
    fetchDistricts()
      .then((data) => {
        if (isMounted && data.districts) {
          setDistricts(data.districts);
          if (data.districts.length > 0 && !data.districts.includes(selectedDistrict)) {
            setSelectedDistrict(data.districts[0]);
          }
        }
      })
      .catch((err) => {
        console.warn('Could not load district metadata:', err.message);
      });
    return () => { isMounted = false; };
  }, []);

  // Submit single-district prediction
  const submitPrediction = useCallback(async () => {
    setStatus('loading');
    setError(null);

    try {
      let data;
      if (selectedDisease === 'FMD') {
        data = await predictFMD({
          district: selectedDistrict,
          year: Number(selectedYear),
          month: Number(selectedMonth),
          use31Features,
        });
      } else {
        data = await predictLSD({
          district: selectedDistrict,
          year: Number(selectedYear),
          month: Number(selectedMonth),
        });
      }
      setPredictionResult(data);
      setStatus('success');
      setViewMode('results');
    } catch (err) {
      setError(err.message || String(err));
      setStatus('error');
    }
  }, [selectedDisease, selectedDistrict, selectedYear, selectedMonth, use31Features]);

  // Submit all-district forecast
  const submitForecast = useCallback(async (diseaseParam, monthParam, yearParam) => {
    setStatus('loading');
    setError(null);

    const dis = diseaseParam || selectedDisease;
    const m = monthParam || selectedMonth;
    const y = yearParam || selectedYear;

    try {
      const data = await fetchForecast(dis, { month: Number(m), year: Number(y) });
      setForecastResult(data);
      setStatus('success');
      setViewMode('dashboard');
    } catch (err) {
      setError(err.message || String(err));
      setStatus('error');
    }
  }, [selectedDisease, selectedMonth, selectedYear]);

  const resetToForm = useCallback(() => {
    setViewMode('form');
    setStatus('idle');
    setError(null);
  }, []);

  return {
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
  };
}
