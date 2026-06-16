import { useState, useCallback } from 'react';
import { detectImage } from '../services/api';

/**
 * useDetection — custom hook for managing the AI Smart Diagnosis inference lifecycle.
 *
 * States: 'idle' → 'processing' → 'done' | 'error'
 *
 * @returns {object} { status, result, error, imagePreview, detect, reset }
 */
export default function useDetection() {
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

  const detect = useCallback(async (file) => {
    setStatus('processing');
    setError(null);

    // Create a local preview URL so we can display the uploaded image
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);

    try {
      const data = await detectImage(file);
      setResult(data);
      setStatus('done');
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
  }, [imagePreview]);

  return { status, result, error, imagePreview, detect, reset };
}
