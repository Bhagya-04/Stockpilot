// Single-page-app fallback for static hosts: serve the app itself for any unknown path.
// Render (and many static hosts) show dist/404.html for paths that don't match a file, so a copy of
// index.html there makes deep links like /login or /w/<id>/orders load the app after a refresh.
import { copyFileSync } from 'node:fs';

copyFileSync('dist/index.html', 'dist/404.html');
console.log('postbuild: dist/404.html created (SPA fallback)');
