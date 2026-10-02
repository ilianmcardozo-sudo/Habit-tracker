// Copies the web app (static files, no build step) into www/.
// Capacitor packs www/ into the Android app, and Vercel serves the same folder.
import { cpSync, mkdirSync, rmSync } from 'node:fs';
const FILES = ['index.html', 'cloud.js', 'config.js', 'manifest.webmanifest', 'icons', 'vendor'];
rmSync('www', { recursive: true, force: true });
mkdirSync('www');
for (const f of FILES) cpSync(f, `www/${f}`, { recursive: true });
console.log('www/ listo:', FILES.join(', '));
