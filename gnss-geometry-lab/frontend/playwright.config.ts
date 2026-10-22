import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir:'./tests', testMatch:'*.spec.ts', workers:1, timeout:60000,
  reporter:[['list'],['json',{outputFile:'../qa/browser-tests.json'}]],
  use:{baseURL:'http://127.0.0.1:8892',channel:'msedge',headless:true,viewport:{width:1440,height:1050},screenshot:'only-on-failure',trace:'retain-on-failure'},
  webServer:{command:'..\\.venv\\Scripts\\python.exe ..\\desktop.py --serve --port 8892',url:'http://127.0.0.1:8892',reuseExistingServer:false},
})
