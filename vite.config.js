import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: process.env.VITE_BASE_PATH || './',
  plugins: [vue()],
  server: {
    proxy: {
      '/start': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
        }
      },
      '/stop': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true
      },
      '/audio': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true,
        ws: true
      },
      '/events': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true
      },
      '/debug-env': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true
      },
      '/api': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true,
        proxyTimeout: 600000,
        timeout: 600000
      },
      '/ws': {
        target: 'ws://127.0.0.1:8771',
        ws: true,
        changeOrigin: true
      }
    }
  }
})
