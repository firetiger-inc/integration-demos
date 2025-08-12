#!/usr/bin/env node

import { config } from 'dotenv';
import fetch from 'node-fetch';

config();

const BASE_URL = 'http://localhost:3000';

async function testServer() {
  console.log('🧪 Testing demo server...');

  try {
    // Test health endpoint
    console.log('📊 Testing health endpoint...');
    const healthResponse = await fetch(`${BASE_URL}/health`);
    const healthData = await healthResponse.json();
    console.log('✅ Health check:', healthData.status);

    // Test config endpoint
    console.log('⚙️ Testing config endpoint...');
    const configResponse = await fetch(`${BASE_URL}/config`);
    const configData = await configResponse.json();
    
    if (configData.error) {
      console.log('❌ Config error:', configData.error);
    } else {
      console.log('✅ Config loaded:');
      console.log(`  - Client Token: ${configData.clientToken?.substring(0, 10)}...`);
      console.log(`  - Site: ${configData.site}`);
      console.log(`  - Service: ${configData.service}`);
      console.log(`  - Environment: ${configData.env}`);
      console.log(`  - Proxy: ${configData.proxyEndpoint || 'Not configured'}`);
    }

    // Test demo page
    console.log('🎮 Testing demo page...');
    const demoResponse = await fetch(`${BASE_URL}/demo`);
    const demoHtml = await demoResponse.text();
    
    if (demoHtml.includes('{{DD_CLIENT_TOKEN}}')) {
      console.log('❌ Demo page has unresolved template variables');
    } else {
      console.log('✅ Demo page rendered with environment variables');
      console.log(`📱 Demo available at: ${BASE_URL}/demo`);
    }

  } catch (error) {
    console.error('❌ Test failed:', error.message);
    console.log('💡 Make sure the server is running: npm run demo');
  }
}

testServer();