import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ImageEvidenceViewer from './ImageEvidenceViewer';
import ImageEvidenceStatus from './ImageEvidenceStatus';

describe('Image evidence', () => {
  it('maps the crop into the original portrait coordinate system', () => {
    const { container } = render(<ImageEvidenceViewer original="original" overlay="mask" showMask view="full"
      result={{ image_size: { width: 400, height: 1000 }, crop_transform: { crop_box: [50,300,250,800] } }} />);
    expect(screen.getByTestId('full-image-evidence')).toHaveAttribute('viewBox','0 0 400 1000');
    const layers = container.querySelectorAll('image');
    expect(layers[0]).toHaveAttribute('href','original');
    expect(layers[1]).toHaveAttribute('x','50');
    expect(layers[1]).toHaveAttribute('y','300');
    expect(layers[1]).toHaveAttribute('width','200');
    expect(layers[1]).toHaveAttribute('height','500');
  });
  it('distinguishes unavailable segmentation from a measured empty mask', () => {
    const { rerender } = render(<ImageEvidenceStatus result={{ segmentation: { status:'unavailable' } }} />);
    expect(screen.getByText(/measurements were not obtained/)).toBeInTheDocument();
    expect(screen.queryByText(/0%/)).not.toBeInTheDocument();
    rerender(<ImageEvidenceStatus result={{ segmentation: { status:'completed_no_regions', lesion_coverage_pct:0, cluster_count:0 } }} />);
    expect(screen.getByText(/0% of analyzed crop pixels; 0 connected regions/)).toBeInTheDocument();
  });
});
