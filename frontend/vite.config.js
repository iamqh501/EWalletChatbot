import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_BACKEND_PORT || env.BACKEND_PORT || '8000'
  const userPort = parseInt(env.VITE_USER_PORT || env.FRONTEND_PORT || '3000', 10)

  return {
    plugins: [react()],
    cacheDir: 'node_modules/.vite_user',
    server: {
      host: '127.0.0.1',
      port: userPort,
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
        'react-markdown',
        'remark-math',
        'remark-gfm',
        'rehype-katex',
        'lucide-react'
      ]
    }
  }
})
