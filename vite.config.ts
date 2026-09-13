import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { readFileSync } from 'fs'

export default defineConfig({
  plugins: [
    react(),
    // MapLibre GL v6 carga maplibre-gl-shared.mjs como Worker en runtime
    // via new URL('./maplibre-gl-shared.mjs', import.meta.url).
    // Rollup no lo incluye en el output automáticamente, por lo que Vercel
    // devuelve index.html (text/html) cuando el browser lo pide → MIME error.
    // Este plugin copia el archivo al output del build en cada deploy.
    {
      name: 'copy-maplibre-worker',
      apply: 'build' as const,
      generateBundle() {
        this.emitFile({
          type: 'asset',
          fileName: 'assets/maplibre-gl-shared.mjs',
          source: readFileSync(
            path.resolve(__dirname, 'node_modules/maplibre-gl/dist/maplibre-gl-shared.mjs'),
            'utf-8'
          ),
        })
      },
    },
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('maplibre-gl')) return 'maplibre'
        },
      },
    },
  },
})
