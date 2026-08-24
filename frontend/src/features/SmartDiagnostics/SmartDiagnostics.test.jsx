import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import SmartDiagnostics from './index';

// Custom render with MemoryRouter
const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

// Mock the API service to avoid real network calls
vi.mock('./services/api', () => ({
  detectImage: vi.fn(),
  fetchReasoning: vi.fn(),
  reportDiagnosticCase: vi.fn().mockResolvedValue({
    id: 'case-test-123',
    case_number: 'REC-2026-001',
    status: 'Verified',
    verified: true
  }),
  verifyDiagnosticCase: vi.fn(),
  fetchDiagnosticCases: vi.fn()
}));

// Mock URL.createObjectURL / revokeObjectURL for jsdom
const mockCreateObjectURL = vi.fn(() => 'blob:mock-preview-url');
const mockRevokeObjectURL = vi.fn();

beforeEach(() => {
  global.URL.createObjectURL = mockCreateObjectURL;
  global.URL.revokeObjectURL = mockRevokeObjectURL;
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Helper to get the mocked API functions */
const getDetectImage = async () => {
  const { detectImage } = await import('./services/api');
  return detectImage;
};

const getFetchReasoning = async () => {
  const { fetchReasoning } = await import('./services/api');
  return fetchReasoning;
};

describe('SmartDiagnostics', () => {
  it('renders the page title and dropzone in idle state', () => {
    renderWithRouter(<SmartDiagnostics />);
    expect(screen.getByText('AI-Powered Smart Diagnosis System')).toBeInTheDocument();
    expect(screen.getByText('Drag and drop clinical imagery')).toBeInTheDocument();
  });

  it('does not show results or failure views in idle state', () => {
    renderWithRouter(<SmartDiagnostics />);
    expect(screen.queryByTestId('success-view')).not.toBeInTheDocument();
    expect(screen.queryByTestId('failure-view')).not.toBeInTheDocument();
    expect(screen.queryByText('New Analysis')).not.toBeInTheDocument();
  });

  it('shows loading state after file upload', async () => {
    const detectImage = await getDetectImage();
    // Make it hang so we stay in loading state
    detectImage.mockImplementation(() => new Promise(() => {}));

    renderWithRouter(<SmartDiagnostics />);

    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    expect(screen.getByText('Running AI Diagnostics...')).toBeInTheDocument();
  });

  it('shows success view with disease name when detection succeeds', async () => {
    const detectImage = await getDetectImage();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Lumpy Skin Disease',
        confidence: 94.2,
        all_probabilities: { 'Lumpy Skin Disease': 94.2, Healthy: 3.0 },
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });

    renderWithRouter(<SmartDiagnostics />);

    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    expect(screen.getByTestId('predicted-condition')).toHaveTextContent('Lumpy Skin Disease');
    expect(screen.getByTestId('confidence-score')).toHaveTextContent('94.2%');
  });

  it('shows failure view when cattle is not detected', async () => {
    const detectImage = await getDetectImage();
    detectImage.mockResolvedValue({
      cattle_detected: false,
      detections: [],
      best_detection: null,
      disease: null,
      cropped_image: null,
      image_size: null,
      device: 'cpu',
    });

    renderWithRouter(<SmartDiagnostics />);

    const file = new File(['test'], 'cat.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('failure-view')).toBeInTheDocument();
    });

    expect(screen.getByText('Diagnosis Aborted')).toBeInTheDocument();
  });

  it('shows failure view on API error', async () => {
    const detectImage = await getDetectImage();
    detectImage.mockRejectedValue(new Error('Network failure'));

    renderWithRouter(<SmartDiagnostics />);

    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('failure-view')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Network failure').length).toBeGreaterThanOrEqual(1);
  });

  it('resets to idle state when "New Analysis" button is clicked', async () => {
    const detectImage = await getDetectImage();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Healthy',
        confidence: 98.0,
        all_probabilities: { Healthy: 98.0 },
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });

    renderWithRouter(<SmartDiagnostics />);

    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    // Click "New Analysis"
    const newAnalysisBtn = screen.getByText('New Analysis');
    await userEvent.click(newAnalysisBtn);

    expect(screen.getByText('Drag and drop clinical imagery')).toBeInTheDocument();
    expect(screen.queryByTestId('success-view')).not.toBeInTheDocument();
  });

  it('renders the header with Diagnostic Intake & Visual Triage badge', () => {
    renderWithRouter(<SmartDiagnostics />);
    expect(screen.getByText('Diagnostic Intake & Visual Triage')).toBeInTheDocument();
    expect(screen.getByText('AI-Powered Smart Diagnosis System')).toBeInTheDocument();
  });

  it('renders the pipeline version indicator', () => {
    renderWithRouter(<SmartDiagnostics />);
    expect(screen.getByText('CV Pipeline v3.2')).toBeInTheDocument();
  });

  it('displays confidence as a percentage without double multiplication', async () => {
    const detectImage = await getDetectImage();
    // Backend returns confidence already as a percentage (e.g. 74.3, not 0.743)
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Lumpy Skin Disease',
        confidence: 74.3,
        all_probabilities: { 'Lumpy Skin Disease': 74.3, Healthy: 12.1 },
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });

    renderWithRouter(<SmartDiagnostics />);

    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    // Must show 74.3%, NOT 7430.0% (the old double-multiplication bug)
    const scoreEl = screen.getByTestId('confidence-score');
    expect(scoreEl).toHaveTextContent('74.3%');
    expect(scoreEl).not.toHaveTextContent('7430');
  });

  // ═══════════════════════════════════════════════════════════════════════
  // New integration tests — bounding box overlay + ReasoningBriefing
  // ═══════════════════════════════════════════════════════════════════════

  it('shows bounding box overlay when bestBbox is present in detection result', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.05, y1: 0.1, x2: 0.5, y2: 0.6 },
      },
      disease: {
        name: 'Lumpy Skin Disease',
        confidence: 91.5,
        all_probabilities: { 'Lumpy Skin Disease': 91.5 },
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    fetchReasoning.mockResolvedValue({
      status: 'ok',
      reasoning_report: '## 1. Test\nContent',
      model_name: 'qwen',
    });

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    // The bounding box overlay div should exist with LESION_01 label
    expect(screen.getByText('LESION_01')).toBeInTheDocument();
  });

  it('renders ReasoningBriefing with clinical report after successful detection + reasoning', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Mastitis',
        confidence: 88.0,
        all_probabilities: { 'Mastitis': 88.0, 'Cattle (Healthy)': 12.0 },
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    fetchReasoning.mockResolvedValue({
      status: 'ok',
      reasoning_report: '## 1. Primary Diagnostic Assessment\nMastitis confirmed with high certainty.\n## 2. Pathological Rationale\nUdder swelling detected.',
      model_name: 'qwen2.5',
    });

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('reasoning-briefing')).toBeInTheDocument();
    });

    expect(screen.getByText('AI Clinical Briefing')).toBeInTheDocument();
  });

  it('shows reasoning loading skeleton while LLM reasoning is in progress', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Cattle (Healthy)',
        confidence: 95.0,
        all_probabilities: { 'Cattle (Healthy)': 95.0 },
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    // Make reasoning hang so we stay in loading state
    fetchReasoning.mockImplementation(() => new Promise(() => {}));

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    // ReasoningBriefing should show loading skeleton
    expect(screen.getByText(/Generating Clinical Briefing/)).toBeInTheDocument();
  });

  it('shows reasoning error fallback when LLM reasoning API fails', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Cattle (Healthy)',
        confidence: 95.0,
        all_probabilities: { 'Cattle (Healthy)': 95.0 },
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    fetchReasoning.mockRejectedValue(new Error('LM Studio connection refused'));

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    // ReasoningBriefing should show error fallback
    await waitFor(() => {
      expect(screen.getByText('Clinical Reasoning Unavailable')).toBeInTheDocument();
    });
  });

  it('renders Mask R-CNN symptom overlay when symptoms_image is provided', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Lumpy Skin Disease',
        confidence: 94.2,
        all_probabilities: { 'Lumpy Skin Disease': 94.2 },
      },
      cropped_image: 'data:image/jpeg;base64,mock-cropped-base64',
      symptoms_image: 'data:image/jpeg;base64,mock-symptoms-mask-base64',
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    fetchReasoning.mockResolvedValue({
      status: 'ok',
      reasoning_report: '## Diagnostic Briefing',
      model_name: 'qwen',
    });

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    // Mask R-CNN overlay image should be rendered
    const maskOverlay = screen.getByTestId('mask-rcnn-overlay');
    expect(maskOverlay).toBeInTheDocument();
    expect(maskOverlay).toHaveAttribute('src', 'data:image/jpeg;base64,mock-symptoms-mask-base64');
    expect(screen.getByText('Mask R-CNN Active')).toBeInTheDocument();
    expect(screen.getByText('MASK_RCNN_LESION')).toBeInTheDocument();
  });

  it('toggles Mask R-CNN symptom overlay visibility', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Lumpy Skin Disease',
        confidence: 94.2,
        all_probabilities: { 'Lumpy Skin Disease': 94.2 },
      },
      cropped_image: 'data:image/jpeg;base64,mock-cropped-base64',
      symptoms_image: 'data:image/jpeg;base64,mock-symptoms-mask-base64',
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    fetchReasoning.mockResolvedValue({
      status: 'ok',
      reasoning_report: '## Diagnostic Briefing',
      model_name: 'qwen',
    });

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    const toggleBtn = screen.getByTestId('toggle-symptom-mask-btn');
    expect(toggleBtn).toHaveTextContent('VISIBLE');
    expect(screen.getByTestId('mask-rcnn-overlay')).toBeInTheDocument();

    // Click toggle to hide mask
    await userEvent.click(toggleBtn);
    expect(toggleBtn).toHaveTextContent('HIDDEN');
    expect(screen.queryByTestId('mask-rcnn-overlay')).not.toBeInTheDocument();
    expect(screen.getByTestId('raw-crop-overlay')).toBeInTheDocument();

    // Click toggle again to restore mask
    await userEvent.click(toggleBtn);
    expect(toggleBtn).toHaveTextContent('VISIBLE');
    expect(screen.getByTestId('mask-rcnn-overlay')).toBeInTheDocument();
  });

  it('switches between Full Scan and Lesion Focus views', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.95, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.95,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Mastitis',
        confidence: 90.0,
        all_probabilities: { Mastitis: 90.0 },
      },
      cropped_image: 'data:image/jpeg;base64,mock-cropped-base64',
      symptoms_image: 'data:image/jpeg;base64,mock-symptoms-mask-base64',
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    fetchReasoning.mockResolvedValue({
      status: 'ok',
      reasoning_report: '## Diagnostic Briefing',
      model_name: 'qwen',
    });

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('success-view')).toBeInTheDocument();
    });

    // Default is Full Scan
    expect(screen.queryByTestId('lesion-focus-image')).not.toBeInTheDocument();

    // Click "Lesion Focus" button
    const lesionBtn = screen.getByTestId('view-mode-lesion-btn');
    await userEvent.click(lesionBtn);

    // Lesion Focus image and pathology legend should be displayed
    expect(screen.getByTestId('lesion-focus-image')).toBeInTheDocument();
    expect(screen.getByText('Mask R-CNN Pathological Area')).toBeInTheDocument();
    expect(screen.getByText('YOLO Bounding Margin')).toBeInTheDocument();

    // Click "Full Scan" button to switch back
    const fullScanBtn = screen.getByTestId('view-mode-full-btn');
    await userEvent.click(fullScanBtn);
    expect(screen.queryByTestId('lesion-focus-image')).not.toBeInTheDocument();
    expect(screen.getByTestId('mask-rcnn-overlay')).toBeInTheDocument();
  });

  it('renders LLM-synthesized clinical severity grade and pathological narrative', async () => {
    const detectImage = await getDetectImage();
    const fetchReasoning = await getFetchReasoning();
    detectImage.mockResolvedValue({
      cattle_detected: true,
      detections: [{ bbox: [10, 20, 100, 200], confidence: 0.96, class_name: 'cattle' }],
      best_detection: {
        bbox: [10, 20, 100, 200],
        confidence: 0.96,
        bbox_normalized: { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 },
      },
      disease: {
        name: 'Lumpy Skin Disease',
        confidence: 94.5,
        all_probabilities: { 'Lumpy Skin Disease': 94.5 },
      },
      severity: {
        grade: 'Moderate',
        description: 'Initial vision telemetry preview.',
        stage: 'Active Progression',
        prognosis: 'Recoverable',
        lesion_coverage_pct: 12.4,
        cluster_count: 7,
        source: 'vision_telemetry',
      },
      cropped_image: null,
      image_size: { width: 640, height: 480 },
      device: 'cpu',
    });
    fetchReasoning.mockResolvedValue({
      status: 'ok',
      reasoning_report: '## 1. Clinical Severity Assessment\nAcute systemic infection risk.',
      model_name: 'qwen2.5',
      severity_assessment: {
        grade: 'Severe',
        description: 'Extensive multifocal nodular eruptions with high viral load indicators.',
        stage: 'Acute Eruptive Phase',
        prognosis: 'Guarded',
        diagnostic_rationale: 'Characteristic circumscribed dermal nodules with central necrosis detected across the nape.',
        spatial_correlation: 'Automated segmentation localized 7 clusters at the Cervical & Dorsal Nape Region.',
        lesion_coverage_pct: 12.4,
        cluster_count: 7,
        source: 'llm_reasoning',
      },
    });

    renderWithRouter(<SmartDiagnostics />);
    const file = new File(['test'], 'cow.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');

    await act(async () => {
      await userEvent.upload(input, file);
    });

    await waitFor(() => {
      expect(screen.getByTestId('severity-grade')).toHaveTextContent('Severe');
    });

    expect(screen.getByTestId('severity-narrative')).toHaveTextContent(
      'Extensive multifocal nodular eruptions with high viral load indicators.'
    );
    expect(screen.getByTestId('diagnostic-rationale')).toHaveTextContent(
      'Characteristic circumscribed dermal nodules'
    );
    expect(screen.getByTestId('spatial-correlation')).toHaveTextContent(
      'Cervical & Dorsal Nape Region'
    );
    expect(screen.getAllByText('LLM REASONED').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('ANATOMICAL TELEMETRY')).toBeInTheDocument();
  });
});
