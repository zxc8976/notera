const { defineConfig } = require('vite');
const vue = require('@vitejs/plugin-vue');
const path = require('path');
const { readFileSync } = require('fs');

// 讀取 package.json 版本號
const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'));

// 動態決定 API 代理目標：優先採用環境變數，否則預設本機後端
const apiTarget = process.env.VITE_API_BASE_URL || 'http://localhost:18000';
const hmrClientPort = Number(process.env.VITE_HMR_CLIENT_PORT || process.env.FRONTEND_PORT || process.env.VITE_PORT || 5173);
const devCspHeader = "default-src 'self' blob: data:; script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' 'inline-speculation-rules' chrome-extension:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' http: https: ws: wss:; frame-src 'self';";

module.exports = defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  base: '/',
  server: {
    host: '0.0.0.0',  // 維持 0.0.0.0 以支援容器與本機連線
    port: 5173,
    strictPort: true,
    cors: true,
    headers: {
      'Content-Security-Policy': devCspHeader
    },
    // 讓 HMR 使用預設主機（避免強制 localhost 造成容器環境下連線問題）
    hmr: {
      clientPort: hmrClientPort
    },
    proxy: {
      // API 代理配置
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
        timeout: 600000,  // 增加到10分鐘
        proxyTimeout: 600000,
        rewrite: (p) => p.replace(/^\/api/, '/api'),
        ws: true,  // 啟用 WebSocket 代理
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            console.log('❌ API Proxy error:', err.message, 'URL:', req.url)
            if (res && !res.headersSent) {
              res.writeHead(500, {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
              })
              res.end(JSON.stringify({
                error: 'API service unavailable: ' + err.message,
                message: '後端服務暫時不可用，請檢查 notegen 容器是否正常運行'
              }))
            }
          })
          proxy.on('proxyReq', (_proxyReq, req) => {
            console.log('🚀 API Request:', req.method, req.url, '->', apiTarget)
          })
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log('✅ API Response:', proxyRes.statusCode, req.url)
            if (proxyRes.statusCode >= 400) {
              console.log('❌ API Error:', proxyRes.statusCode, proxyRes.statusMessage)
            }
          })
        }
      },
      // WebSocket 代理配置
      '/ws': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            console.log('❌ WebSocket Proxy error:', err.message, 'URL:', req.url)
          })
          proxy.on('proxyReq', (_proxyReq, req) => {
            console.log('🔌 WebSocket Request:', req.url, '->', apiTarget)
          })
        }
      },
      // 圖片代理配置
      '/images': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
        timeout: 60000,
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            console.log('❌ Images proxy error:', err.message, req.url)
            if (res && !res.headersSent) {
              res.writeHead(404, {
                'Content-Type': 'text/plain',
                'Access-Control-Allow-Origin': '*'
              })
              res.end('Image not found')
            }
          })
          proxy.on('proxyReq', (_proxyReq, req) => {
            console.log('🖼️ Image Request:', req.url, '->', apiTarget)
          })
        }
      }
    }
  },
  preview: {
    host: '0.0.0.0',  // 同樣使用0.0.0.0
    port: 5173,
    strictPort: true,
    headers: {
      'Content-Security-Policy': devCspHeader
    }
  },
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(pkg.version)
  },
  optimizeDeps: {
    include: ['vue', 'vue-router', 'element-plus']
  }
});
