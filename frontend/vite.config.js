import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const rootEnvDir = path.resolve(import.meta.dirname, '..')

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootEnvDir, '')
  const backendPort = env.BACKEND_PORT || '8000'
  const userPort = parseInt(env.FRONTEND_PORT || '3000', 10)

  return {
    envDir: rootEnvDir,
    envPrefix: ['BACKEND_', 'FRONTEND_', 'ADMIN_'],
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
