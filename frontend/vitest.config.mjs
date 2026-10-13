import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.mjs'],
    css: false,
    env: { VITE_FORECAST_REFERENCE_PERIOD: '2024-12' },
  },
});
