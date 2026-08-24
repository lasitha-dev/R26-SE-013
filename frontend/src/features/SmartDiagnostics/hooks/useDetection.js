import { useState, useCallback } from 'react';
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

  const detect = useCallback(async (file) => {
    setStatus('processing');
    setError(null);
    setReasoning(null);
    setReasoningStatus('idle');
    setReasoningError(null);

    // Create a local preview URL so we can display the uploaded image
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);

    try {
      const data = await detectImage(file);
      setResult(data);
      setStatus('done');

      // Auto-trigger Tier 3 reasoning if cattle was detected
      if (data.cattle_detected) {
        setReasoningStatus('loading');
        try {
          const reasoningData = await fetchReasoning(data);
          setReasoning(reasoningData.reasoning_report || null);
          setReasoningStatus(reasoningData.status === 'ok' ? 'done' : 'error');
          if (reasoningData.status !== 'ok') {
            setReasoningError(reasoningData.reasoning_report);
          }
        } catch (reasonErr) {
          setReasoningError(reasonErr.message || String(reasonErr));
          setReasoningStatus('error');
        }
      }
    } catch (err) {
      setError(err.message || String(err));
      setStatus('error');
    }
  }, []);

  const reset = useCallback(() => {
    // Revoke the preview URL to free memory
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
    }
    setStatus('idle');
    setResult(null);
    setError(null);
    setImagePreview(null);
    setReasoning(null);
    setReasoningStatus('idle');
    setReasoningError(null);
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
  };
}
