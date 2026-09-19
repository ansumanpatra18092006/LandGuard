import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxy = { '/api': 'http://127.0.0.1:8000' };

// `preview` mirrors `server` so a production build can be exercised against the local API
// before deployment — the dashboard chunk only behaves realistically once it is bundled.
export default defineConfig({ plugins: [react()], server: { proxy }, preview: { proxy } });
