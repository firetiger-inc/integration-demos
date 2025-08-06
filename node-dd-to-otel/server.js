#!/usr/bin/env node

import { config } from 'dotenv';
import express from 'express';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Serve static files
app.use(express.static('.'));

// Health endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development'
  });
});

// Config endpoint for client-side applications
app.get('/config', (req, res) => {
  const config = {
    clientToken: process.env.DD_CLIENT_TOKEN,
    site: process.env.DD_SITE || 'us5.datadoghq.com',
    service: process.env.DD_SERVICE || 'browser-extension',
    env: process.env.DD_ENV || 'demo',
    version: process.env.DD_VERSION || '1.0.0',
    proxyEndpoint: process.env.PROXY_ENDPOINT
  };

  // Validate required fields
  if (!config.clientToken) {
    return res.status(500).json({
      error: 'DD_CLIENT_TOKEN environment variable is required'
    });
  }

  res.json(config);
});

// Serve the demo HTML with environment variables injected
app.get('/demo', (req, res) => {
  try {
    const htmlTemplate = readFileSync(join(__dirname, 'browser-demo.html'), 'utf8');
    
    // Inject environment variables into the HTML
    const injectedHtml = htmlTemplate
      .replace('{{DD_CLIENT_TOKEN}}', process.env.DD_CLIENT_TOKEN || '')
      .replace('{{DD_SITE}}', process.env.DD_SITE || 'us5.datadoghq.com')
      .replace('{{DD_SERVICE}}', process.env.DD_SERVICE || 'browser-extension')
      .replace('{{DD_ENV}}', process.env.DD_ENV || 'demo')
      .replace('{{DD_VERSION}}', process.env.DD_VERSION || '1.0.0')
      .replace('{{PROXY_ENDPOINT}}', process.env.PROXY_ENDPOINT || 'https://ddproxy.rustaml.workers.dev');

    res.setHeader('Content-Type', 'text/html');
    res.send(injectedHtml);
  } catch (error) {
    console.error('Error serving demo page:', error);
    res.status(500).json({ error: 'Failed to serve demo page' });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Demo server running at http://localhost:${PORT}`);
  console.log(`📱 Demo page: http://localhost:${PORT}/demo`);
  console.log(`⚙️  Config API: http://localhost:${PORT}/config`);
  
  if (!process.env.DD_CLIENT_TOKEN) {
    console.log('⚠️  Warning: DD_CLIENT_TOKEN not set - demo will not work');
    console.log('💡 Set environment variables in .env file');
  }
});