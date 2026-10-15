import { useState, useCallback, useRef, useEffect } from 'react';
import { detectImage, fetchReasoning } from '../services/api';

/**
 * useDetection — custom hook for managing the AI Smart Diagnosis inference lifecycle.
 *
 * States: 'idle' → 'processing' → 'done' | 'error'
 * Reasoning: 'idle' → 'loading' → 'done' | 'error'  (auto-triggered after successful detection)
 *
 * @returns {object} { status, result, error, imagePreview, detect, reset,
 *                     reasoning, reasoningStatus, reasoningError }
 */
export default function useDetection() {
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

  // Tier 3 — LLM reasoning state
  const [reasoning, setReasoning] = useState(null);
  const [reasoningStatus, setReasoningStatus] = useState('idle');
  const [reasoningError, setReasoningError] = useState(null);
  const [severityAssessment, setSeverityAssessment] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const imageRevision = useRef(0);
  const reasoningRevision = useRef(0);
  const previewRef = useRef(null);
  const lastReasoningInput = useRef(null);
  useEffect(() => () => {
    ++imageRevision.current;
    ++reasoningRevision.current;
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
  }, []);

  const requestReasoning = useCallback(async (data, imageToken) => {
    lastReasoningInput.current = data;
    const token = ++reasoningRevision.current;
    const current = () => imageToken === imageRevision.current && token === reasoningRevision.current;
    setReasoningStatus('loading');
    setReasoningError(null);
    setReasoning(null);
    setSeverityAssessment(null);
    setExplanation(null);
    try {
      const reasoningData = await fetchReasoning(data);
      if (!current()) return;
      setReasoning(reasoningData.reasoning_report || null);
      setSeverityAssessment(reasoningData.severity_assessment || null);
      setExplanation(reasoningData.explanation || null);
      setReasoningStatus(reasoningData.status === 'ok' ? 'done' : ['fallback', 'unavailable'].includes(reasoningData.status) ? reasoningData.status : 'error');
      if (reasoningData.status !== 'ok') setReasoningError(reasoningData.reasoning_report);
    } catch (reasonErr) {
      if (!current()) return;
      setReasoningError(reasonErr.message || String(reasonErr));
      setReasoningStatus('error');
    }
  }, []);

  const invalidateClinicalAssessment = useCallback(() => {
    lastReasoningInput.current = null;
    ++reasoningRevision.current;
    setReasoning(null);
    setReasoningStatus('idle');
    setReasoningError(null);
    setSeverityAssessment(null);
    setExplanation(null);
  }, []);

  const assessClinicalObservations = useCallback(async (observations) => {
    if (!result || status !== 'done') return;
    await requestReasoning({ ...result, clinical_observations: observations }, imageRevision.current);
  }, [result, status, requestReasoning]);

  const detect = useCallback(async (file, context) => {
    lastReasoningInput.current = null;
    const imageToken = ++imageRevision.current;
    ++reasoningRevision.current;
    setResult(null);
    setStatus('processing');
    setError(null);
    setReasoning(null);
    setReasoningStatus('idle');
    setReasoningError(null);
    setSeverityAssessment(null);
    setExplanation(null);

    // Create a local preview URL so we can display the uploaded image
    const previewUrl = URL.createObjectURL(file);
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = previewUrl;
    setImagePreview(previewUrl);

    try {
      const data = await (context ? detectImage(file, context) : detectImage(file));
      if (imageToken !== imageRevision.current) return;
      setResult(data);
      setStatus('done');

      // Auto-trigger Tier 3 reasoning if cattle was detected
      if (data.cattle_detected) {
        await requestReasoning(data, imageToken);
      }
    } catch (err) {
      if (imageToken !== imageRevision.current) return;
      setError(err.message || String(err));
      setStatus('error');
    }
  }, [requestReasoning]);

  const reset = useCallback(() => {
    lastReasoningInput.current = null;
    ++imageRevision.current;
    ++reasoningRevision.current;
    // Revoke the preview URL to free memory
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
    }
    previewRef.current = null;
    setStatus('idle');
    setResult(null);
    setError(null);
    setImagePreview(null);
    setReasoning(null);
    setReasoningStatus('idle');
    setReasoningError(null);
    setSeverityAssessment(null);
    setExplanation(null);
  }, [imagePreview]);

  return {
    status,
    result,
    error,
    imagePreview,
    detect,
    reset,
    reasoning,
    reasoningStatus,
    reasoningError,
    severityAssessment,
    explanation,
    assessClinicalObservations,
    invalidateClinicalAssessment,
    retryReasoning: () => result && requestReasoning(lastReasoningInput.current || result, imageRevision.current),
  };
}
