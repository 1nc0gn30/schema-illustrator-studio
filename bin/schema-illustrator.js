#!/usr/bin/env node
/**
 * Schema Illustrator Studio — Unified CLI & Desktop Workstation Launcher
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.resolve(__dirname, '..');
const srcDir = path.join(rootDir, 'src');
const args = process.argv.slice(2);
const defaultPort = process.env.PORT || '8099';

const isWeb = args[0] === 'web' || args.includes('--web');
const isAppRequest = !isWeb && (args.length === 0 || args.includes('--gui') || args.includes('--app') || args.includes('--desktop') || args[0] === 'app' || args[0] === 'desktop' || args[0] === 'gui');

if (isWeb) {
  console.log(`Launching Schema Illustrator Studio Web UI on http://127.0.0.1:${defaultPort} ...`);
  const pyChild = spawn('python3', ['-m', 'schema_illustrator_studio.cli', 'serve', '--port', String(defaultPort), '--no-open'], {
    cwd: rootDir,
    stdio: 'inherit',
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH ? `${srcDir}:${process.env.PYTHONPATH}` : srcDir,
      ZOTH_ZERO_EGRESS: 'true',
    },
  });
  pyChild.on('error', (pyErr) => {
    console.error('[SchemaIllustrator] Failed to start web server:', pyErr);
  });
} else if (isAppRequest) {
  console.log('Launching Schema Illustrator Studio Desktop Workstation...');

  const localElectron = path.join(rootDir, 'node_modules', '.bin', 'electron');
  const electronCmd = fs.existsSync(localElectron) ? localElectron : 'electron';

  const child = spawn(electronCmd, ['.'], {
    cwd: rootDir,
    stdio: 'inherit',
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH ? `${srcDir}:${process.env.PYTHONPATH}` : srcDir,
      ELECTRON_ENABLE_LOGGING: '1',
      ZOTH_ZERO_EGRESS: 'true',
    },
  });

  child.on('error', (err) => {
    console.warn(`[SchemaIllustrator] Electron notice: ${err.message}. Starting web UI on port ${defaultPort}...`);
    const pyChild = spawn('python3', ['-m', 'schema_illustrator_studio.cli', 'serve', '--port', String(defaultPort), '--no-open'], {
      cwd: rootDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        PYTHONPATH: process.env.PYTHONPATH ? `${srcDir}:${process.env.PYTHONPATH}` : srcDir,
      },
    });
    pyChild.on('error', (pyErr) => {
      console.error('[SchemaIllustrator] Failed to start backend:', pyErr);
    });
  });
} else {
  const child = spawn('python3', ['-m', 'schema_illustrator_studio.cli', ...args], {
    cwd: rootDir,
    stdio: 'inherit',
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH ? `${srcDir}:${process.env.PYTHONPATH}` : srcDir,
    },
  });

  child.on('exit', (code) => {
    process.exit(code || 0);
  });
}
