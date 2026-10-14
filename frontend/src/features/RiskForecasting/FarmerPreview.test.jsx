import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('./services/storedForecastApi', () => ({
  fetchStoredDistrictRisks: vi.fn(),
}));

import { fetchStoredDistrictRisks } from './services/storedForecastApi';
import FarmerPreview, { isFarmerPreviewEnabled, PREVIEW_DISTRICTS } from './FarmerPreview';

const noRecord = { status: 'error', data: null, error: { category: 'NO_RECORD' } };

describe('FarmerPreview', () => {
  beforeEach(() => {
    fetchStoredDistrictRisks.mockReset().mockResolvedValue({ overallStatus: 'error', fmd: noRecord, lsd: noRecord });
  });

  it('is off unless explicitly enabled, and then reads nothing', () => {
    expect(isFarmerPreviewEnabled(undefined)).toBe(false);
    expect(isFarmerPreviewEnabled('false')).toBe(false);
    expect(isFarmerPreviewEnabled('true')).toBe(true);
    render(<FarmerPreview enabled={false} />);
    expect(screen.getByText('Farmer preview is disabled')).toBeInTheDocument();
    expect(fetchStoredDistrictRisks).not.toHaveBeenCalled();
  });

  it('offers all 25 districts and shows the stored forecast of the chosen one', async () => {
    render(<FarmerPreview enabled />);
    expect(PREVIEW_DISTRICTS).toHaveLength(25);
    await waitFor(() => expect(fetchStoredDistrictRisks).toHaveBeenCalledWith(expect.objectContaining({ district: 'Colombo' })));

    fireEvent.change(screen.getByLabelText('Preview district'), { target: { value: 'Kandy' } });
    await waitFor(() => expect(fetchStoredDistrictRisks).toHaveBeenCalledWith(expect.objectContaining({ district: 'Kandy' })));
    await waitFor(() => expect(screen.getAllByText('No forecast has been issued for this month yet.').length).toBeGreaterThan(0));
  });
});
