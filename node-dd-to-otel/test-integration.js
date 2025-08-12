import { config } from 'dotenv';
import fetch from 'node-fetch';

config();

const WORKER_URL = process.env.WORKER_URL || 'http://localhost:8787'; // Default for wrangler dev
const DD_CLIENT_TOKEN = process.env.DD_CLIENT_TOKEN;

class IntegrationTester {
  constructor() {
    this.results = [];
  }

  async runTest(testName, testFn) {
    console.log(`\n🧪 Running test: ${testName}`);
    const startTime = Date.now();
    
    try {
      await testFn();
      const duration = Date.now() - startTime;
      console.log(`✅ ${testName} - PASSED (${duration}ms)`);
      this.results.push({ name: testName, status: 'PASSED', duration });
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`❌ ${testName} - FAILED (${duration}ms):`, error.message);
      this.results.push({ name: testName, status: 'FAILED', duration, error: error.message });
    }
  }

  async testHealthEndpoint() {
    const response = await fetch(`${WORKER_URL}/health`);
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    
    const data = await response.json();
    if (!data.status || data.status !== 'healthy') {
      throw new Error('Health endpoint returned unhealthy status');
    }
    
    console.log('  📊 Health data:', data);
  }

  async testLogsProxy() {
    if (!DD_CLIENT_TOKEN) {
      throw new Error('DD_CLIENT_TOKEN not configured');
    }

    const logEntry = {
      ddsource: 'test',
      ddtags: 'env:test,service:integration-test',
      message: 'Integration test log entry',
      level: 'info',
      timestamp: new Date().toISOString(),
      testId: `test_${Date.now()}`
    };

    const response = await fetch(`${WORKER_URL}/v1/input/${DD_CLIENT_TOKEN}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(logEntry)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Logs proxy failed: ${response.status} - ${errorText}`);
    }

    const result = await response.json();
    console.log('  📝 Log proxy result:', result);

    if (!result.success) {
      throw new Error('Log proxy reported failure');
    }
  }

  async testCORS() {
    const response = await fetch(`${WORKER_URL}/v1/input/test`, {
      method: 'OPTIONS',
      headers: {
        'Origin': 'https://example.com',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type'
      }
    });

    if (response.status !== 204) {
      throw new Error(`CORS preflight failed: ${response.status}`);
    }

    const corsHeaders = [
      'Access-Control-Allow-Origin',
      'Access-Control-Allow-Methods', 
      'Access-Control-Allow-Headers'
    ];

    for (const header of corsHeaders) {
      if (!response.headers.get(header)) {
        throw new Error(`Missing CORS header: ${header}`);
      }
    }

    console.log('  🌐 CORS headers validated');
  }

  async testInvalidEndpoint() {
    const response = await fetch(`${WORKER_URL}/invalid-endpoint`);
    
    if (response.status !== 404) {
      throw new Error(`Expected 404 for invalid endpoint, got: ${response.status}`);
    }
    
    console.log('  🚫 Invalid endpoint correctly returns 404');
  }

  async testWithoutClientToken() {
    const response = await fetch(`${WORKER_URL}/v1/input/invalid-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'test' })
    });

    // This should fail at the DataDog level, but worker should still respond
    console.log(`  🔑 Invalid token test returned: ${response.status}`);
  }

  printResults() {
    console.log('\n📋 Test Results Summary:');
    console.log('=' .repeat(50));
    
    const passed = this.results.filter(r => r.status === 'PASSED').length;
    const failed = this.results.filter(r => r.status === 'FAILED').length;
    
    this.results.forEach(result => {
      const icon = result.status === 'PASSED' ? '✅' : '❌';
      console.log(`${icon} ${result.name} (${result.duration}ms)`);
      if (result.error) {
        console.log(`   Error: ${result.error}`);
      }
    });
    
    console.log('=' .repeat(50));
    console.log(`Total: ${this.results.length} | Passed: ${passed} | Failed: ${failed}`);
    
    if (failed > 0) {
      process.exit(1);
    }
  }
}

async function main() {
  console.log('🚀 Starting Integration Tests');
  console.log(`📡 Worker URL: ${WORKER_URL}`);
  console.log(`🔑 DD Client Token: ${DD_CLIENT_TOKEN ? '***' + DD_CLIENT_TOKEN.slice(-4) : 'NOT SET'}`);

  const tester = new IntegrationTester();

  // Run all tests
  await tester.runTest('Health Endpoint', () => tester.testHealthEndpoint());
  await tester.runTest('CORS Preflight', () => tester.testCORS());
  await tester.runTest('Invalid Endpoint', () => tester.testInvalidEndpoint());
  await tester.runTest('Logs Proxy', () => tester.testLogsProxy());
  await tester.runTest('Invalid Token Handling', () => tester.testWithoutClientToken());

  // Print final results
  tester.printResults();
}

main().catch(console.error);