/**
 * api.test.js — API client unit tests.
 * =======================================
 *
 * Tests that `detectImage` and `fetchReasoning` correctly construct
 * requests (FormData, JSON body, headers) and handle success/error
 * responses from the backend.
 *
 * Mocks `global.fetch` — no network access required.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { detectImage, fetchReasoning } from './api';

// ═══════════════════════════════════════════════════════════════════════════
// Setup — mock global.fetch
// ═══════════════════════════════════════════════════════════════════════════

let mockFetch;

beforeEach(() => {
  mockFetch = vi.fn();
  global.fetch = mockFetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Helper to create a successful Response-like object */
const okResponse = (body) => ({
  ok: true,
  status: 200,
  json: () => Promise.resolve(body),
  text: () => Promise.resolve(JSON.stringify(body)),
});

/** Helper to create a failed Response-like object */
const errorResponse = (status, body = 'Server error') => ({
  ok: false,
  status,
  json: () => Promise.resolve(body),
  text: () => Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
});


// ═══════════════════════════════════════════════════════════════════════════
// detectImage
// ═══════════════════════════════════════════════════════════════════════════

describe('detectImage', () => {
  const mockFile = new File(['image-data'], 'cow.jpg', { type: 'image/jpeg' });

  it('test_detectimage_sends_post_with_formdata', async () => {
    mockFetch.mockResolvedValue(okResponse({ cattle_detected: true }));

    await detectImage(mockFile);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/detect');
    expect(options.method).toBe('POST');
    expect(options.body).toBeInstanceOf(FormData);
  });

  it('test_detectimage_formdata_contains_image_field', async () => {
    mockFetch.mockResolvedValue(okResponse({ cattle_detected: true }));

    await detectImage(mockFile);

    const formData = mockFetch.mock.calls[0][1].body;
    expect(formData.get('image')).toBeTruthy();
    expect(formData.get('image').name).toBe('cow.jpg');
  });

  it('test_detectimage_returns_parsed_json_on_success', async () => {
    const mockResult = {
      cattle_detected: true,
      disease: { name: 'Lumpy Skin Disease', confidence: 91.5 },
    };
    mockFetch.mockResolvedValue(okResponse(mockResult));

    const result = await detectImage(mockFile);

    expect(result).toEqual(mockResult);
    expect(result.cattle_detected).toBe(true);
    expect(result.disease.name).toBe('Lumpy Skin Disease');
  });

  it('test_detectimage_throws_on_non_ok_response', async () => {
    mockFetch.mockResolvedValue(errorResponse(500, 'Internal Server Error'));

    await expect(detectImage(mockFile)).rejects.toThrow(/API error 500/);
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// fetchReasoning
// ═══════════════════════════════════════════════════════════════════════════

describe('fetchReasoning', () => {
  const mockDetectionResult = {
    cattle_detected: true,
    detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
    best_detection: {
      bbox: [10, 20, 100, 200],
      confidence: 0.95,
      bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
    },
    disease: { name: 'Mastitis', confidence: 88.3, all_probabilities: {} },
    image_size: { width: 640, height: 480 },
  };

  it('test_fetchreasoning_sends_post_with_json_body', async () => {
    mockFetch.mockResolvedValue(okResponse({
      status: 'ok',
      reasoning_report: 'Test report',
    }));

    await fetchReasoning(mockDetectionResult);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/reason');
    expect(options.method).toBe('POST');
    expect(options.headers['Content-Type']).toBe('application/json');
  });

  it('test_fetchreasoning_includes_all_detection_fields', async () => {
    mockFetch.mockResolvedValue(okResponse({ status: 'ok', reasoning_report: '' }));

    await fetchReasoning(mockDetectionResult);

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toHaveProperty('cattle_detected', true);
    expect(body).toHaveProperty('detections');
    expect(body.detections).toHaveLength(1);
    expect(body).toHaveProperty('best_detection');
    expect(body.best_detection.confidence).toBe(0.95);
    expect(body).toHaveProperty('disease');
    expect(body.disease.name).toBe('Mastitis');
    expect(body).toHaveProperty('image_size');
    expect(body.image_size.width).toBe(640);
  });

  it('test_fetchreasoning_returns_parsed_json_on_success', async () => {
    const mockResult = {
      status: 'ok',
      reasoning_report: '## 1. Primary Diagnostic Assessment\nAll clear.',
      model_name: 'qwen2.5-vl-3b-instruct',
    };
    mockFetch.mockResolvedValue(okResponse(mockResult));

    const result = await fetchReasoning(mockDetectionResult);

    expect(result).toEqual(mockResult);
    expect(result.status).toBe('ok');
    expect(result.reasoning_report).toContain('Primary Diagnostic');
  });

  it('test_fetchreasoning_throws_on_non_ok_response', async () => {
    mockFetch.mockResolvedValue(errorResponse(422, 'Validation Error'));

    await expect(fetchReasoning(mockDetectionResult)).rejects.toThrow(
      /Reasoning API error 422/
    );
  });
});
