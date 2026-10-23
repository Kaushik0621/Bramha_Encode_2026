import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
export default defineConfig(({mode}) => {
  // Vite's server reads only these non-secret settings. Never expose backend env
  // through `define`, a VITE_ variable, or client code.
  const serverEnv = loadEnv(mode, fileURLToPath(new URL('../backend', import.meta.url)), ['BACKEND_PORT', 'FRONTEND_ORIGIN']);
  const origin = new URL(process.env.FRONTEND_ORIGIN || serverEnv.FRONTEND_ORIGIN || 'http://localhost:8500');
  const port = Number(process.env.BACKEND_PORT || serverEnv.BACKEND_PORT || 8000);
  return { plugins: [react()], server: {port: Number(origin.port || 8500), strictPort: true, proxy: {'/api': `http://127.0.0.1:${port}`}}, preview: {port:4173} };
});
