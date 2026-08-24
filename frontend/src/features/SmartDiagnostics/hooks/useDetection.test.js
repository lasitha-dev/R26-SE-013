/**
 * useDetection.test.js — Hook lifecycle and state machine tests.
 * ================================================================
 *
 * Tests the useDetection custom hook's state transitions, error
 * handling, reasoning auto-trigger, and reset functionality.
 *
 * Uses `renderHook` from @testing-library/react and mocks the
 * API service module to avoid network access.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import useDetection from './useDetection';

// Mock the API service to intercept all network calls
vi.mock('../services/api', () => ({
  detectImage: vi.fn(),
  fetchReasoning: vi.fn(),
}));

// Mock URL.createObjectURL / revokeObjectURL (jsdom doesn't have them)
const mockCreateObjectURL = vi.fn(() => 'blob:mock-preview-url');
const mockRevokeObjectURL = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  global.URL.createObjectURL = mockCreateObjectURL;
  global.URL.revokeObjectURL = mockRevokeObjectURL;
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Helper to import the mocked API functions */
const getApi = async () => {
  const api = await import('../services/api');
  return { detectImage: api.detectImage, fetchReasoning: api.fetchReasoning };
};


// ═══════════════════════════════════════════════════════════════════════════
// Test fixtures
// ═══════════════════════════════════════════════════════════════════════════

const MOCK_DETECTION_RESULT = {
  cattle_detected: true,
  detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
  best_detection: {
    bbox: [10, 20, 100, 200],
    confidence: 0.95,
    bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
  },
  disease: {
    name: 'Lumpy Skin Disease',
    confidence: 91.5,
    all_probabilities: { 'Lumpy Skin Disease': 91.5 },
  },
  image_size: { width: 640, height: 480 },
};

const MOCK_REASONING_RESULT = {
  status: 'ok',
  reasoning_report: '## 1. Primary Diagnostic Assessment\nTest report.',
  model_name: 'qwen2.5-vl-3b-instruct',
};

const MOCK_FILE = new File(['test-image-data'], 'cow.jpg', { type: 'image/jpeg' });


// ═══════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════

describe('useDetection', () => {
  it('test_usedetection_initial_state_is_idle', () => {
    const { result } = renderHook(() => useDetection());

    expect(result.current.status).toBe('idle');
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.imagePreview).toBeNull();
    expect(result.current.reasoning).toBeNull();
    expect(result.current.reasoningStatus).toBe('idle');
    expect(result.current.reasoningError).toBeNull();
  });

  it('test_usedetection_detect_transitions_to_processing', async () => {
    const { detectImage, fetchReasoning } = await getApi();
    // Make it hang so we can observe the 'processing' state
    detectImage.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useDetection());

    act(() => {
      result.current.detect(MOCK_FILE);
    });

    expect(result.current.status).toBe('processing');
    expect(result.current.imagePreview).toBe('blob:mock-preview-url');
  });

  it('test_usedetection_detect_success_transitions_to_done', async () => {
    const { detectImage, fetchReasoning } = await getApi();
    detectImage.mockResolvedValue(MOCK_DETECTION_RESULT);
    fetchReasoning.mockResolvedValue(MOCK_REASONING_RESULT);

    const { result } = renderHook(() => useDetection());

    await act(async () => {
      await result.current.detect(MOCK_FILE);
    });

    expect(result.current.status).toBe('done');
    expect(result.current.result).toEqual(MOCK_DETECTION_RESULT);
    expect(result.current.error).toBeNull();
  });

  it('test_usedetection_detect_error_transitions_to_error', async () => {
    const { detectImage } = await getApi();
    detectImage.mockRejectedValue(new Error('Network failure'));

    const { result } = renderHook(() => useDetection());

    await act(async () => {
      await result.current.detect(MOCK_FILE);
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBe('Network failure');
  });

  it('test_usedetection_detect_success_triggers_reasoning', async () => {
    const { detectImage, fetchReasoning } = await getApi();
    detectImage.mockResolvedValue(MOCK_DETECTION_RESULT);
    fetchReasoning.mockResolvedValue(MOCK_REASONING_RESULT);

    const { result } = renderHook(() => useDetection());

    await act(async () => {
      await result.current.detect(MOCK_FILE);
    });

    // Reasoning should have been auto-triggered and completed
    expect(fetchReasoning).toHaveBeenCalledTimes(1);
    expect(result.current.reasoningStatus).toBe('done');
    expect(result.current.reasoning).toContain('Primary Diagnostic Assessment');
  });

  it('test_usedetection_reasoning_error_sets_error_state', async () => {
    const { detectImage, fetchReasoning } = await getApi();
    detectImage.mockResolvedValue(MOCK_DETECTION_RESULT);
    fetchReasoning.mockRejectedValue(new Error('LM Studio timeout'));

    const { result } = renderHook(() => useDetection());

    await act(async () => {
      await result.current.detect(MOCK_FILE);
    });

    expect(result.current.status).toBe('done'); // Detection itself succeeded
    expect(result.current.reasoningStatus).toBe('error');
    expect(result.current.reasoningError).toBe('LM Studio timeout');
  });

  it('test_usedetection_reset_clears_all_state', async () => {
    const { detectImage, fetchReasoning } = await getApi();
    detectImage.mockResolvedValue(MOCK_DETECTION_RESULT);
    fetchReasoning.mockResolvedValue(MOCK_REASONING_RESULT);

    const { result } = renderHook(() => useDetection());

    // First, run a detection to populate state
    await act(async () => {
      await result.current.detect(MOCK_FILE);
    });

    expect(result.current.status).toBe('done');

    // Now reset
    act(() => {
      result.current.reset();
    });

    expect(result.current.status).toBe('idle');
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.imagePreview).toBeNull();
    expect(result.current.reasoning).toBeNull();
    expect(result.current.reasoningStatus).toBe('idle');
    expect(result.current.reasoningError).toBeNull();
  });

  it('test_usedetection_reset_revokes_preview_url', async () => {
    const { detectImage, fetchReasoning } = await getApi();
    detectImage.mockResolvedValue(MOCK_DETECTION_RESULT);
    fetchReasoning.mockResolvedValue(MOCK_REASONING_RESULT);

    const { result } = renderHook(() => useDetection());

    await act(async () => {
      await result.current.detect(MOCK_FILE);
    });

    act(() => {
      result.current.reset();
    });

    // URL.revokeObjectURL should have been called with the preview URL
    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-preview-url');
  });
});
