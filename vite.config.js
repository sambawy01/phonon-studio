import { defineConfig } from 'vite';

// GitHub Pages serves from https://<user>.github.io/<repo>/, so the base must be the repo name.
// Set BASE_PATH=/ for a custom domain or a user pages repo.
export default defineConfig({
  base: process.env.BASE_PATH || '/phonon-studio/',
  build: {
    target: 'esnext',
    // The wasm worker and the engine are large; keep them out of the inline bundle.
    assetsInlineLimit: 0,
  },
  worker: { format: 'es' },
  optimizeDeps: { exclude: ['phonon-tts'] },
});
