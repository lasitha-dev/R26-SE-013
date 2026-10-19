import '@testing-library/jest-dom';
import { vi } from 'vitest';

// MapLibre and file previews use browser URL APIs that jsdom does not implement.
if (!URL.createObjectURL) URL.createObjectURL = vi.fn(() => 'blob:test-preview');
if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();
