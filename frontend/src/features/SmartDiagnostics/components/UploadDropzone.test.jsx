import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import UploadDropzone from './UploadDropzone';

describe('UploadDropzone', () => {
  it('renders idle state with dropzone text', () => {
    render(<UploadDropzone onFile={vi.fn()} />);
    expect(screen.getByText('Drag and drop clinical imagery')).toBeInTheDocument();
    expect(screen.getByText('DICOM, JPG, or PNG up to 50MB')).toBeInTheDocument();
  });

  it('renders the section header "01 Image Intake"', () => {
    render(<UploadDropzone onFile={vi.fn()} />);
    expect(screen.getByText('01 Image Intake')).toBeInTheDocument();
  });

  it('renders loading state when isLoading is true', () => {
    render(<UploadDropzone isLoading onFile={vi.fn()} />);
    expect(screen.getByText('Running AI Diagnostics...')).toBeInTheDocument();
    expect(screen.getByText('Processing layers and extracting features')).toBeInTheDocument();
    expect(screen.queryByText('Drag and drop clinical imagery')).not.toBeInTheDocument();
  });

  it('calls onFile when a file is selected via file input', () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByTestId('file-input');
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFile).toHaveBeenCalledTimes(1);
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it('calls onFile when a file is dropped on the dropzone', () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);

    const file = new File(['test'], 'cow.png', { type: 'image/png' });
    const dropZone = screen.getByRole('button', { name: /upload clinical image/i });

    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    });

    expect(onFile).toHaveBeenCalledTimes(1);
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it('shows idle state test ID when not loading', () => {
    render(<UploadDropzone onFile={vi.fn()} />);
    expect(screen.getByTestId('idle-state')).toBeInTheDocument();
    expect(screen.queryByTestId('loading-state')).not.toBeInTheDocument();
  });

  it('shows loading state test ID when loading', () => {
    render(<UploadDropzone isLoading onFile={vi.fn()} />);
    expect(screen.getByTestId('loading-state')).toBeInTheDocument();
    expect(screen.queryByTestId('idle-state')).not.toBeInTheDocument();
  });
});
