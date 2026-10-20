import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests', workers: 1, timeout: 90000,
  reporter: [['list'], ['json', { outputFile: '../qa/react-browser-tests.json' }]],
  use: { baseURL: 'http://127.0.0.1:8877', channel: 'msedge', headless: true, viewport: { width: 1440, height: 1050 }, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: '..\\.venv\\Scripts\\python.exe ..\\desktop.py --serve --port 8877', url: 'http://127.0.0.1:8877', reuseExistingServer: false },
})
