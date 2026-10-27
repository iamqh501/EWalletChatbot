import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_BACKEND_PORT || env.BACKEND_PORT || '8000'
  const adminPort = parseInt(env.VITE_ADMIN_PORT || env.ADMIN_PORT || '3001', 10)

  return {
    cacheDir: 'node_modules/.vite_admin',
    plugins: [
      react(),
      {
        name: 'admin-entry-rewrite',
        configureServer(server) {
          server.middlewares.use((req, res, next) => {
            const url = req.url ? req.url.split('?')[0] : ''
            if (url === '/' || url === '/index.html' || url === '/admin' || url === '/admin/') {
              const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
              req.url = '/admin.html' + query
            }
            next()
          })
        }
      }
    ],
    server: {
      host: '127.0.0.1',
      port: adminPort,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true
        }
      }
    },
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-dom/client',
        'lucide-react'
      ]
    },
    build: {
      rollupOptions: {
        input: {
          admin: 'admin.html'
        }
      }
    }
  }
})
