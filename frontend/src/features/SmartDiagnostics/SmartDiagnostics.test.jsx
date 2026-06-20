import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SmartDiagnostics from './index';

// Mock the API service to avoid real network calls
vi.mock('./services/api', () => ({
  detectImage: vi.fn(),
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

/** Helper to get the mocked detectImage */
const getDetectImage = async () => {
  const { detectImage } = await import('./services/api');
  return detectImage;
};

describe('SmartDiagnostics', () => {
  it('renders the page title and dropzone in idle state', () => {
    render(<SmartDiagnostics />);
    expect(screen.getByText('AI-Powered Smart Diagnosis System')).toBeInTheDocument();
    expect(screen.getByText('Drag and drop clinical imagery')).toBeInTheDocument();
  });

  it('does not show results or failure views in idle state', () => {
    render(<SmartDiagnostics />);
    expect(screen.queryByTestId('success-view')).not.toBeInTheDocument();
    expect(screen.queryByTestId('failure-view')).not.toBeInTheDocument();
    expect(screen.queryByText('New Analysis')).not.toBeInTheDocument();
  });

  it('shows loading state after file upload', async () => {
    const detectImage = await getDetectImage();
    // Make it hang so we stay in loading state
    detectImage.mockImplementation(() => new Promise(() => {}));

    render(<SmartDiagnostics />);

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

    render(<SmartDiagnostics />);

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

    render(<SmartDiagnostics />);

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

    render(<SmartDiagnostics />);

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

    render(<SmartDiagnostics />);

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

  it('renders the sidebar with ADRS Core branding', () => {
    render(<SmartDiagnostics />);
    expect(screen.getByText('ADRS Core')).toBeInTheDocument();
    expect(screen.getByText('Precision Sentinel')).toBeInTheDocument();
  });

  it('renders the top header with AI Diagnostics Panel title', () => {
    render(<SmartDiagnostics />);
    expect(screen.getByText('AI Diagnostics Panel')).toBeInTheDocument();
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

    render(<SmartDiagnostics />);

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
});
