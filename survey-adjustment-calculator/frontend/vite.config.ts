import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react(), {
    name: 'local-calculation-session', apply: 'serve',
    async transformIndexHtml(html) {
      const source = await fetch('http://127.0.0.1:8877').then(r => r.text())
      const session = source.match(/<script>window\.__SURVEY_TOKEN__=.*?<\/script>/)?.[0]
      if (!session) throw new Error('请先启动 python desktop.py --serve --port 8877')
      return html.replace('<head>', '<head>'+session)
    },
  }],
  base: './',
  build: { outDir: 'web-dist', chunkSizeWarningLimit: 900 },
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8877', changeOrigin: true, configure(proxy) { proxy.on('proxyReq', req => req.setHeader('Origin', 'http://127.0.0.1:8877')) } } } },
})
