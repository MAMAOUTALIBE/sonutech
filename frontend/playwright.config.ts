import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1, retries: 0,
  timeout: 60000, reporter: [['list']],
  use: { baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000', viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
});
